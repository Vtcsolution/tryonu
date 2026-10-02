"""Live, side-by-side comparison of the old masked pipeline vs. the zoned
pipeline (OpenAI and Gemini), against local fixture files.

    python -m app.scripts.live_compare_engines tests/fixtures/live/manifest.json

NOT RUN as part of building this script — it makes real, billed OpenAI
and Gemini image-generation calls the moment it's executed.

Standalone: no database, no job row, no credit debit, nothing written to
the configured object storage. Every product/person image is read from a
local file (never fetched over HTTP) by monkeypatching the pipelines' own
_download() to resolve "local://<slug>" URLs against an in-memory map --
the rest of masked.py/zoned.py runs completely unmodified. Debug images
go to a local folder (./live_compare_output/<timestamp>/) rather than
DebugCapture's allowlisted S3 path.

Cost tracking is in DOLLARS, not call count: the three engines have
different, non-comparable per-call prices (OpenAI's own token-based
image-output rate vs Gemini's per-resolution rate), so a call-count cap
would not actually bound spend the way the task's own $10 total budget
requires. Rates are the ones documented in app/core/config.py's own
comments (checked against each provider's docs on 2026-10-02) -- update
_OPENAI_COST_PER_IMAGE/_GEMINI_COST_PER_IMAGE here if those change.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.ai.providers.base import OutfitPiece
from app.ai.providers.gemini_image import GeminiImageTryOnProvider
from app.ai.providers.openai_image import OpenAIImageTryOnProvider
from app.core.config import get_settings
from app.models.enums import OutfitSlot
from app.services.tryon_quality import masked as masked_module
from app.services.tryon_quality import zoned as zoned_module
from app.services.tryon_quality.masked import render_masked_look
from app.services.tryon_quality.pipeline import ItemReport, LookItem, RenderHint
from app.services.tryon_quality.zoned import BatchPiece, render_zoned_look

# Order-of-magnitude per-image estimates at the quality/resolution this
# script actually requests (see main()) -- not a flat rate across all
# settings. OpenAI is token-based (image output $30/1M tokens); this is
# the commonly-reported per-image figure at medium/1024x1536 ($0.041),
# used as-is since "high"/"xhigh" token counts were not published at the
# time of writing (2026-10-02) -- treat the OpenAI total as a floor, not
# an exact figure, and watch the real response for anything unexpected.
_OPENAI_COST_PER_IMAGE_USD = 0.041
# Gemini 3.1 Flash Image at 2K (ai.google.dev/gemini-api/docs/pricing, 2026-10-02).
_GEMINI_COST_PER_IMAGE_USD = 0.101


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class CostBudget:
    max_usd: float
    spent_usd: float = 0.0

    def spend(self, usd: float, label: str) -> None:
        if self.spent_usd + usd > self.max_usd:
            raise BudgetExceeded(
                f"refusing '{label}' (${usd:.3f}): would bring total to "
                f"${self.spent_usd + usd:.3f}, over the ${self.max_usd:.2f} cap"
            )
        self.spent_usd += usd
        print(f"  [${self.spent_usd:.3f}/{self.max_usd:.2f}] {label} (${usd:.3f})")


class LocalDebug:
    """Same .save(stage, image, label) interface as DebugCapture, writing
    straight to a local folder instead of the configured object storage."""

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


def _load_manifest(path: Path) -> tuple[bytes, list[LookItem], dict[str, np.ndarray]]:
    data = json.loads(path.read_text())
    root = path.parent
    person = (root / data["person_photo"]).read_bytes()
    items: list[LookItem] = []
    local_images: dict[str, np.ndarray] = {}
    for p in data["products"]:
        slug = f"local://{Path(p['image_file']).stem}"
        img_bytes = (root / p["image_file"]).read_bytes()
        local_images[slug] = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        items.append(LookItem(image_url=slug, slot=OutfitSlot(p["slot"]), name=p["name"]))
    return person, items, local_images


def _patch_local_downloads(local_images: dict[str, np.ndarray]):
    """Every product image comes from a local file, never HTTP -- patches
    both pipelines' own bound _download() so nothing in masked.py/zoned.py
    needs to know this is a fixture run."""

    async def fake_download(url: str) -> np.ndarray:
        if url not in local_images:
            raise ValueError(f"no local fixture registered for {url!r}")
        return local_images[url]

    masked_module._download = fake_download
    zoned_module._download = fake_download


def _detect_black_box(image: np.ndarray, min_share: float = 0.01) -> dict | None:
    """A generic, product-agnostic check for the exact bug this task
    started from: a large, near-perfectly-flat dark rectangular region
    (the symptom of a failed/empty paste, not a real photo's own shadow,
    which is never this flat). Returns the region's own bounding box
    (fractions of the photo) if found, else None."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark = (gray < 25).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    h, w = image.shape[:2]
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area / (h * w) < min_share:
            continue
        region = gray[y : y + bh, x : x + bw]
        if float(region.std()) < 6.0:  # flat, not real dark photo content (hair, shadow, fabric)
            return {"x0": x / w, "y0": y / h, "x1": (x + bw) / w, "y1": (y + bh) / h, "share": area / (h * w)}
    return None


def _report_row(name: str, report: ItemReport) -> str:
    v = report.verdict
    if v is None:
        return f"  {name[:28]:28} applied={'no':5}  (no verdict — {report.history[-1] if report.history else 'n/a'})"
    return (
        f"  {name[:28]:28} applied={str(report.verified):5} "
        f"colour/design={v.product_match:.0f}  location={v.worn_correctly:.0f}  realism={v.realism:.0f}"
    )


def _pipeline_edit_masked_openai(provider: OpenAIImageTryOnProvider, budget: CostBudget):
    async def edit(person_png: bytes, mask_png: bytes, item: LookItem, hint: RenderHint) -> bytes:
        budget.spend(_OPENAI_COST_PER_IMAGE_USD, f"edit_masked (old engine): {item.name[:40]}")
        piece = OutfitPiece(item.image_url, item.slot.value, item.name, note=hint.fix, description=hint.description)
        return (await provider.edit_masked(person_png, mask_png, piece)).image_bytes

    return edit


def _pipeline_edit_batch_openai(provider: OpenAIImageTryOnProvider, budget: CostBudget):
    async def edit_batch(person_png: bytes, mask_png: bytes, pieces: list[BatchPiece]) -> bytes:
        names = ", ".join(p.item.name[:30] for p in pieces)
        budget.spend(_OPENAI_COST_PER_IMAGE_USD, f"edit_masked_batch ({len(pieces)}, zoned/OpenAI): {names}")
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        return (await provider.edit_masked_batch(person_png, mask_png, outfit_pieces)).image_bytes

    return edit_batch


def _pipeline_edit_batch_gemini(provider: GeminiImageTryOnProvider, budget: CostBudget):
    async def edit_batch(person_png: bytes, mask_png: bytes, pieces: list[BatchPiece]) -> bytes:  # noqa: ARG001
        names = ", ".join(p.item.name[:30] for p in pieces)
        budget.spend(_GEMINI_COST_PER_IMAGE_USD, f"generate_outfit ({len(pieces)}, zoned/Gemini): {names}")
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        data_uri = "data:image/png;base64," + base64.b64encode(person_png).decode()
        return (await provider.generate_outfit(data_uri, outfit_pieces)).image_bytes

    return edit_batch


async def _run_old_engine(person, items, provider, budget, out_root):
    debug = LocalDebug(out_root, "old_openai")
    t0 = time.perf_counter()
    settings = get_settings()
    image, reports = await render_masked_look(
        person, items, _pipeline_edit_masked_openai(provider, budget),
        retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
        min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=180, debug=debug,
    )
    elapsed = time.perf_counter() - t0
    (out_root / "old_openai_result.jpg").write_bytes(image)
    return image, reports, elapsed


async def _run_zoned(person, items, edit_batch, label, out_root):
    debug = LocalDebug(out_root, label)
    t0 = time.perf_counter()
    settings = get_settings()
    image, reports = await render_zoned_look(
        person, items, edit_batch,
        retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
        min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=180, debug=debug,
    )
    elapsed = time.perf_counter() - t0
    (out_root / f"{label}_result.jpg").write_bytes(image)
    return image, reports, elapsed


async def main(manifest_path: Path, max_usd: float, which: list[str]) -> int:
    settings = get_settings()
    person, items, local_images = _load_manifest(manifest_path)
    _patch_local_downloads(local_images)
    budget = CostBudget(max_usd=max_usd)
    out_root = Path("live_compare_output") / time.strftime("%Y%m%d_%H%M%S")
    print(f"Output: {out_root}\nBudget: ${max_usd:.2f}\n")

    results: dict[str, tuple] = {}
    try:
        if "old" in which:
            if not settings.OPENAI_API_KEY:
                print("OPENAI_API_KEY not set — skipping old engine")
            else:
                print("=== OLD engine (masked.py, OpenAI) ===")
                openai_provider = OpenAIImageTryOnProvider(
                    api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_IMAGE_MODEL, quality="high"
                )
                results["old_openai"] = await _run_old_engine(person, items, openai_provider, budget, out_root)

        if "openai" in which:
            if not settings.OPENAI_API_KEY:
                print("OPENAI_API_KEY not set — skipping zoned/OpenAI")
            else:
                print("\n=== ZONED engine, OpenAI ===")
                openai_provider = OpenAIImageTryOnProvider(
                    api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_IMAGE_MODEL, quality="high"
                )
                edit_batch = _pipeline_edit_batch_openai(openai_provider, budget)
                results["zoned_openai"] = await _run_zoned(person, items, edit_batch, "zoned_openai", out_root)

        if "gemini" in which:
            if not settings.GEMINI_API_KEY:
                print("GEMINI_API_KEY not set — skipping zoned/Gemini")
            else:
                print("\n=== ZONED engine, Gemini ===")
                gemini_provider = GeminiImageTryOnProvider(
                    api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_IMAGE_MODEL, image_size="2K"
                )
                edit_batch = _pipeline_edit_batch_gemini(gemini_provider, budget)
                results["zoned_gemini"] = await _run_zoned(person, items, edit_batch, "zoned_gemini", out_root)
    except BudgetExceeded as exc:
        print(f"\nSTOPPED: {exc}")
        print(f"Partial results (if any) are saved under {out_root}")

    print(f"\n=== Results: {out_root} ===")
    for label, (image, reports, elapsed) in results.items():
        print(f"\n--- {label} ({elapsed:.1f}s) ---")
        for item, report in zip(items, reports):
            print(_report_row(item.name, report))
        black_box = _detect_black_box(cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR))
        print(f"  black-box check: {'FOUND ' + str(black_box) if black_box else 'clean'}")

    print(f"\ntotal spend: ${budget.spent_usd:.3f} / ${budget.max_usd:.2f}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path, help="path to manifest.json (see tests/fixtures/live/manifest.json)")
    parser.add_argument("--max-usd", type=float, default=10.0, help="hard cap on total spend across all engines")
    parser.add_argument(
        "--which", default="old,openai,gemini", help="comma-separated: old,openai,gemini"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.manifest, args.max_usd, args.which.split(","))))
