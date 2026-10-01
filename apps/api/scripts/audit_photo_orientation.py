"""Read-only audit: how many ALREADY-STORED user photos are sideways or
upside-down because they were uploaded before validate_and_optimize()
applied EXIF orientation (see app/services/image_service.py).

There is no raw original to reprocess — only the already-stripped JPEG is
ever stored (confirmed: the upload endpoint never persists the raw
upload). The only signal left is the photo's own content: try every
quarter-turn and see which one a face detector agrees is upright
(app/services/photo_orientation.py). Scoped to FRONT and FULL_BODY photos
— the only kinds a frontal face is actually expected in; a BACK photo has
no face to check by design, and is reported separately, unscored.

This makes no writes of any kind and no paid API calls — it only reads
rows and photo bytes and runs a local CPU face detector. Still a real,
non-trivial read against production data (every row, every photo
downloaded) if pointed at it, so it is not run automatically by anything
and should be run deliberately, once, when you want the numbers.

    .venv/Scripts/python scripts/audit_photo_orientation.py [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import PhotoKind  # noqa: E402
from app.models.photo import UserPhoto  # noqa: E402
from app.services.photo_orientation import guess_orientation  # noqa: E402
from app.services.storage_service import get_storage  # noqa: E402
from app.services.tryon_quality.compose import decode  # noqa: E402

_FACE_EXPECTED = {PhotoKind.FRONT, PhotoKind.FULL_BODY}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="audit at most N photos (default: all)")
    args = parser.parse_args()

    storage = get_storage()
    upright = 0
    needs_rotation: list[tuple[str, str, int]] = []  # (photo_id, user_id, degrees)
    unresolved: list[tuple[str, str]] = []  # (photo_id, user_id) — no single confident rotation
    skipped_no_face_expected = 0
    read_failed: list[str] = []

    async with AsyncSessionLocal() as db:
        query = select(UserPhoto).where(UserPhoto.is_deleted.is_(False)).order_by(UserPhoto.created_at)
        if args.limit:
            query = query.limit(args.limit)
        photos = list((await db.execute(query)).scalars().all())

    print(f"auditing {len(photos)} stored photo(s)...")
    for photo in photos:
        if photo.kind not in _FACE_EXPECTED:
            skipped_no_face_expected += 1
            continue
        try:
            raw = await asyncio.to_thread(storage.read, photo.storage_key)
            img = decode(raw)
        except Exception as exc:  # noqa: BLE001 — one unreadable photo must not stop the audit
            read_failed.append(photo.id)
            print(f"  could not read {photo.id}: {str(exc)[:120]}")
            continue

        guess = guess_orientation(img)
        if guess.confident and guess.rotation == 0:
            upright += 1
        elif guess.confident:
            needs_rotation.append((photo.id, photo.user_id, guess.rotation))
        else:
            unresolved.append((photo.id, photo.user_id))

    print()
    print("=== results ===")
    print(f"upright (no action needed):        {upright}")
    print(f"confidently sideways (fixable):     {len(needs_rotation)}")
    print(f"unresolved (ambiguous, no face, or multiple faces found): {len(unresolved)}")
    print(f"skipped (kind has no expected face, e.g. BACK):           {skipped_no_face_expected}")
    print(f"could not be read at all:           {len(read_failed)}")
    print()
    if needs_rotation:
        print("fixable photos (first 20 shown):")
        for photo_id, user_id, degrees in needs_rotation[:20]:
            print(f"  photo={photo_id} user={user_id} needs {degrees}° rotation")
    if unresolved:
        print(f"\n{len(unresolved)} unresolved photo(s) — recommend flagging these profiles for re-upload")
        for photo_id, user_id in unresolved[:20]:
            print(f"  photo={photo_id} user={user_id}")

    print()
    print("This script made no changes. Nothing was written or rotated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
