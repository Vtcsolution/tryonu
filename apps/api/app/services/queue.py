"""Background job queue abstraction.

API -> queue.enqueue_tryon_job(job_id) -> [Redis/RQ worker process OR, in
local dev, an in-process asyncio task] -> app.workers.tasks.tryon_tasks

The HTTP request that creates a TryOnJob returns immediately with
status="queued" either way — it never waits on AI generation. Swapping
REDIS_URL in/out is the *only* thing that changes which path runs; the
worker task code is identical.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

_redis_conn = None


def _get_rq_queue(name: str):  # noqa: ANN201
    global _redis_conn
    from redis import Redis
    from rq import Queue

    if _redis_conn is None:
        _redis_conn = Redis.from_url(settings.REDIS_URL)
    return Queue(name, connection=_redis_conn)


_inprocess_tasks: set[asyncio.Task] = set()


def queue_state() -> dict:
    """How many renders are waiting, and how many workers are there to
    take them.

    A job sat "Queued — waiting for a worker" for 76 seconds and looked
    like a slow render when it had not started at all: one worker takes
    one job at a time, so a second try-on waits for the first to finish.
    Nothing outside the box could tell the two apart, so /health says it."""
    if not settings.REDIS_URL:
        return {"mode": "in-process", "running": len([t for t in _inprocess_tasks if not t.done()])}
    try:
        from rq import Worker

        queue = _get_rq_queue("tryon")
        workers = Worker.all(queue=queue)
        return {
            "mode": "redis",
            "waiting": queue.count,
            "workers": len(workers),
            "busy": len([w for w in workers if w.get_state() == "busy"]),
        }
    except Exception as exc:  # noqa: BLE001 — a health check never fails on this
        return {"mode": "redis", "error": str(exc)[:120]}


def enqueue_tryon_job(job_id: str) -> None:
    if settings.REDIS_URL:
        queue = _get_rq_queue("tryon")
        queue.enqueue(
            "app.workers.tasks.tryon_tasks.run_tryon_job",
            job_id,
            job_timeout=1200,  # several items x (render ~45s + inspection), plus retries
            retry=None,
        )
        logger.info("job_enqueued_rq", job_id=job_id, queue="tryon")
        return

    # Dev fallback: no Redis running. Run the exact same async task body as
    # a background task on this process's event loop.
    from app.workers.tasks.tryon_tasks import run_tryon_job_async

    logger.info("job_enqueued_inprocess", job_id=job_id)
    task = asyncio.create_task(run_tryon_job_async(job_id))
    # Keep a reference until it finishes: asyncio only holds a weak one, so an
    # unreferenced task can be garbage-collected mid-render (and in tests, a
    # job abandoned when the loop closes could leave its transaction holding
    # the SQLite database against the next test).
    _inprocess_tasks.add(task)
    task.add_done_callback(_inprocess_tasks.discard)
    task.add_done_callback(_log_inprocess_result)


def _log_inprocess_result(task: asyncio.Task) -> None:
    exc = task.exception() if task.done() and not task.cancelled() else None
    if exc:
        logger.error("inprocess_job_task_failed", error=str(exc))


def enqueue_product_sync() -> None:
    if settings.REDIS_URL:
        queue = _get_rq_queue("ingestion")
        queue.enqueue("app.workers.tasks.ingestion_tasks.run_product_sync", job_timeout=600)
        return

    from app.workers.tasks.ingestion_tasks import run_product_sync_async

    asyncio.create_task(run_product_sync_async())
