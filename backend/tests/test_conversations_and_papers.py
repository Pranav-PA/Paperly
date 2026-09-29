import json
import time


def wait_job(client, headers, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def generate(client, headers, conv_id, text="generate"):
    """Send a message that triggers generation and wait for the paper; returns the paper id."""
    res = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": text}, headers=headers)
    assert res.status_code == 200, res.text
    meta = json.loads(res.json()["metadata_json"])
    assert meta["action"] == "working"
    job = wait_job(client, headers, meta["job_id"])
    assert job["status"] == "done", job
    return job["result"]["paper_id"]


def test_create_and_list_conversations(client, auth_headers):
    # 1. Create conversation
    res = client.post(
        "/api/v1/conversations",
        json={"title": "NEET Physics Test"},
        headers=auth_headers
    )
    assert res.status_code == 201
    conv = res.json()
    assert conv["title"] == "NEET Physics Test"
    conv_id = conv["id"]

    # 2. List conversations
    res_list = client.get("/api/v1/conversations", headers=auth_headers)
    assert res_list.status_code == 200
    convs = res_list.json()
    assert any(c["id"] == conv_id for c in convs)


def test_full_conversation_generation_edit_export_flow(client, auth_headers):
    # 1. Create conversation
    create_res = client.post(
        "/api/v1/conversations",
        json={"title": "Class 12 Physics Test"},
        headers=auth_headers
    )
    conv_id = create_res.json()["id"]

    # 2. Post initial message (clarification)
    msg1 = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I want to create a physics paper on electrostatics."},
        headers=auth_headers
    )
    assert msg1.status_code == 200
    assert "difficulty" in msg1.json()["content"].lower()

    # 3. Post confirmation message triggering paper generation
    paper_id = generate(client, auth_headers, conv_id, "Please generate the paper now with 35 marks, moderate difficulty.")
    assert paper_id is not None
    detail = client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers).json()
    assert detail["latest_paper_id"] == paper_id
    assert detail["active_job_id"] is None
    assert "is ready" in detail["messages"][-1]["content"]

    # 4. Fetch the generated PaperSchema
    paper_res = client.get(f"/api/v1/papers/{paper_id}", headers=auth_headers)
    assert paper_res.status_code == 200
    schema = paper_res.json()
    assert schema["metadata"]["subject"] == "Physics"
    assert len(schema["sections"]) >= 1

    # 5. Perform conversational in-place editing
    edit_res = client.post(
        f"/api/v1/papers/{paper_id}/edit",
        json={"instruction": "Make question 1 harder."},
        headers=auth_headers
    )
    assert edit_res.status_code == 202
    edit_job = wait_job(client, auth_headers, edit_res.json()["job_id"])
    assert edit_job["status"] == "done"
    edit_data = edit_job["result"]
    assert edit_data["version_number"] == 2
    assert "Question 1" in edit_data["change_summary"]

    # 6. Export question paper to DOCX
    docx_res = client.get(f"/api/v1/papers/{paper_id}/export/docx", headers=auth_headers)
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 1000  # valid binary docx
    assert docx_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # 7. Export question paper to PDF/HTML
    pdf_res = client.get(f"/api/v1/papers/{paper_id}/export/pdf", headers=auth_headers)
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 500

    # 8. Export Solutions to DOCX
    sol_docx = client.get(f"/api/v1/papers/{paper_id}/solutions/docx", headers=auth_headers)
    assert sol_docx.status_code == 200
    assert len(sol_docx.content) > 500

    # 9. Export Solutions to PDF/HTML
    sol_pdf = client.get(f"/api/v1/papers/{paper_id}/solutions/pdf", headers=auth_headers)
    assert sol_pdf.status_code == 200
    assert len(sol_pdf.content) > 500

    # 10. Check version history
    versions_res = client.get(f"/api/v1/papers/{paper_id}/versions", headers=auth_headers)
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) >= 2
    assert versions[0]["version_number"] == 2

    # 11. Revert to version 1 (undo)
    revert_res = client.post(f"/api/v1/papers/{paper_id}/revert/1", headers=auth_headers)
    assert revert_res.status_code == 200
    assert revert_res.json()["version_number"] == 1


def test_regeneration_creates_new_version_and_lists_papers(client, auth_headers):
    conv_id = client.post("/api/v1/conversations", json={"title": "Regen"}, headers=auth_headers).json()["id"]
    paper_id = generate(client, auth_headers, conv_id)
    assert generate(client, auth_headers, conv_id, "generate again") == paper_id

    versions = client.get(f"/api/v1/papers/{paper_id}/versions", headers=auth_headers).json()
    assert [v["version_number"] for v in versions] == [2, 1]

    papers = client.get("/api/v1/papers", headers=auth_headers).json()
    assert any(p["id"] == paper_id and p["question_count"] == 3 for p in papers)

    listed = client.get("/api/v1/conversations", headers=auth_headers).json()
    assert next(c for c in listed if c["id"] == conv_id)["latest_paper_id"] == paper_id


def test_generated_totals_match_questions(client, auth_headers):
    conv_id = client.post("/api/v1/conversations", json={}, headers=auth_headers).json()["id"]
    paper_id = generate(client, auth_headers, conv_id)
    schema = client.get(f"/api/v1/papers/{paper_id}", headers=auth_headers).json()
    marks = sum(q["marks"] for s in schema["sections"] for q in s["questions"])
    assert schema["metadata"]["total_marks"] == marks
    numbers = [q["question_number"] for s in schema["sections"] for q in s["questions"]]
    assert numbers == list(range(1, len(numbers) + 1))


def test_delete_conversation(client, auth_headers):
    conv_id = client.post("/api/v1/conversations", json={"title": "Temp"}, headers=auth_headers).json()["id"]
    assert client.delete(f"/api/v1/conversations/{conv_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers).status_code == 404


def test_upload_text_and_reject_unsupported(client, auth_headers):
    conv_id = client.post("/api/v1/conversations", json={}, headers=auth_headers).json()["id"]
    ok = client.post(
        f"/api/v1/conversations/{conv_id}/upload",
        files={"file": ("notes.txt", b"Chapter 1: Newton's laws", "text/plain")},
        headers=auth_headers,
    )
    assert ok.status_code == 200 and ok.json()["extracted_characters"] > 0
    bad = client.post(
        f"/api/v1/conversations/{conv_id}/upload",
        files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
        headers=auth_headers,
    )
    assert bad.status_code == 415
    # Photos need Gemini to read them; in offline demo mode they're refused with a clear message.
    photo = client.post(
        f"/api/v1/conversations/{conv_id}/upload",
        files={"file": ("photo.jpg", b"\xff\xd8\xff", "image/jpeg")},
        headers=auth_headers,
    )
    assert photo.status_code == 422


def test_ai_failure_returns_502_without_saving(client, auth_headers, monkeypatch):
    from app.services.ai_service import AIService, AIServiceError

    async def boom(*args, **kwargs):
        raise AIServiceError("Gemini rejected the API key.")

    monkeypatch.setattr(AIService, "decide", boom)
    conv_id = client.post("/api/v1/conversations", json={}, headers=auth_headers).json()["id"]
    res = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=auth_headers)
    assert res.status_code == 502
    assert "API key" in res.json()["detail"]
    assert client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers).json()["messages"] == []


def test_generation_failure_posts_error_message(client, auth_headers, monkeypatch):
    from app.services.ai_service import AIService, AIServiceError

    async def boom(*args, **kwargs):
        raise AIServiceError("Gemini rate limit or quota reached.")

    monkeypatch.setattr(AIService, "generate_paper", boom)
    conv_id = client.post("/api/v1/conversations", json={}, headers=auth_headers).json()["id"]
    res = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "generate"}, headers=auth_headers)
    job = wait_job(client, auth_headers, json.loads(res.json()["metadata_json"])["job_id"])
    assert job["status"] == "error" and "quota" in job["error"]
    msgs = client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers).json()["messages"]
    assert "couldn't finish" in msgs[-1]["content"]


def send(client, headers, conv_id, text):
    res = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": text}, headers=headers)
    assert res.status_code == 200, res.text
    return json.loads(res.json()["metadata_json"])


def test_uploaded_paper_is_imported_and_edited_not_regenerated(client, auth_headers):
    conv_id = client.post("/api/v1/conversations", json={"title": "Edit doc"}, headers=auth_headers).json()["id"]
    doc = b"Class 8 Science Test\n1. What is photosynthesis?\n2. Name the parts of a flower.\n3. What is friction?\n"
    up = client.post(f"/api/v1/conversations/{conv_id}/upload",
                     files={"file": ("science_test.txt", doc, "text/plain")}, headers=auth_headers)
    assert up.status_code == 200

    meta = send(client, auth_headers, conv_id, "Change the last question to What is inertia?")
    assert meta["action"] == "working" and meta["kind"] == "import"
    job = wait_job(client, auth_headers, meta["job_id"])
    assert job["status"] == "done", job
    paper = client.get(f"/api/v1/papers/{job['result']['paper_id']}", headers=auth_headers).json()
    texts = [q["text"] for s in paper["sections"] for q in s["questions"]]
    # Original questions kept, only the last one changed.
    assert texts == ["What is photosynthesis?", "Name the parts of a flower.", "What is inertia?"]


def test_chat_edits_existing_paper_layout(client, auth_headers):
    conv_id = client.post("/api/v1/conversations", json={}, headers=auth_headers).json()["id"]
    paper_id = generate(client, auth_headers, conv_id)
    meta = send(client, auth_headers, conv_id, "Make it two columns with a serif font")
    assert meta["kind"] == "edit"
    job = wait_job(client, auth_headers, meta["job_id"])
    assert job["status"] == "done" and job["result"]["paper_id"] == paper_id
    paper = client.get(f"/api/v1/papers/{paper_id}", headers=auth_headers).json()
    assert paper["layout"]["columns"] == 2 and paper["layout"]["font_family"] == "serif"
    msgs = client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers).json()["messages"]
    assert json.loads(msgs[-1]["metadata_json"])["action"] == "paper_updated"
    for fmt in ("pdf", "docx"):
        assert client.get(f"/api/v1/papers/{paper_id}/export/{fmt}", headers=auth_headers).status_code == 200
        assert client.get(f"/api/v1/papers/{paper_id}/solutions/{fmt}", headers=auth_headers).status_code == 200

