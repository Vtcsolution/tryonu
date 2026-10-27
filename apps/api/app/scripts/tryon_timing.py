"""How long the last try-ons took, and where the time went. Read-only.

    python -m app.scripts.tryon_timing            # the last 10 try-ons
    python -m app.scripts.tryon_timing --recent 25

For each try-on: how long it waited for the worker, how long it ran, and (for
try-ons drawn after this script was added) each stage: getting the products,
preparing the look board, FASHN drawing it, checking the result. Never prints
secrets or photos.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.runtime_settings import build_settings, load_overrides
from app.db.session import AsyncSessionLocal
from app.models.tryon import TryOnJob
from app.services.queue import queue_state

_STAGES = {
    "products": "products",
    "describe": "details",
    "board": "board",
    "draw": "drawing",
    "check": "check",
}


def _aware(moment: datetime | None) -> datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _secs(start: datetime | None, end: datetime | None) -> str:
    start, end = _aware(start), _aware(end)
    if start is None or end is None:
        return "-"
    s = int((end - start).total_seconds())
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recent", type=int, default=10)
    args = parser.parse_args()

    overrides, _ = await load_overrides()
    s = build_settings(overrides)
    print(
        f"Engine: {s.VIRTUAL_TRYON_PROVIDER} / {s.TRYON_ENGINE_MODE} / looks: {s.TRYON_MULTI_ENGINE}; "
        f"FASHN {s.FASHN_MODEL} {s.FASHN_RESOLUTION} {s.FASHN_GENERATION_MODE}; "
        f"vision check {'on' if s.TRYON_DIRECT_VLM_QC else 'off'}"
    )
    print(f"Worker: {queue_state()}\n")

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        jobs = (
            await db.execute(
                select(TryOnJob)
                .options(selectinload(TryOnJob.result))
                .order_by(TryOnJob.created_at.desc())
                .limit(args.recent)
            )
        ).scalars().all()
        for job in jobs:
            products = len(job.steps or []) or 1
            end = job.completed_at or (now if job.started_at else None)
            line = (
                f"{job.id[:8]}  {_aware(job.created_at):%m-%d %H:%M}  {job.status.value:<10} {products} product(s)  "
                f"waited {_secs(job.queued_at or job.created_at, job.started_at)}  "
                f"ran {_secs(job.started_at, end)}{'' if job.completed_at else ' (still going)' if job.started_at else ''}"
                f"  try {job.attempt}"
            )
            print(line)
            final = ((job.result.qc_report or {}).get("final_check") or {}) if job.result else {}
            timings = final.get("timings") or {}
            if timings:
                parts = [f"{_STAGES.get(k, k)} {v}s" for k, v in timings.items() if k != "total"]
                print(f"          stages: {', '.join(parts)}  (total {timings.get('total')}s)")
            if job.status.value in ("processing", "queued") and job.progress:
                print(f"          now: {job.progress}")
            if job.error_message:
                print(f"          error: {job.error_message[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
