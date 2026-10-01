"""Offline calibration for the shadow-mode distractor-rank signal
(app/services/tryon_quality/distractor_rank.py): replays it against past
completed try-on jobs' own stored results and product photos, so a real
pass/fail threshold can eventually be set from actual score distributions
instead of guessed at. No render, no vision-model call, no paid API of
any kind — every image used here is already stored (the job's own result)
or already public (a product's own listing photo); the only computation
is local CPU CLIP inference.

    python -m app.scripts.calibrate_distractor_rank [--limit N]

Prints the rank/margin distribution across every drawn item found. A
healthy signal is almost every item ranking 1st (margin > 0); items that
don't are worth a manual look — either the render really did drift
toward a lookalike, or the category-based distractor set is too noisy to
use as a threshold on its own (see distractor_rank.py's own docstring on
why category is the proxy used for "the same search").
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.enums import JobStatus
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult
from app.services.tryon_quality.compose import Region, decode
from app.services.tryon_quality.distractor_rank import rank_against_distractors
from app.workers.tasks.tryon_tasks import _box_crop, _distractors_for

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None


async def _fetch(url: str):  # noqa: ANN202
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    return decode(resp.content)


async def main(limit: int) -> int:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(TryOnResult, TryOnJob)
            .join(TryOnJob, TryOnResult.job_id == TryOnJob.id)
            .where(TryOnJob.status == JobStatus.COMPLETED, TryOnResult.placements.is_not(None))
            .order_by(TryOnJob.completed_at.desc())
            .limit(limit)
        )
        ranks: list[int] = []
        margins: list[float] = []
        for result, job in rows.all():
            try:
                full = await _fetch(result.image_url)
            except Exception as exc:  # noqa: BLE001 — one bad row must not stop the run
                print(f"  skip job {job.id}: couldn't fetch result image ({exc})")
                continue
            for placement in result.placements or []:
                if not placement.get("drawn") or not placement.get("product_id") or not placement.get("box"):
                    continue
                product = await session.get(Product, placement["product_id"])
                if product is None:
                    continue
                distractors = await _distractors_for(session, product)
                if not distractors:
                    continue
                try:
                    box = Region(*placement["box"])
                    crop = _box_crop(full, box)
                    product_image = await _fetch(product.primary_image_url)
                    distractor_images = []
                    for d in distractors:
                        if not d.primary_image_url:
                            continue
                        try:
                            distractor_images.append(await _fetch(d.primary_image_url))
                        except Exception:  # noqa: BLE001 — one missing distractor photo isn't fatal
                            continue
                    if not distractor_images:
                        continue
                    outcome = rank_against_distractors(crop, product_image, distractor_images)
                except Exception as exc:  # noqa: BLE001 — one bad item must not stop the run
                    print(f"  skip {placement.get('name')!r} on job {job.id}: {exc}")
                    continue
                ranks.append(outcome.rank)
                margins.append(outcome.margin)
                print(
                    f"  job {job.id} — {placement.get('name', '')[:40]!r}: "
                    f"rank {outcome.rank}/{outcome.total}, margin {outcome.margin:+.4f}"
                )

        if not ranks:
            print("No eligible items found (need completed jobs with placements and same-category distractors).")
            return 1

        print(f"\n{len(ranks)} items scored")
        print(f"rank 1 (best match): {ranks.count(1)} ({100 * ranks.count(1) / len(ranks):.0f}%)")
        print(f"mean margin: {statistics.mean(margins):+.4f}, median: {statistics.median(margins):+.4f}")
        print(f"worst margin: {min(margins):+.4f}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200, help="how many recent completed jobs to scan")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.limit)))
