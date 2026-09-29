"""
Tiny in-memory background job registry.

Paper generation and edits can take longer than the ~100 s a Cloudflare tunnel keeps a request open,
so those run as background tasks and the app polls GET /api/v1/jobs/{id}. The server runs a single
uvicorn worker, so an in-process dict is enough; jobs are simply forgotten on restart.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_JOB_TTL_SECONDS = 60 * 60


@dataclass
class Job:
    id: str
    user_id: str
    kind: str
    conversation_id: Optional[str] = None
    status: str = "running"  # running | done | error
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


_jobs: Dict[str, Job] = {}
_tasks: set = set()


def _prune() -> None:
    cutoff = time.time() - _JOB_TTL_SECONDS
    for job_id in [j.id for j in _jobs.values() if j.created_at < cutoff and j.status != "running"]:
        _jobs.pop(job_id, None)


def start_job(
    kind: str,
    user_id: str,
    work: Callable[[], Awaitable[Dict[str, Any]]],
    on_error: Callable[[str], None],
    conversation_id: Optional[str] = None,
) -> Job:
    """Run `work` in the background. `on_error` receives a teacher-friendly message on failure."""
    _prune()
    job = Job(id=str(uuid.uuid4()), user_id=user_id, kind=kind, conversation_id=conversation_id)
    _jobs[job.id] = job

    async def runner():
        try:
            job.result = await work()
            job.status = "done"
        except Exception as e:  # noqa: BLE001 - surface every failure to the app
            from app.services.ai_service import AIServiceError
            message = str(e) if isinstance(e, AIServiceError) else "Something went wrong while writing the paper."
            if not isinstance(e, AIServiceError):
                logger.error("Background job %s failed", job.id, exc_info=True)
            job.error = message
            job.status = "error"
            try:
                on_error(message)
            except Exception:
                logger.error("Job error handler failed", exc_info=True)

    task = asyncio.create_task(runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


def get_job(job_id: str, user_id: str) -> Optional[Job]:
    job = _jobs.get(job_id)
    return job if job and job.user_id == user_id else None


def running_job_for_conversation(conversation_id: str) -> Optional[Job]:
    for job in _jobs.values():
        if job.conversation_id == conversation_id and job.status == "running":
            return job
    return None
