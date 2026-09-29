import io
import json
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.paper import Paper, PaperVersion
from app.schemas.paper_schema import (
    PaperSchema,
    PaperEditRequest,
    PaperEditResponse,
)
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


@router.post("/{id}/edit", response_model=PaperEditResponse)
async def edit_paper_conversational(
    id: str,
    edit_req: PaperEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Apply a natural language modification instruction to the paper.
    Produces an updated PaperSchema and records a new version for undo capability.
    """
    paper, active_version = _get_user_paper_and_active_version(id, current_user.id, db)
    current_schema = PaperSchema.model_validate_json(active_version.schema_json)

    # Invoke Editor Agent
    updated_schema, change_summary = await AIService.edit_paper(
        current_schema=current_schema,
        instruction=edit_req.instruction
    )

    # Next version number
    latest_ver = (
        db.query(PaperVersion)
        .filter(PaperVersion.paper_id == paper.id)
        .order_by(PaperVersion.version_number.desc())
        .first()
    )
    new_version_num = (latest_ver.version_number + 1) if latest_ver else 1

    new_version = PaperVersion(
        paper_id=paper.id,
        version_number=new_version_num,
        schema_json=updated_schema.model_dump_json(),
        change_summary=change_summary
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)

    paper.current_version_id = new_version.id
    db.commit()

    # Also log modification in conversation history
    edit_log_msg = Message(
        conversation_id=paper.conversation_id,
        role="assistant",
        content=f"Applied modification: {change_summary}"
    )
    db.add(edit_log_msg)
    db.commit()

    return PaperEditResponse(
        paper_id=paper.id,
        version_number=new_version.version_number,
        change_summary=change_summary,
        paper_schema=updated_schema
    )


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
        docx_bytes = DocxGenerationService.generate_question_paper_docx(schema)
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
        pdf_bytes = PdfGenerationService.generate_pdf_bytes(schema, include_solutions=True)
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
