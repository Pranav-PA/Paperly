import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.paper import Paper, PaperVersion
from app.schemas.paper_schema import (
    PaperSchema,
    PaperEditRequest,
    PaperEditResponse,
)
from app.services import jobs
from app.services.ai_service import AIService
from app.services.docx_service import DocxGenerationService
from app.services.pdf_service import PdfGenerationService

router = APIRouter(prefix="/papers", tags=["Papers"])


def _get_user_paper_and_active_version(paper_id: str, user_id: str, db: Session):
    paper = (
        db.query(Paper)
        .join(Conversation, Paper.conversation_id == Conversation.id)
        .filter(Paper.id == paper_id, Conversation.user_id == user_id)
        .first()
    )
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if not paper.current_version_id:
        active_version = (
            db.query(PaperVersion)
            .filter(PaperVersion.paper_id == paper.id)
            .order_by(PaperVersion.version_number.desc())
            .first()
        )
    else:
        active_version = db.query(PaperVersion).filter(PaperVersion.id == paper.current_version_id).first()

    if not active_version:
        raise HTTPException(status_code=404, detail="No active version found for this paper")

    return paper, active_version


@router.get("")
def list_papers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List the teacher's papers (latest active version summary), newest first."""
    rows = (
        db.query(Paper, PaperVersion)
        .join(Conversation, Paper.conversation_id == Conversation.id)
        .join(PaperVersion, PaperVersion.id == Paper.current_version_id)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Paper.updated_at.desc())
        .all()
    )
    result = []
    for paper, version in rows:
        schema = PaperSchema.model_validate_json(version.schema_json)
        result.append({
            "id": paper.id,
            "conversation_id": paper.conversation_id,
            "title": paper.title,
            "subject": schema.metadata.subject,
            "class_grade": schema.metadata.class_grade,
            "total_marks": schema.metadata.total_marks,
            "question_count": schema.total_question_count(),
            "version_number": version.version_number,
            "updated_at": paper.updated_at,
        })
    return result


@router.get("/{id}", response_model=PaperSchema)
def get_paper(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve the current active PaperSchema AST for the document editor."""
    _, active_version = _get_user_paper_and_active_version(id, current_user.id, db)
    schema_dict = json.loads(active_version.schema_json)
    return PaperSchema.model_validate(schema_dict)


@router.post("/{id}/edit", status_code=status.HTTP_202_ACCEPTED)
async def edit_paper_conversational(
    id: str,
    edit_req: PaperEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Apply a natural language edit to the paper in the background.
    Returns {"job_id"}; poll GET /api/v1/jobs/{job_id}. The finished job's result is a PaperEditResponse.
    """
    paper, active_version = _get_user_paper_and_active_version(id, current_user.id, db)
    if jobs.running_job_for_conversation(paper.conversation_id):
        raise HTTPException(status_code=409, detail="Another change is still in progress. Please wait a moment.")

    current_schema = PaperSchema.model_validate_json(active_version.schema_json)
    paper_id, conv_id, instruction = paper.id, paper.conversation_id, edit_req.instruction

    async def work():
        updated_schema, change_summary = await AIService.edit_paper(current_schema=current_schema, instruction=instruction)
        job_db = SessionLocal()
        try:
            paper_row = job_db.get(Paper, paper_id)
            last_number = job_db.query(func.max(PaperVersion.version_number)).filter(PaperVersion.paper_id == paper_id).scalar() or 0
            new_version = PaperVersion(
                paper_id=paper_id,
                version_number=last_number + 1,
                schema_json=updated_schema.model_dump_json(),
                change_summary=change_summary[:255],
            )
            job_db.add(new_version)
            job_db.flush()
            paper_row.current_version_id = new_version.id
            paper_row.title = updated_schema.metadata.title
            paper_row.conversation.updated_at = datetime.now(timezone.utc)
            job_db.add(Message(conversation_id=conv_id, role="user", content=f"Edit: {instruction}"))
            job_db.add(Message(
                conversation_id=conv_id,
                role="assistant",
                content=f"Updated the paper (version {new_version.version_number}): {change_summary}",
            ))
            job_db.commit()
            return PaperEditResponse(
                paper_id=paper_id,
                version_number=new_version.version_number,
                change_summary=change_summary,
                paper_schema=updated_schema,
            ).model_dump(mode="json")
        finally:
            job_db.close()

    job = jobs.start_job("edit", current_user.id, work, on_error=lambda _msg: None, conversation_id=conv_id)
    return {"job_id": job.id}


@router.get("/{id}/export/{format}")
def export_paper(
    id: str,
    format: str,
    include_answers: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export the question paper as a formatted DOCX or PDF file."""
    paper, active_version = _get_user_paper_and_active_version(id, current_user.id, db)
    schema = PaperSchema.model_validate_json(active_version.schema_json)

    clean_title = "".join(c for c in paper.title if c.isalnum() or c in (" ", "-", "_")).strip()
    filename_base = clean_title.replace(" ", "_") or "Question_Paper"

    if format.lower() == "docx":
        docx_bytes = DocxGenerationService.generate_question_paper_docx(schema, include_solutions=include_answers)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'}
        )
    elif format.lower() == "pdf":
        pdf_bytes = PdfGenerationService.generate_pdf_bytes(schema, include_solutions=include_answers)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf" if pdf_bytes.startswith(b"%PDF") else "text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'}
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format. Choose 'pdf' or 'docx'.")


@router.get("/{id}/solutions/{format}")
def export_solutions(
    id: str,
    format: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export the Answer Key and Detailed Solutions as a separate document."""
    paper, active_version = _get_user_paper_and_active_version(id, current_user.id, db)
    schema = PaperSchema.model_validate_json(active_version.schema_json)

    clean_title = "".join(c for c in paper.title if c.isalnum() or c in (" ", "-", "_")).strip()
    filename_base = (clean_title.replace(" ", "_") or "Question_Paper") + "_Solutions"

    if format.lower() == "docx":
        docx_bytes = DocxGenerationService.generate_solutions_docx(schema)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'}
        )
    elif format.lower() == "pdf":
        pdf_bytes = PdfGenerationService.generate_pdf_bytes(schema, solutions_only=True)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf" if pdf_bytes.startswith(b"%PDF") else "text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'}
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format. Choose 'pdf' or 'docx'.")


@router.get("/{id}/versions")
def get_paper_versions(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full version history for undo/revert tracking."""
    paper, _ = _get_user_paper_and_active_version(id, current_user.id, db)
    versions = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper.id)
        .order_by(PaperVersion.version_number.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "change_summary": v.change_summary,
            "created_at": v.created_at,
            "is_active": (v.id == paper.current_version_id)
        }
        for v in versions
    ]


@router.post("/{id}/revert/{version_number}")
def revert_paper_version(
    id: str,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reverts the paper's active state to a specified previous version number."""
    paper, _ = _get_user_paper_and_active_version(id, current_user.id, db)
    target_version = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper.id, PaperVersion.version_number == version_number)
        .first()
    )
    if not target_version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found for this paper")

    paper.current_version_id = target_version.id
    db.commit()

    schema_dict = json.loads(target_version.schema_json)
    return {
        "message": f"Successfully reverted to version {version_number}",
        "version_number": version_number,
        "paper_schema": schema_dict
    }
