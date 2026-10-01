"""Live, side-by-side comparison of the old masked pipeline vs. the zoned
pipeline — same person photo, same products, one real OpenAI run each.

    python -m app.scripts.live_compare_engines path/to/config.json

NOT RUN as part of this session — this script makes real, billed OpenAI
image-generation calls the moment it's executed. Written so it's ready
the moment you approve a live test.

Standalone: no database, no job row, no credit debit, nothing written to
the configured object storage. Debug images go to a local folder
(./live_compare_output/<timestamp>/) so they're easy to open directly —
not through DebugCapture's allowlist/S3 path, which is for real jobs.

Config file (JSON):
{
  "person_photo": "path/to/front.jpg",
  "products": [
    {"name": "Pink Lawn Kameez", "image_url": "https://...", "slot": "dress"},
    {"name": "Kundan Earrings", "image_url": "https://...", "slot": "accessory"},
    ...
  ]
}

A hard cap (--max-calls, default 20) on TOTAL real image-generation calls
across BOTH engines combined — the script raises and stops before making
a call that would exceed it, never after. That cap covers only
edit_masked/edit_masked_batch (the expensive image-generation calls);
judge()/describe_product()/zone_spec_for() still make their own cheap
vision-text calls on top, uncapped here — the same calls both the old and
zoned engines already make today for every real job, not something this
script adds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.ai.providers.base import OutfitPiece
from app.ai.providers.openai_image import OpenAIImageTryOnProvider
from app.core.config import get_settings
from app.models.enums import OutfitSlot
from app.services.tryon_quality.masked import render_masked_look
from app.services.tryon_quality.pipeline import ItemReport, LookItem, RenderHint
from app.services.tryon_quality.zoned import BatchPiece, render_zoned_look

# Order-of-magnitude estimate only (see docs/tryon/ — current per-call
# pricing for this app's exact configured OPENAI_IMAGE_MODEL has not been
# verified this session). Override with --cost-per-call if you have a
# real rate.
_DEFAULT_COST_PER_CALL_USD = 0.035


class CallBudgetExceeded(RuntimeError):
    pass


@dataclass
class CallBudget:
    max_calls: int
    used: int = 0

    def spend(self, label: str) -> None:
        if self.used + 1 > self.max_calls:
            raise CallBudgetExceeded(
                f"refusing '{label}': this call would be #{self.used + 1}, over the {self.max_calls}-call cap"
            )
        self.used += 1
        print(f"  [call {self.used}/{self.max_calls}] {label}")


class LocalDebug:
    """Same .save(stage, image, label) interface as DebugCapture, writing
    straight to a local folder instead of the configured object storage —
    this script never touches real S3/R2, on purpose."""

    def __init__(self, root: Path, engine: str) -> None:
        self.root = root / engine
        self.root.mkdir(parents=True, exist_ok=True)
        self.enabled = True
        self._seq = 0

    def save(self, stage: str, image, label: str = "") -> None:  # noqa: ANN001
        self._seq += 1
        suffix = f"_{label}" if label else ""
        path = self.root / f"{self._seq:02d}_{stage}{suffix}.png"
        if isinstance(image, (bytes, bytearray)):
            path.write_bytes(bytes(image))
        else:
            cv2.imwrite(str(path), image)


def _load_config(path: Path) -> tuple[bytes, list[LookItem]]:
    data = json.loads(path.read_text())
    person = Path(data["person_photo"]).read_bytes()
    items = [
        LookItem(image_url=p["image_url"], slot=OutfitSlot(p["slot"]), name=p["name"])
        for p in data["products"]
    ]
    return person, items


def _budget_guarded_edit(provider: OpenAIImageTryOnProvider, budget: CallBudget):
    async def edit(person_png: bytes, mask_png: bytes, item: LookItem, hint: RenderHint) -> bytes:
        budget.spend(f"edit_masked: {item.name[:40]}")
        piece = OutfitPiece(item.image_url, item.slot.value, item.name, note=hint.fix, description=hint.description)
        return (await provider.edit_masked(person_png, mask_png, piece)).image_bytes

    return edit


def _budget_guarded_edit_batch(provider: OpenAIImageTryOnProvider, budget: CallBudget):
    async def edit_batch(person_png: bytes, mask_png: bytes, pieces: list[BatchPiece]) -> bytes:
        names = ", ".join(p.item.name[:30] for p in pieces)
        budget.spend(f"edit_masked_batch ({len(pieces)}): {names}")
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        return (await provider.edit_masked_batch(person_png, mask_png, outfit_pieces)).image_bytes

    return edit_batch


def _report_row(report: ItemReport) -> str:
    v = report.verdict
    scores = f"p={v.product_match:.0f} w={v.worn_correctly:.0f} r={v.realism:.0f}" if v else "—"
    return f"  {report.name[:30]:30} verified={str(report.verified):5} attempts={report.attempts}  {scores}"


async def main(config_path: Path, max_calls: int, cost_per_call: float) -> int:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        print("OPENAI_API_KEY is not set — nothing to call.")
        return 1

    person, items = _load_config(config_path)
    provider = OpenAIImageTryOnProvider(
        api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_IMAGE_MODEL, quality=settings.OPENAI_IMAGE_QUALITY
    )
    budget = CallBudget(max_calls=max_calls)
    out_root = Path("live_compare_output") / time.strftime("%Y%m%d_%H%M%S")

    print(f"=== OLD engine (masked.py), {len(items)} products, budget {budget.max_calls} total ===")
    old_debug = LocalDebug(out_root, "old")
    t0 = time.perf_counter()
    try:
        old_image, old_reports = await render_masked_look(
            person, items, _budget_guarded_edit(provider, budget),
            retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
            min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
            debug=old_debug,
        )
        old_time = time.perf_counter() - t0
        (out_root / "old_result.jpg").write_bytes(old_image)
    except CallBudgetExceeded as exc:
        print(f"STOPPED (old engine): {exc}")
        return 1

    print(f"\n=== ZONED engine (zoned.py), {len(items)} products, budget {budget.max_calls - budget.used} left ===")
    zoned_debug = LocalDebug(out_root, "zoned")
    t0 = time.perf_counter()
    try:
        zoned_image, zoned_reports = await render_zoned_look(
            person, items, _budget_guarded_edit_batch(provider, budget),
            retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
            min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
            debug=zoned_debug,
        )
        zoned_time = time.perf_counter() - t0
        (out_root / "zoned_result.jpg").write_bytes(zoned_image)
    except CallBudgetExceeded as exc:
        print(f"STOPPED (zoned engine): {exc}")
        print(f"Old engine's own result is still saved at {out_root / 'old_result.jpg'}")
        return 1

    print(f"\n=== Results: {out_root}/old_result.jpg vs {out_root}/zoned_result.jpg ===")
    print("\nOLD — per item:")
    for r in old_reports:
        print(_report_row(r))
    print("\nZONED — per item:")
    for r in zoned_reports:
        print(_report_row(r))

    print("\n=== Cost & time (estimate — see _DEFAULT_COST_PER_CALL_USD's own caveat) ===")
    print(f"total real image-generation calls: {budget.used}/{budget.max_calls}")
    print(f"estimated cost (both engines, @ ${cost_per_call:.3f}/call): ${budget.used * cost_per_call:.3f}")
    print(f"old engine wall time: {old_time:.1f}s")
    print(f"zoned engine wall time: {zoned_time:.1f}s")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", type=Path, help="path to the JSON config (see module docstring)")
    parser.add_argument("--max-calls", type=int, default=20, help="hard cap on total real image-gen calls")
    parser.add_argument("--cost-per-call", type=float, default=_DEFAULT_COST_PER_CALL_USD)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.config, args.max_calls, args.cost_per_call)))
