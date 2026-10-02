"""End-to-end realistic comparison: a real AI-stylist ask (real eBay/
AliExpress search, real OpenAI text-model picks) feeding real old-vs-zoned
image rendering (real OpenAI + Gemini image calls) -- everything a real
user's request does, except the HTTP layer and which Postgres stores the
rows. Run against the dev database set up this session
(apps/api/.env.dev) -- never production, which this machine cannot reach
at all (no SSH, no direct DB access).

    DATABASE_URL=<dev url> python -m app.scripts.live_user_simulation \
        person_front.jpg "a full wedding guest outfit with jewelry" \
        "casual wear with a watch and a bag" \
        "a complete 8-piece bridal look" \
        --max-usd 10

NOT RUN as part of writing this script -- it makes real, billed stylist
and image-generation calls the moment it executes. Prints which database
host it's actually using at startup so that's always auditable before
anything is spent.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.datastructures import UploadFile

from app.ai.providers.gemini_image import GeminiImageTryOnProvider
from app.ai.providers.openai_image import OpenAIImageTryOnProvider
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.enums import PhotoKind
from app.models.photo import UserPhoto
from app.models.product import Product
from app.models.user import User
from app.schemas.stylist import StylistAskRequest
from app.services.image_service import validate_and_optimize
from app.services.outfit_slots import slot_for
from app.services.storage_service import get_storage, new_key
from app.services.stylist_service import ask_stylist
from app.services.tryon_quality.masked import render_masked_look
from app.services.tryon_quality.pipeline import ItemReport, LookItem
from app.services.tryon_quality.zoned import BatchPiece, render_zoned_look

_OPENAI_COST_PER_IMAGE_USD = 0.041
_GEMINI_COST_PER_IMAGE_USD = 0.101
_TEST_USER_EMAIL = "live-sim@tryonu.test"


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class CostBudget:
    max_usd: float
    spent_usd: float = 0.0
    log: list[str] = field(default_factory=list)

    def spend(self, usd: float, label: str) -> None:
        if self.spent_usd + usd > self.max_usd:
            raise BudgetExceeded(
                f"refusing '{label}' (${usd:.3f}): would bring total to "
                f"${self.spent_usd + usd:.3f}, over the ${self.max_usd:.2f} cap"
            )
        self.spent_usd += usd
        line = f"[${self.spent_usd:.3f}/{self.max_usd:.2f}] {label} (${usd:.3f})"
        self.log.append(line)
        print("  " + line)


class LocalDebug:
    def __init__(self, root: Path, label: str) -> None:
        self.root = root / label
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


def _detect_black_box(image: np.ndarray, min_share: float = 0.01) -> dict | None:
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
        if float(region.std()) < 6.0:
            return {"x0": x / w, "y0": y / h, "x1": (x + bw) / w, "y1": (y + bh) / h, "share": round(area / (h * w), 4)}
    return None


async def _get_or_create_test_user(session) -> User:  # noqa: ANN001
    row = await session.execute(select(User).where(User.email == _TEST_USER_EMAIL))
    user = row.scalar_one_or_none()
    if user is not None:
        return user
    user = User(email=_TEST_USER_EMAIL, hashed_password="x", is_active=True, email_verified=True, credits_balance=1000)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _store_front_photo(session, user: User, photo_path: Path) -> UserPhoto:  # noqa: ANN001
    from starlette.datastructures import Headers

    data = photo_path.read_bytes()
    content_type = "image/jpeg" if photo_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    upload = UploadFile(filename=photo_path.name, file=io.BytesIO(data), headers=Headers({"content-type": content_type}))
    processed = await validate_and_optimize(upload)
    key = new_key("users", user.id, "photos", f"{uuid.uuid4().hex}.{processed.ext}")
    storage = get_storage()
    storage.put(key, processed.content, processed.content_type)
    photo = UserPhoto(
        user_id=user.id, kind=PhotoKind.FRONT, storage_key=key, url=storage.signed_url(key),
        width=processed.width, height=processed.height, content_type=processed.content_type,
        byte_size=len(processed.content), is_primary=True,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _ask_and_fetch_products(session, user: User, prompt: str, max_items: int, budget: CostBudget):  # noqa: ANN001
    req = StylistAskRequest(prompt=prompt, max_items=max_items)
    stylist_request, alternatives = await ask_stylist(session, user_id=user.id, req=req)
    budget.spend(0.001, f"ask_stylist text model: {prompt[:50]!r}")  # gpt-4o-mini-class, negligible but logged
    ids = stylist_request.recommended_product_ids or []
    if not ids:
        return [], {}
    rows = await session.execute(
        select(Product).where(Product.id.in_(ids)).options(selectinload(Product.images))
    )
    by_id = {p.id: p for p in rows.scalars().all()}
    products = [by_id[i] for i in ids if i in by_id]
    distractor_options = {
        pid: [{"product_id": None, "image_url": o.images[0]} for o in opts if o.images]
        for pid, (term, opts) in alternatives.items()
    }
    return products, distractor_options


def _look_items(products: list[Product]) -> list[LookItem]:
    return [LookItem(image_url=p.primary_image_url, slot=slot_for(p.name), name=p.name) for p in products if p.primary_image_url]


def _report_row(name: str, report: ItemReport) -> str:
    v = report.verdict
    if v is None:
        return f"    {name[:28]:28} applied={'no':5}  ({report.history[-1] if report.history else 'no attempt'})"
    return (
        f"    {name[:28]:28} applied={str(report.verified):5} "
        f"colour/design={v.product_match:.0f}  location={v.worn_correctly:.0f}  realism={v.realism:.0f}"
    )


def _build_adapters(openai_provider, gemini_provider, budget: CostBudget):  # noqa: ANN001
    from app.ai.providers.base import OutfitPiece
    import base64

    async def edit_masked_old(person_png, mask_png, item, hint):
        budget.spend(_OPENAI_COST_PER_IMAGE_USD, f"old/edit_masked: {item.name[:40]}")
        piece = OutfitPiece(item.image_url, item.slot.value, item.name, note=hint.fix, description=hint.description)
        return (await openai_provider.edit_masked(person_png, mask_png, piece)).image_bytes

    async def edit_batch_openai(person_png, mask_png, pieces: list[BatchPiece]):
        names = ", ".join(p.item.name[:30] for p in pieces)
        budget.spend(_OPENAI_COST_PER_IMAGE_USD, f"zoned-openai/batch ({len(pieces)}): {names}")
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        return (await openai_provider.edit_masked_batch(person_png, mask_png, outfit_pieces)).image_bytes

    async def edit_batch_gemini(person_png, mask_png, pieces: list[BatchPiece]):
        names = ", ".join(p.item.name[:30] for p in pieces)
        budget.spend(_GEMINI_COST_PER_IMAGE_USD, f"zoned-gemini/batch ({len(pieces)}): {names}")
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        data_uri = "data:image/png;base64," + base64.b64encode(person_png).decode()
        return (await gemini_provider.generate_outfit(data_uri, outfit_pieces)).image_bytes

    return edit_masked_old, edit_batch_openai, edit_batch_gemini


async def main(photo_path: Path, prompts: list[str], max_usd: float, which: list[str]) -> int:
    settings = get_settings()
    host = urlparse(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")).hostname
    print(f"DATABASE_URL host: {host}  (must be the dev project, never production)")
    if not settings.OPENAI_API_KEY:
        print("OPENAI_API_KEY not set — nothing to do")
        return 1

    budget = CostBudget(max_usd=max_usd)
    out_root = Path("live_sim_output") / time.strftime("%Y%m%d_%H%M%S")
    openai_provider = OpenAIImageTryOnProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_IMAGE_MODEL, quality=settings.OPENAI_IMAGE_QUALITY)
    gemini_provider = (
        GeminiImageTryOnProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_IMAGE_MODEL, image_size="2K")
        if settings.GEMINI_API_KEY else None
    )
    edit_masked_old, edit_batch_openai, edit_batch_gemini = _build_adapters(openai_provider, gemini_provider, budget)

    async with AsyncSessionLocal() as session:
        user = await _get_or_create_test_user(session)
        photo = await _store_front_photo(session, user, photo_path)
        person_bytes = get_storage().read(photo.storage_key)
        print(f"test user: {user.email} ({user.id}); photo stored at {photo.storage_key}\n")

        for i, prompt in enumerate(prompts, start=1):
            print(f"\n{'=' * 70}\nPROMPT {i}: {prompt!r}\n{'=' * 70}")
            max_items = 10 if "8" in prompt or "eight" in prompt.lower() else 6
            try:
                products, distractor_options = await _ask_and_fetch_products(session, user, prompt, max_items, budget)
            except Exception as exc:  # noqa: BLE001
                print(f"  ask_stylist failed: {exc}")
                continue
            if not products:
                print("  no products recommended — skipping")
                continue
            items = _look_items(products)
            print(f"  {len(items)} real products: {[it.name[:40] for it in items]}")

            try:
                if "old" in which:
                    print("\n  --- OLD engine (masked.py, OpenAI) ---")
                    debug = LocalDebug(out_root, f"prompt{i}_old")
                    image, reports = await render_masked_look(
                        person_bytes, items, edit_masked_old,
                        retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                        min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                        debug=debug,
                    )
                    (out_root / f"prompt{i}_old.jpg").write_bytes(image)
                    for item, report in zip(items, reports):
                        print(_report_row(item.name, report))
                    bb = _detect_black_box(cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR))
                    print(f"    black-box check: {'FOUND ' + str(bb) if bb else 'clean'}")

                if "zoned" in which:
                    print("\n  --- ZONED engine (OpenAI) ---")
                    debug = LocalDebug(out_root, f"prompt{i}_zoned_openai")
                    image, reports = await render_zoned_look(
                        person_bytes, items, edit_batch_openai,
                        retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                        min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                        debug=debug,
                    )
                    (out_root / f"prompt{i}_zoned_openai.jpg").write_bytes(image)
                    for item, report in zip(items, reports):
                        print(_report_row(item.name, report))
                    bb = _detect_black_box(cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR))
                    print(f"    black-box check: {'FOUND ' + str(bb) if bb else 'clean'}")

                if "gemini" in which and gemini_provider is not None:
                    print("\n  --- ZONED engine (Gemini) ---")
                    debug = LocalDebug(out_root, f"prompt{i}_zoned_gemini")
                    image, reports = await render_zoned_look(
                        person_bytes, items, edit_batch_gemini,
                        retries=settings.TRYON_QUALITY_RETRIES, min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                        min_other=settings.TRYON_QUALITY_MIN_FIT, budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                        debug=debug,
                    )
                    (out_root / f"prompt{i}_zoned_gemini.jpg").write_bytes(image)
                    for item, report in zip(items, reports):
                        print(_report_row(item.name, report))
                    bb = _detect_black_box(cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR))
                    print(f"    black-box check: {'FOUND ' + str(bb) if bb else 'clean'}")
            except BudgetExceeded as exc:
                print(f"\nSTOPPED: {exc}")
                break

    print(f"\n{'=' * 70}\nOutput: {out_root}\ntotal spend: ${budget.spent_usd:.3f} / ${budget.max_usd:.2f}\n{'=' * 70}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo", type=Path)
    parser.add_argument("prompts", nargs="+")
    parser.add_argument("--max-usd", type=float, default=10.0)
    parser.add_argument("--which", default="old,zoned,gemini", help="comma-separated: old,zoned,gemini")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.photo, args.prompts, args.max_usd, args.which.split(","))))
