import json
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
from app.services import jobs
from app.services.ai_service import AIService, AIServiceError, SourceDoc
from app.services.extract_service import DocumentExtractionService

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

JOB_MESSAGES = {
    "generate": "Writing your paper now. This usually takes 30-90 seconds.",
    "import": "Reading your document and applying the change. This usually takes 30-90 seconds.",
    "edit": "",
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


def _current_schema(conv_id: str, db: Session) -> Optional[PaperSchema]:
    paper = _latest_paper(conv_id, db)
    if not paper or not paper.current_version_id:
        return None
    version = db.get(PaperVersion, paper.current_version_id)
    return PaperSchema.model_validate_json(version.schema_json) if version else None


def _raw_path(file_id: str, filename: str) -> Path:
    return Path(settings.UPLOAD_DIR) / f"{file_id}{Path(filename).suffix.lower()}"


def _sources(conv_id: str, db: Session) -> List[SourceDoc]:
    files = db.query(UploadedFile).filter(UploadedFile.conversation_id == conv_id).order_by(UploadedFile.created_at).all()
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


def _save_version(conv: Conversation, paper_schema: PaperSchema, summary: str, db: Session) -> Tuple[Paper, int]:
    """Create the paper on first use; every later change becomes a new version of it."""
    paper = _latest_paper(conv.id, db)
    if not paper:
        paper = Paper(conversation_id=conv.id, title=paper_schema.metadata.title)
        db.add(paper)
        db.flush()
    else:
        paper.title = paper_schema.metadata.title

    last_number = db.query(func.max(PaperVersion.version_number)).filter(PaperVersion.paper_id == paper.id).scalar() or 0
    version = PaperVersion(
        paper_id=paper.id,
        version_number=last_number + 1,
        schema_json=paper_schema.model_dump_json(),
        change_summary=summary[:255],
    )
    db.add(version)
    db.flush()
    paper.current_version_id = version.id
    paper.updated_at = datetime.now(timezone.utc)
    conv.title = paper_schema.metadata.title[:255]
    return paper, version.version_number


def _describe(paper_schema: PaperSchema) -> str:
    return f"{paper_schema.total_question_count()} questions, {paper_schema.metadata.total_marks:g} marks"


def _start_paper_job(kind: str, conv: Conversation, user: User, instruction: str, history: List[dict],
                     sources: List[SourceDoc], source_file: Optional[str], current: Optional[PaperSchema]):
    """Run generate/import/edit in the background; the result is posted into the chat as a message."""
    conv_id = conv.id

    async def work():
        if kind == "edit" and current is not None:
            schema, summary = await AIService.edit_paper(current, instruction, sources)
        elif kind == "import":
            target = next((s for s in reversed(sources) if s.filename == source_file), sources[-1])
            schema, summary = await AIService.import_document(target, instruction)
        else:
            requirements = "\n".join(f"{h['role']}: {h['content']}" for h in history[-30:])
            if instruction:
                requirements += f"\n\nFinal instruction: {instruction}"
            schema = await AIService.generate_paper(requirements=requirements, sources=sources)
            summary = "Generated from your requirements"

        db = SessionLocal()
        try:
            conv_row = db.get(Conversation, conv_id)
            if conv_row is None:  # deleted while working
                return {"paper_id": None}
            paper, version_number = _save_version(conv_row, schema, summary, db)
            if kind == "edit":
                action, text = "paper_updated", f"Done: {summary} (version {version_number})"
            elif kind == "import":
                action, text = "paper_ready", f"{summary}\n\n'{schema.metadata.title}' is ready: {_describe(schema)}. Open it, or tell me what to change next."
            else:
                action, text = "paper_ready", (
                    f"Your paper '{schema.metadata.title}' is ready: {_describe(schema)}. "
                    "Open it to review, ask me for changes, or export it as PDF/DOCX."
                )
            db.add(Message(
                conversation_id=conv_id,
                role="assistant",
                content=text,
                metadata_json=json.dumps({"action": action, "paper_id": paper.id, "version": version_number}),
            ))
            conv_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            return {"paper_id": paper.id, "version": version_number, "summary": summary}
        finally:
            db.close()

    def on_error(message: str):
        db = SessionLocal()
        try:
            if db.get(Conversation, conv_id) is None:
                return
            db.add(Message(
                conversation_id=conv_id,
                role="assistant",
                content=f"I couldn't finish that. {message} Send your message again to retry.",
                metadata_json=json.dumps({"action": "error"}),
            ))
            db.commit()
        finally:
            db.close()

    return jobs.start_job(kind, user.id, work, on_error, conversation_id=conv_id)


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
    """Start a new paper creation conversation thread."""
    conv = Conversation(
        user_id=current_user.id,
        title=(conv_in.title or "New Assessment")[:255]
    )
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
    """Retrieve full conversation details including messages and generated paper."""
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
    """Delete a conversation along with its messages, uploads and papers."""
    conv = _get_user_conversation(id, current_user, db)
    for f in conv.uploaded_files:
        _raw_path(f.id, f.filename).unlink(missing_ok=True)
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
    Post a teacher message. Paperly replies directly (clarifying question / chat), or starts a background job
    that generates, imports or edits the paper: then the reply's metadata has action "working", the job kind
    and a job_id to poll at GET /api/v1/jobs/{job_id}. The finished job posts its own message into the chat.
    """
    conv = _get_user_conversation(id, current_user, db)
    if jobs.running_job_for_conversation(conv.id):
        raise HTTPException(status_code=409, detail="I'm still working on your last request. Please wait a moment.")

    history = [{"role": m.role, "content": m.content} for m in conv.messages]
    history.append({"role": "user", "content": msg_in.content})
    sources = _sources(conv.id, db)
    current = _current_schema(conv.id, db)

    try:
        decision = await AIService.decide(history, current, sources)
    except AIServiceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    reply = decision.response_message
    metadata = {"action": decision.action, "orchestrator_meta": decision.model_dump()}
    if decision.action in ("generate", "import", "edit"):
        job = _start_paper_job(decision.action, conv, current_user, decision.instruction or msg_in.content,
                               history, sources, decision.source_file, current)
        metadata.update(action="working", kind=decision.action, job_id=job.id)
        if JOB_MESSAGES[decision.action]:
            reply = f"{reply}\n\n{JOB_MESSAGES[decision.action]}"

    db.add(Message(conversation_id=conv.id, role="user", content=msg_in.content))
    assistant_msg = Message(
        conversation_id=conv.id, role="assistant", content=reply, metadata_json=json.dumps(metadata)
    )
    db.add(assistant_msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


@router.post("/{id}/upload", response_model=FileUploadResponse)
async def upload_source_material(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a paper to edit, or notes/syllabus to build from: PDF, DOCX, TXT, MD, CSV or a photo."""
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
    is_raw = suffix in RAW_TYPES or mime_type.startswith("image/")

    try:
        extracted_safe_text, char_count = DocumentExtractionService.extract_text_from_bytes(
            filename=filename,
            content=content,
            mime_type=mime_type
        )
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file. Try a PDF, DOCX, TXT or a photo.")
    if char_count == 0 and not (is_raw and settings.ai_enabled):
        raise HTTPException(status_code=422, detail="No readable text found in this file.")

    file_id = str(uuid.uuid4())
    if is_raw:
        if not suffix:
            filename += ".jpg"
        _raw_path(file_id, filename).write_bytes(content)

    uploaded = UploadedFile(
        id=file_id,
        conversation_id=conv.id,
        filename=filename,
        mime_type=mime_type,
        extracted_text=extracted_safe_text,
        file_size=len(content)
    )
    db.add(uploaded)
    has_paper = _latest_paper(conv.id, db) is not None
    db.add(Message(
        conversation_id=conv.id,
        role="assistant",
        content=(
            f"Got '{filename}'. What should I do with it? For example: "
            + ('"replace my paper with this one", "add its questions to my paper"'
               if has_paper else
               '"change the last question to …", "make it two columns", or "create a new paper from these notes"')
            + "."
        ),
        metadata_json=json.dumps({"action": "file_received", "filename": filename}),
    ))
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(uploaded)

    return FileUploadResponse(
        file_id=uploaded.id,
        filename=uploaded.filename,
        extracted_characters=char_count,
        status="ready"
    )
