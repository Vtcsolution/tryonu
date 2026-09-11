"""Production RQ worker entrypoint.

    python -m app.workers.worker

Listens on the "tryon" and "ingestion" queues. Run as many replicas of this
as you need AI throughput — each is stateless and pulls the next job off
Redis. Requires REDIS_URL to be set (see app/core/config.py); this process
refuses to start against the in-process dev fallback since that only makes
sense inside the API process itself.
"""

from __future__ import annotations

import sys

from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging, logger

settings = get_settings()


def main() -> None:
    configure_logging(settings.DEBUG)

    if not settings.REDIS_URL:
        logger.error("worker_start_failed", reason="REDIS_URL is not set")
        print(
            "REDIS_URL is not configured — this worker process has nothing to "
            "listen to. Local dev runs jobs in-process inside the API server "
            "instead; set REDIS_URL to run a real worker.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    conn = Redis.from_url(settings.REDIS_URL)
    queues = [Queue("tryon", connection=conn), Queue("ingestion", connection=conn)]
    logger.info("worker_starting", queues=[q.name for q in queues])

    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
