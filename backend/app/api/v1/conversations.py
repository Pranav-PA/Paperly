import json
from datetime import datetime, timezone
from typing import List, Optional
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
from app.services.ai_service import AIService, AIServiceError
from app.services.extract_service import DocumentExtractionService

router = APIRouter(prefix="/conversations", tags=["Conversations"])

# Keep prompts bounded on a low-memory phone: total characters of uploaded material sent to the model.
MAX_SOURCE_CHARS = 200_000


def _get_user_conversation(conv_id: str, user: User, db: Session) -> Conversation:
    conv = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.user_id == user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _latest_paper_id(conv_id: str, db: Session) -> Optional[str]:
    paper = db.query(Paper).filter(Paper.conversation_id == conv_id).order_by(Paper.created_at.desc()).first()
    return paper.id if paper else None


def _source_texts(conv_id: str, db: Session) -> List[str]:
    files = db.query(UploadedFile).filter(UploadedFile.conversation_id == conv_id).order_by(UploadedFile.created_at).all()
    texts, used = [], 0
    for f in files:
        if f.extracted_text and used + len(f.extracted_text) <= MAX_SOURCE_CHARS:
            texts.append(f.extracted_text)
            used += len(f.extracted_text)
    return texts


def _save_generated_paper(conv: Conversation, paper_schema: PaperSchema, db: Session) -> Paper:
    """Create the paper on first generation; later generations become new versions of it."""
    paper = db.query(Paper).filter(Paper.conversation_id == conv.id).first()
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
        change_summary="Generated from requirements" if last_number == 0 else "Regenerated from updated requirements",
    )
    db.add(version)
    db.flush()
    paper.current_version_id = version.id
    conv.title = paper_schema.metadata.title
    return paper


def _generated_reply(paper_schema: PaperSchema) -> str:
    return (
        f"Your paper '{paper_schema.metadata.title}' is ready: "
        f"{paper_schema.total_question_count()} questions, {paper_schema.metadata.total_marks:g} marks. "
        "Open it to review, ask me for changes, or export it as PDF/DOCX."
    )


def _start_generation_job(conv: Conversation, user: User, history: List[dict], sources: List[str]):
    """Generate the paper in the background; the app polls the job and then re-syncs the conversation."""
    conv_id = conv.id
    requirements = "\n".join(f"{h['role']}: {h['content']}" for h in history)

    async def work():
        paper_schema = await AIService.generate_paper(requirements=requirements, source_materials=sources)
        db = SessionLocal()
        try:
            conv_row = db.get(Conversation, conv_id)
            if conv_row is None:  # deleted while generating
                return {"paper_id": None}
            paper = _save_generated_paper(conv_row, paper_schema, db)
            db.add(Message(
                conversation_id=conv_id,
                role="assistant",
                content=_generated_reply(paper_schema),
                metadata_json=json.dumps({"action": "paper_ready", "paper_id": paper.id}),
            ))
            conv_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            return {"paper_id": paper.id}
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
                content=f"I couldn't finish the paper. {message} Send \"generate\" to try again.",
                metadata_json=json.dumps({"action": "error"}),
            ))
            db.commit()
        finally:
            db.close()

    return jobs.start_job("generate", user.id, work, on_error, conversation_id=conv_id)


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
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=conv.messages,
        latest_paper_id=_latest_paper_id(conv.id, db),
        active_job_id=job.id if (job := jobs.running_job_for_conversation(conv.id)) else None,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation along with its messages, uploads and papers."""
    conv = _get_user_conversation(id, current_user, db)
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
    Post a teacher message and receive the assistant's reply.
    When requirements are complete, paper generation starts in the background: the reply's
    metadata has action "generating" and a job_id to poll at GET /api/v1/jobs/{job_id}.
    """
    conv = _get_user_conversation(id, current_user, db)
    if jobs.running_job_for_conversation(conv.id):
        raise HTTPException(status_code=409, detail="Your paper is still being written. Please wait a moment.")

    history = [{"role": m.role, "content": m.content} for m in conv.messages]
    history.append({"role": "user", "content": msg_in.content})
    sources = _source_texts(conv.id, db)

    try:
        reply, action, meta = await AIService.process_chat(history, source_materials=sources)
    except AIServiceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    metadata = {"action": action, "orchestrator_meta": meta}
    if action == "ready_to_generate":
        job = _start_generation_job(conv, current_user, history, sources)
        metadata.update(action="generating", job_id=job.id)
        reply = f"{reply}\n\nWriting your paper now. This usually takes 30-90 seconds."

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
    """Upload PDF, DOCX, TXT, MD or CSV notes/syllabus as reference material for generation."""
    conv = _get_user_conversation(id, current_user, db)

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.MAX_UPLOAD_MB} MB")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    filename = (file.filename or "uploaded_file")[:200]
    mime_type = file.content_type or "application/octet-stream"

    try:
        extracted_safe_text, char_count = DocumentExtractionService.extract_text_from_bytes(
            filename=filename,
            content=content,
            mime_type=mime_type
        )
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file. Try a PDF, DOCX or TXT file.")
    if char_count == 0:
        raise HTTPException(status_code=422, detail="No readable text found (scanned PDFs without a text layer are not supported).")

    uploaded = UploadedFile(
        conversation_id=conv.id,
        filename=filename,
        mime_type=mime_type,
        extracted_text=extracted_safe_text,
        file_size=len(content)
    )
    db.add(uploaded)
    db.add(Message(
        conversation_id=conv.id,
        role="assistant",
        content=f"Got '{filename}' ({char_count:,} characters). I'll use it as reference material for your paper."
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
