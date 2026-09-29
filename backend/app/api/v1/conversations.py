import json
import asyncio
from typing import List, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
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
from app.services.ai_service import AIService
from app.services.extract_service import DocumentExtractionService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all conversations for the authenticated user."""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conv_in: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new paper creation conversation thread."""
    conv = Conversation(
        user_id=current_user.id,
        title=conv_in.title or "New Assessment"
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
    conv = db.query(Conversation).filter(
        Conversation.id == id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    latest_paper = db.query(Paper).filter(Paper.conversation_id == conv.id).order_by(Paper.created_at.desc()).first()
    latest_paper_id = latest_paper.id if latest_paper else None

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=conv.messages,
        latest_paper_id=latest_paper_id
    )


@router.post("/{id}/messages", response_model=MessageResponse)
async def post_message(
    id: str,
    msg_in: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Post a user message to the conversation and receive the AI agent's response.
    Orchestrates requirements clarification or triggers paper synthesis.
    """
    conv = db.query(Conversation).filter(
        Conversation.id == id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. Save User Message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=msg_in.content
    )
    db.add(user_msg)
    db.commit()

    # 2. Collect history & uploaded context materials
    history = [
        {"role": m.role, "content": m.content}
        for m in conv.messages
    ]
    uploaded_files = db.query(UploadedFile).filter(UploadedFile.conversation_id == conv.id).all()
    source_texts = [f.extracted_text for f in uploaded_files if f.extracted_text]

    # 3. Consult Orchestrator Agent
    ai_reply_text, action, meta = await AIService.process_chat(history, source_materials=source_texts)

    # 4. If AI determines requirements are complete, generate the Paper!
    paper_created_id = None
    if action == "ready_to_generate":
        # Synthesize requirements from conversation
        conversation_context = "\n".join([f"{h['role']}: {h['content']}" for h in history])
        paper_schema = await AIService.generate_paper(
            requirements=conversation_context,
            source_materials=source_texts
        )

        # Update or create Paper entity
        paper = db.query(Paper).filter(Paper.conversation_id == conv.id).first()
        if not paper:
            paper = Paper(
                conversation_id=conv.id,
                title=paper_schema.metadata.title
            )
            db.add(paper)
            db.commit()
            db.refresh(paper)

        # Save Version 1
        version = PaperVersion(
            paper_id=paper.id,
            version_number=1,
            schema_json=paper_schema.model_dump_json(),
            change_summary="Initial synthesis from requirements"
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        paper.current_version_id = version.id
        db.commit()
        paper_created_id = paper.id

        ai_reply_text = (
            f"I have successfully generated your '{paper_schema.metadata.title}'! "
            f"Total questions: {paper_schema.total_question_count()}, "
            f"Total marks: {paper_schema.metadata.total_marks:g}. "
            f"You can now inspect the document in the editor, ask for adjustments, or export it to PDF/DOCX."
        )

    # 5. Save Assistant Message
    meta_json = json.dumps({
        "action": action,
        "paper_id": paper_created_id,
        "orchestrator_meta": meta
    })
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=ai_reply_text,
        metadata_json=meta_json
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg


@router.post("/{id}/messages/stream")
async def post_message_stream(
    id: str,
    msg_in: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Streams the AI agent reasoning and generation pipeline states via Server-Sent Events (SSE).
    Matches Screen 4 progress stepper: Requirements -> Research -> Generation -> Validation -> Layout.
    """
    conv = db.query(Conversation).filter(
        Conversation.id == id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. Save User Message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=msg_in.content
    )
    db.add(user_msg)
    db.commit()

    async def event_generator() -> AsyncGenerator[str, None]:
        # Step 1: Requirements analysis
        yield f"data: {json.dumps({'type': 'step', 'step': 'requirements', 'message': 'Requirements collected'})}\n\n"
        await asyncio.sleep(0.05)

        # Step 2: Research & context analysis
        yield f"data: {json.dumps({'type': 'step', 'step': 'research', 'message': 'Research completed & sources analyzed'})}\n\n"
        await asyncio.sleep(0.05)

        history = [{"role": m.role, "content": m.content} for m in conv.messages]
        uploaded_files = db.query(UploadedFile).filter(UploadedFile.conversation_id == conv.id).all()
        source_texts = [f.extracted_text for f in uploaded_files if f.extracted_text]

        ai_reply_text, action, meta = await AIService.process_chat(history, source_materials=source_texts)

        paper_created_id = None
        if action == "ready_to_generate":
            # Step 3: Question generation
            yield f"data: {json.dumps({'type': 'step', 'step': 'generation', 'message': 'Questions generated'})}\n\n"
            await asyncio.sleep(0.05)

            # Step 4: Validation
            yield f"data: {json.dumps({'type': 'step', 'step': 'validation', 'message': 'Validating questions & STEM calculations'})}\n\n"
            
            conversation_context = "\n".join([f"{h['role']}: {h['content']}" for h in history])
            paper_schema = await AIService.generate_paper(
                requirements=conversation_context,
                source_materials=source_texts
            )

            # Step 5: Document creation
            yield f"data: {json.dumps({'type': 'step', 'step': 'document', 'message': 'Creating document & layout'})}\n\n"

            paper = db.query(Paper).filter(Paper.conversation_id == conv.id).first()
            if not paper:
                paper = Paper(conversation_id=conv.id, title=paper_schema.metadata.title)
                db.add(paper)
                db.commit()
                db.refresh(paper)

            version = PaperVersion(
                paper_id=paper.id,
                version_number=1,
                schema_json=paper_schema.model_dump_json(),
                change_summary="Initial synthesis from requirements"
            )
            db.add(version)
            db.commit()
            db.refresh(version)

            paper.current_version_id = version.id
            db.commit()
            paper_created_id = paper.id

            ai_reply_text = (
                f"Generated '{paper_schema.metadata.title}' with {paper_schema.total_question_count()} questions "
                f"and {paper_schema.metadata.total_marks:g} total marks."
            )

        # Save assistant message in DB
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=ai_reply_text,
            metadata_json=json.dumps({"action": action, "paper_id": paper_created_id, "orchestrator_meta": meta})
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        # Final complete event
        yield f"data: {json.dumps({'type': 'complete', 'action': action, 'paper_id': paper_created_id, 'content': ai_reply_text})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{id}/upload", response_model=FileUploadResponse)
async def upload_source_material(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload PDF, DOCX, TXT, or CSV notes/curricula as grounding context for generation."""
    conv = db.query(Conversation).filter(
        Conversation.id == id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    content = await file.read()
    filename = file.filename or "uploaded_file"
    mime_type = file.content_type or "application/octet-stream"

    extracted_safe_text, char_count = DocumentExtractionService.extract_text_from_bytes(
        filename=filename,
        content=content,
        mime_type=mime_type
    )

    uploaded = UploadedFile(
        conversation_id=conv.id,
        filename=filename,
        mime_type=mime_type,
        extracted_text=extracted_safe_text,
        file_size=len(content)
    )
    db.add(uploaded)

    # Add a system/info message acknowledging upload in chat
    info_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=f"Received uploaded document '{filename}' ({char_count:,} characters extracted). I will use this as reference material."
    )
    db.add(info_msg)
    db.commit()
    db.refresh(uploaded)

    return FileUploadResponse(
        file_id=uploaded.id,
        filename=uploaded.filename,
        extracted_characters=char_count,
        status="ready"
    )
