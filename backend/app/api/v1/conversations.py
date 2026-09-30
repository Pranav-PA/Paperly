import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.models.conversation import Conversation, Message, UploadedFile
from app.models.paper import Paper, PaperVersion
from app.schemas.conversation import (
    ConversationCreate,
    ConversationSummary,
    ConversationDetail,
    MessageCreate,
    MessageResponse,
    FileUploadResponse,
)
from app.schemas.paper_schema import PaperSchema
from app.services import doc_edit, documents, jobs
from app.services.ai_service import AIService, AIServiceError, SourceDoc
from app.services.extract_service import DocumentExtractionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["Conversations"])

# Keep prompts bounded on a low-memory phone: total characters of uploaded text sent to the model.
MAX_SOURCE_CHARS = 200_000

# Files Gemini can read directly (layout, maths, handwriting); these are stored as-is.
RAW_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def _get_user_conversation(conv_id: str, user: User, db: Session) -> Conversation:
    conv = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.user_id == user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _latest_paper(conv_id: str, db: Session) -> Optional[Paper]:
    return db.query(Paper).filter(Paper.conversation_id == conv_id).order_by(Paper.created_at.desc()).first()


def _current_version(conv_id: str, db: Session) -> Optional[PaperVersion]:
    paper = _latest_paper(conv_id, db)
    if not paper or not paper.current_version_id:
        return None
    return db.get(PaperVersion, paper.current_version_id)


def _raw_path(file_id: str, filename: str) -> Path:
    return Path(settings.UPLOAD_DIR) / f"{file_id}{Path(filename).suffix.lower()}"


def _open_filename(conv: Conversation) -> Optional[str]:
    """Filename of the upload currently open as the chat's document (None if it's a Paperly-made paper)."""
    for m in reversed(conv.messages):
        meta = json.loads(m.metadata_json) if m.metadata_json else {}
        if meta.get("action") in ("paper_ready", "paper_updated"):
            return meta.get("opened_file")  # None when a generated/converted paper replaced the upload
    return None


def _sources(conv_id: str, db: Session, exclude: Optional[str] = None) -> List[SourceDoc]:
    files = db.query(UploadedFile).filter(UploadedFile.conversation_id == conv_id).order_by(UploadedFile.created_at).all()
    files = [f for f in files if f.filename != exclude]
    sources, used = [], 0
    for f in reversed(files):  # newest first within the budget
        text = f.extracted_text or ""
        if used + len(text) > MAX_SOURCE_CHARS:
            continue
        used += len(text)
        raw = _raw_path(f.id, f.filename)
        sources.insert(0, SourceDoc(
            filename=f.filename,
            mime_type=RAW_TYPES.get(Path(f.filename).suffix.lower(), f.mime_type),
            text=text,
            raw_path=str(raw) if raw.exists() else None,
        ))
    return sources


def _save_version(
    conv: Conversation,
    db: Session,
    summary: str,
    schema: Optional[PaperSchema] = None,
    doc_kind: str = "paperly",
    data: Optional[bytes] = None,
    title: Optional[str] = None,
) -> Tuple[Paper, PaperVersion]:
    """Add a version to the chat's document (creating it on first use) and make it current."""
    title = title or (schema.metadata.title if schema else "Document")
    paper = _latest_paper(conv.id, db)
    if not paper:
        paper = Paper(conversation_id=conv.id, title=title)
        db.add(paper)
        db.flush()
    else:
        paper.title = title

    last_number = db.query(func.max(PaperVersion.version_number)).filter(PaperVersion.paper_id == paper.id).scalar() or 0
    version = PaperVersion(
        id=str(uuid.uuid4()),
        paper_id=paper.id,
        version_number=last_number + 1,
        schema_json=(schema or documents.stub_schema(title)).model_dump_json(),
        change_summary=summary[:255],
        doc_kind=doc_kind,
    )
    if data is not None:
        version.file_name = documents.write_file(version.id, doc_kind, data)
    db.add(version)
    db.flush()
    paper.current_version_id = version.id
    paper.updated_at = datetime.now(timezone.utc)
    conv.title = title[:255]
    return paper, version


def _post(db: Session, conv_id: str, text: str, meta: dict) -> None:
    db.add(Message(conversation_id=conv_id, role="assistant", content=text, metadata_json=json.dumps(meta)))


def _describe(schema: PaperSchema) -> str:
    return f"{schema.total_question_count()} questions, {schema.metadata.total_marks:g} marks"


def _start_turn(conv: Conversation, user: User):
    """Run one assistant turn in the background. The reply (and any new version) is posted into the chat."""
    conv_id = conv.id

    async def work(job: jobs.Job):
        db = SessionLocal()
        try:
            conv_row = db.get(Conversation, conv_id)
            history = [{"role": m.role, "content": m.content} for m in conv_row.messages]
            opened = _open_filename(conv_row)
            sources = _sources(conv_id, db, exclude=opened)  # the open document is shown separately
            uploads = {f.filename: f.id for f in conv_row.uploaded_files}
            version = _current_version(conv_id, db)
            doc_kind, doc_text = documents.doc_context(version)
        finally:
            db.close()

        turn = await AIService.chat_turn(history, doc_kind, doc_text, sources)
        job.stage = {"edit_document": "edit", "edit_paperly": "edit"}.get(turn.action, turn.action)

        # Do the work (AI calls happen outside any DB session).
        new = None  # (summary, schema, kind, data, title, changes)
        if turn.action == "edit_document" and version is not None and doc_kind in ("docx", "pdf"):
            if not turn.operations:
                turn.action = "reply"
            else:
                original = documents.read_file(version)
                apply = doc_edit.apply_docx_ops if doc_kind == "docx" else doc_edit.apply_pdf_ops
                try:
                    outcome = apply(original, turn.operations)
                except doc_edit.DocEditError as e:
                    raise AIServiceError(str(e))
                changes = [{"before": c.before[:600], "after": c.after[:600]} for c in outcome.changes]
                schema_title = PaperSchema.model_validate_json(version.schema_json).metadata.title
                new = (turn.reply, None, doc_kind, outcome.data, schema_title, changes)
        elif turn.action == "edit_paperly" and doc_kind == "paperly":
            current = PaperSchema.model_validate_json(version.schema_json)
            schema, summary = await AIService.edit_paper(current, turn.instruction or history[-1]["content"], sources)
            new = (summary, schema, "paperly", None, None, [])
        elif turn.action == "generate":
            requirements = "\n".join(f"{h['role']}: {h['content']}" for h in history[-30:])
            if turn.instruction:
                requirements += f"\n\nFinal instruction: {turn.instruction}"
            schema = await AIService.generate_paper(requirements=requirements, sources=sources)
            new = ("Generated from your requirements", schema, "paperly", None, None, [])
        elif turn.action == "convert":
            target = None
            if doc_kind in ("docx", "pdf") and not turn.source_file:
                data = documents.read_file(version)
                raw = Path(settings.UPLOAD_DIR) / f"convert-{version.id}{documents.EXTENSIONS[doc_kind]}"
                raw.write_bytes(data)
                text = "\n".join(b.text for b in (doc_edit.docx_blocks(data) if doc_kind == "docx" else []))
                target = SourceDoc(filename=f"document{documents.EXTENSIONS[doc_kind]}", mime_type=documents.MIME[doc_kind],
                                   text=f"<untrusted_source_material>\n{text}\n</untrusted_source_material>",
                                   raw_path=str(raw) if doc_kind == "pdf" else None)
            elif sources:
                target = next((s for s in reversed(sources) if s.filename == turn.source_file), sources[-1])
            if target is None:
                turn.action = "reply"
            else:
                schema, summary = await AIService.import_document(target, turn.instruction)
                new = (summary, schema, "paperly", None, None, [])
        elif turn.action == "open_file" and turn.source_file in uploads:
            filename = turn.source_file
            kind = {".docx": "docx", ".pdf": "pdf"}.get(Path(filename).suffix.lower())
            raw = _raw_path(uploads[filename], filename)
            if kind is None or not raw.exists() or (kind == "pdf" and not doc_edit.pdf_supported()):
                turn.action = "reply"
            else:
                new = (f"Opened {filename}", None, kind, raw.read_bytes(), documents.title_from_filename(filename), [])
        elif turn.action != "reply":
            turn.action = "reply"  # nothing to act on

        db = SessionLocal()
        try:
            conv_row = db.get(Conversation, conv_id)
            if conv_row is None:  # chat deleted meanwhile
                return {"reply": turn.reply}
            result = {"reply": turn.reply, "action": turn.action}
            if new is None:
                _post(db, conv_id, turn.reply, {"action": "reply"})
            else:
                summary, schema, kind, data, title, changes = new
                paper, v = _save_version(conv_row, db, summary, schema=schema, doc_kind=kind, data=data, title=title)
                updated = turn.action in ("edit_document", "edit_paperly")
                # Remember which upload is open so the assistant doesn't also see it as "another file".
                keep_open = {"opened_file": opened} if (turn.action == "edit_document" and opened) else {}
                if turn.action == "open_file":
                    keep_open = {"opened_file": turn.source_file}
                text = turn.reply if turn.action in ("edit_document", "open_file") else (
                    f"{turn.reply}\n\n{summary}" if updated else
                    f"{turn.reply}\n\n'{schema.metadata.title}' is ready: {_describe(schema)}."
                )
                _post(db, conv_id, text, {
                    "action": "paper_updated" if updated else "paper_ready",
                    "paper_id": paper.id, "version": v.version_number, "changes": changes, **keep_open,
                })
                result.update(paper_id=paper.id, version=v.version_number)
            conv_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            return result
        finally:
            db.close()

    def on_error(message: str):
        db = SessionLocal()
        try:
            if db.get(Conversation, conv_id) is None:
                return
            _post(db, conv_id, f"I couldn't do that. {message}", {"action": "error"})
            db.commit()
        finally:
            db.close()

    return jobs.start_job("chat", user.id, work, on_error, conversation_id=conv_id)


@router.get("", response_model=List[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all conversations for the authenticated user, newest first."""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    paper_ids = dict(
        db.query(Paper.conversation_id, Paper.id)
        .filter(Paper.conversation_id.in_([c.id for c in convs]))
        .all()
    ) if convs else {}
    return [
        ConversationSummary(
            id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at,
            latest_paper_id=paper_ids.get(c.id),
        )
        for c in convs
    ]


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conv_in: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new chat."""
    conv = Conversation(user_id=current_user.id, title=(conv_in.title or "New Assessment")[:255])
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/{id}", response_model=ConversationDetail)
def get_conversation(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full conversation details including messages and the chat's document."""
    conv = _get_user_conversation(id, current_user, db)
    paper = _latest_paper(conv.id, db)
    job = jobs.running_job_for_conversation(conv.id)
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=conv.messages,
        latest_paper_id=paper.id if paper else None,
        active_job_id=job.id if job else None,
        active_job_kind=job.kind if job else None,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation along with its messages, uploads and documents."""
    conv = _get_user_conversation(id, current_user, db)
    for f in conv.uploaded_files:
        _raw_path(f.id, f.filename).unlink(missing_ok=True)
    for paper in conv.papers:
        for v in paper.versions:
            path = documents.file_path(v)
            if path:
                path.unlink(missing_ok=True)
    db.delete(conv)
    db.commit()


@router.post("/{id}/messages", response_model=MessageResponse)
async def post_message(
    id: str,
    msg_in: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a message. The assistant answers in the background: the response is the saved teacher message with
    metadata {"action": "working", "job_id"}; poll GET /api/v1/jobs/{job_id} (its "stage" says what's happening),
    then reload the conversation to get the reply (and any new document version).
    """
    conv = _get_user_conversation(id, current_user, db)
    if jobs.running_job_for_conversation(conv.id):
        raise HTTPException(status_code=409, detail="I'm still working on your last message. Please wait a moment.")

    user_msg = Message(conversation_id=conv.id, role="user", content=msg_in.content)
    db.add(user_msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    job = _start_turn(conv, current_user)
    user_msg.metadata_json = json.dumps({"action": "working", "kind": "chat", "job_id": job.id})
    db.commit()
    db.refresh(user_msg)
    return user_msg


@router.post("/{id}/upload", response_model=FileUploadResponse)
async def upload_source_material(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a file. Word (.docx) and PDF files become the chat's document (edited in place, formatting kept);
    photos, TXT/MD/CSV are reference material (e.g. notes to build a paper from, or a photo to rebuild).
    """
    conv = _get_user_conversation(id, current_user, db)

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.MAX_UPLOAD_MB} MB")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    filename = (file.filename or "uploaded_file")[:200]
    mime_type = file.content_type or "application/octet-stream"
    suffix = Path(filename).suffix.lower()
    is_image = mime_type.startswith("image/") or suffix in (".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif")
    doc_kind = "docx" if suffix == ".docx" else ("pdf" if suffix == ".pdf" or mime_type == "application/pdf" else None)

    try:
        extracted_safe_text, char_count = DocumentExtractionService.extract_text_from_bytes(
            filename=filename, content=content, mime_type=mime_type
        )
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file. Try a PDF, Word file or a photo.")

    file_id = str(uuid.uuid4())
    if is_image:
        if not settings.ai_enabled:
            raise HTTPException(status_code=422, detail="Reading photos needs the Gemini key on the server.")
        if not suffix:
            filename += ".jpg"
    elif char_count == 0 and doc_kind != "pdf":
        raise HTTPException(status_code=422, detail="No readable text found in this file.")
    # Keep every original: PDFs/photos are sent to Gemini as-is, and a Word/PDF can be opened later.
    _raw_path(file_id, filename).write_bytes(content)

    db.add(UploadedFile(
        id=file_id, conversation_id=conv.id, filename=filename, mime_type=mime_type,
        extracted_text=extracted_safe_text, file_size=len(content),
    ))

    if doc_kind == "pdf" and not doc_edit.pdf_supported():
        doc_kind = None  # server can't edit PDFs in place; keep it as reference material

    open_paper = _latest_paper(conv.id, db)
    if doc_kind and open_paper is not None:
        # A document is already open: the new file is something to read from, not a replacement.
        _post(db, conv.id,
              f"Got '{filename}'. I'll keep editing '{open_paper.title}' and can read '{filename}' myself, e.g. "
              f"\"replace chapter 10 with the chapter 14 questions from {filename}\". "
              f"Say \"edit {filename} instead\" if you want to work on that file.",
              {"action": "file_received", "filename": filename})
    elif doc_kind:
        title = documents.title_from_filename(filename)
        paper, version = _save_version(conv, db, f"Uploaded {filename}", doc_kind=doc_kind, data=content, title=title)
        pages = doc_edit.pdf_page_count(content) if doc_kind == "pdf" else None
        _post(db, conv.id,
              f"Opened '{filename}'" + (f" ({pages} page{'s' if pages != 1 else ''})" if pages else "") +
              ". I'll edit this exact document and keep its formatting. Ask me anything about it, or tell me "
              "what to change.",
              {"action": "paper_ready", "paper_id": paper.id, "version": version.version_number,
               "opened_file": filename})
    else:
        _post(db, conv.id,
              f"Got '{filename}'. " + (
                  "It's a photo, so I can't edit it in place, but I can rebuild it as an editable paper (the look "
                  "will change), or use it as reference. What would you like?" if is_image else
                  "I'll use it as reference material. What would you like me to do with it?"),
              {"action": "file_received", "filename": filename})
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    return FileUploadResponse(file_id=file_id, filename=filename, extracted_characters=char_count, status="ready")
