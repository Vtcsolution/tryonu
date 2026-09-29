"""Check the try-on ORCHESTRATION — mask regions, draw order, which items
share a round — without spending a cent on image generation or vision
calls.

Every real bug found in the masked pipeline's own plumbing this session —
a garment sharing a round with sunglasses and tiling the whole photo, a
ring's window spanning half the frame — was visible in this plan alone,
before a single paid API call: both are pure geometry and draw-order
logic, computed from the photo's face detection, never from what a
model actually draws. Run this FIRST when an outfit's placement looks
wrong. Only reach for a real end-to-end render (or check_engines.py)
once this plan looks right and the open question is about the pixels
themselves, not which region each item was even given.

    ./.venv/bin/python scripts/dry_run_tryon.py --photo person.jpg \
        --item dress "Green Kameez" https://example.com/kameez.jpg \
        --item accessory "Sunglasses" https://example.com/sunglasses.jpg \
        --item shoes "Heels" https://example.com/heels.jpg

Ring, bracelet, watch and bag positions need a real vision call
(pipeline.find_body_part) that this tool never makes — those are shown
with a faked, plausible placeholder and the whole run is marked
SIMULATED for that reason. Their real position, and everything about
whether the model actually draws the right product, still needs a real
render to check. This tool answers a narrower question: given these
items, would the plan itself put a garment in the same round as
something else, or hand an item a window way bigger than it needs —
the two failure modes that don't require generating a single pixel to
catch.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.enums import OutfitSlot  # noqa: E402
from app.services.face_restore import detect_face  # noqa: E402
from app.services.tryon_quality import masked as M  # noqa: E402
from app.services.tryon_quality.compose import Region, decode  # noqa: E402
from app.services.tryon_quality.pipeline import _cap, _GARMENTS  # noqa: E402

_PLACEHOLDER_HAND = Region(0.55, 0.55, 0.72, 0.68)  # a plausible wrist — never the real answer


async def _fake_area_for(item, face, base) -> Region:  # noqa: ANN001, ARG001
    return _PLACEHOLDER_HAND


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photo", required=True, help="a real full-body photo")
    parser.add_argument(
        "--item",
        nargs=3,
        action="append",
        default=[],
        metavar=("SLOT", "NAME", "IMAGE_URL"),
        help="repeatable: an OutfitSlot value (dress/top/bottom/outerwear/shoes/watch/bag/accessory/other), "
        "a name, and a product image URL (never fetched — only used for the report)",
    )
    args = parser.parse_args()
    if not args.item:
        parser.error("at least one --item is required")

    photo = Path(args.photo).read_bytes()
    base = _cap(decode(photo))
    face = detect_face(base)
    print(f"photo: {args.photo}  size: {base.shape[1]}x{base.shape[0]}  face: {'found' if face else 'NOT FOUND'}")
    print()

    items = [M.LookItem(url, OutfitSlot(slot.lower()), name) for slot, name, url in args.item]
    order = M._order_of(items)

    with patch.object(M, "_area_for", _fake_area_for):
        regions = list(await asyncio.gather(*(M._mask_region(items[i], face, base) for i in order)))

    ready = [s for s in range(len(order)) if regions[s] is not None]
    is_garment = [items[order[s]].slot in _GARMENTS for s in range(len(order))]
    waves = M._waves(ready, regions, is_garment)
    simulated = regions.count(_PLACEHOLDER_HAND) > 0

    print("draw plan (priority order):")
    for step, i in enumerate(order):
        item = items[i]
        region = regions[step]
        flag = " [SIMULATED placeholder]" if region == _PLACEHOLDER_HAND else ""
        if region is None:
            print(f"  {step}. {item.name} ({item.slot.value}) — no region found, would show as matched-only, never drawn")
        else:
            print(f"  {step}. {item.name} ({item.slot.value}) — {region}{flag}")
    print()

    print(f"rounds ({len(waves)} total, sequential — a garment must always be alone in its own):")
    ok = True
    for w, wave in enumerate(waves, start=1):
        names = ", ".join(items[order[s]].name for s in wave)
        warn = ""
        if len(wave) > 1 and any(is_garment[s] for s in wave):
            warn = "  <-- BUG: a garment sharing a round tiles the whole photo (see commit e63c919)"
            ok = False
        print(f"  round {w}: {names}{warn}")

    print()
    if simulated:
        print("Ring/bracelet/watch/bag positions above are a placeholder, not real — this run never asked the")
        print("real vision call. Everything else (garments, eyewear, ears, forehead, floor) is the exact same")
        print("geometry the real pipeline would use, no API call needed for that part either way.")
    print("PLAN OK" if ok else "PLAN HAS A BUG — fix before spending anything on a real render")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
