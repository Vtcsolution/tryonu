"""Give up on a try-on that never started, and give the credits back.

A job sat at "Queued — waiting for a worker" for four minutes and would
have sat there forever: if no worker picks it up — the process is down,
crash-looping, or pointed at a different Redis — nothing in the system
ever changes its status, so the customer watches a spinner and their
credits stay reserved.

Checked when the client polls the job, which is exactly when someone is
waiting on it, so it needs no scheduler of its own.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.enums import JobStatus
from app.models.tryon import TryOnJob
from app.services import credit_service

# A render is 20-40s per item and can retry, so a long job is normal;
# never having started is not.
QUEUED_LIMIT = timedelta(minutes=5)
RUNNING_LIMIT = timedelta(minutes=20)


def _stuck_for(job: TryOnJob) -> timedelta | None:
    now = datetime.now(timezone.utc)
    if job.status == JobStatus.QUEUED:
        since = job.queued_at or job.created_at
        waited = now - _aware(since)
        return waited if waited > QUEUED_LIMIT else None
    if job.status == JobStatus.PROCESSING and job.started_at:
        running = now - _aware(job.started_at)
        return running if running > RUNNING_LIMIT else None
    return None


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


async def sweep_stuck_jobs() -> int:
    """Fail and refund every job that is never going to run.

    A sweeper rather than a check on the polling endpoint: that endpoint's
    session is the one a client is polling on, and touching the job there
    made the request hold a transaction long enough to block the worker —
    the rescue was causing the thing it was meant to rescue. A sweep also
    reaches jobs nobody is watching, which is exactly the case where a
    customer has closed the tab with their credits still reserved."""
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(TryOnJob).where(TryOnJob.status.in_((JobStatus.QUEUED, JobStatus.PROCESSING)))
        )
        stuck_jobs = [(job, _stuck_for(job)) for job in rows.scalars().all()]
        given_up = 0
        for job, stuck in stuck_jobs:
            if stuck is None:
                continue
            await _give_up(db, job, stuck)
            given_up += 1
        return given_up


async def _give_up(db, job: TryOnJob, stuck: timedelta) -> None:  # noqa: ANN001
    queued = job.status == JobStatus.QUEUED
    job.status = JobStatus.FAILED
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = (
        "Your render never started — no worker picked it up — and your credits were refunded. "
        "Please try again."
        if queued
        else "Your render took too long and was stopped; your credits were refunded. Please try again."
    )
    await credit_service.refund(
        db,
        user_id=job.user_id,
        amount=job.credit_cost,
        reference_type="tryon_job",
        reference_id=job.id,
        note="Automatic refund — the render never started" if queued else "Automatic refund — the render stalled",
    )
    await db.commit()
    logger.error(
        "tryon_job_given_up",
        job_id=job.id,
        was=("queued" if queued else "processing"),
        stuck_for_seconds=int(stuck.total_seconds()),
    )


SWEEP_EVERY_SECONDS = 60


async def sweep_forever() -> None:
    """Runs for the life of the API process."""
    import asyncio

    while True:
        await asyncio.sleep(SWEEP_EVERY_SECONDS)
        try:
            given_up = await sweep_stuck_jobs()
            if given_up:
                logger.warning("tryon_stuck_jobs_swept", count=given_up)
        except Exception as exc:  # noqa: BLE001 — a sweep must never end the loop
            logger.warning("tryon_sweep_failed", error=str(exc)[:200])
