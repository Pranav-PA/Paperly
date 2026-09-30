from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.models.user import User
from app.services import jobs

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}")
def get_job_status(job_id: str, current_user: User = Depends(get_current_user)):
    """Poll a background paper generation/edit job: status is running, done or error."""
    job = jobs.get_job(job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found (the server may have restarted)")
    return {"id": job.id, "kind": job.kind, "status": job.status, "stage": job.stage, "result": job.result, "error": job.error}
