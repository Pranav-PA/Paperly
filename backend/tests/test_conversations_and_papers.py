import json


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
    msg2 = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Please generate the paper now with 35 marks, moderate difficulty."},
        headers=auth_headers
    )
    assert msg2.status_code == 200
    meta = json.loads(msg2.json()["metadata_json"])
    assert meta["action"] == "ready_to_generate"
    paper_id = meta["paper_id"]
    assert paper_id is not None

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
    assert edit_res.status_code == 200
    edit_data = edit_res.json()
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


def test_sse_streaming_message(client, auth_headers):
    # 1. Create conversation
    create_res = client.post(
        "/api/v1/conversations",
        json={"title": "Streaming Test"},
        headers=auth_headers
    )
    conv_id = create_res.json()["id"]

    # 2. Stream a message
    stream_res = client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Generate a quick 10-mark math test."},
        headers=auth_headers
    )
    assert stream_res.status_code == 200
    text = stream_res.text
    assert "data: " in text
    assert "requirements" in text
    assert "complete" in text
