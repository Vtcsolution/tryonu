"""Sharing a finished try-on: the owner makes (or stops) a public link; anyone
with the link sees the picture and the products in it, with their shop links,
and can try the same products on themselves (POST /shared/{token}/try)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.enums import JobStatus, OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from app.models.product import Product
from app.models.shared_look import SharedLook
from app.models.tryon import TryOnJob
from app.services.look_products import look_products
from app.services.storage_service import get_storage

router = APIRouter(tags=["sharing"])


class ShareOut(BaseModel):
    token: str
    url: str
    views: int = 0


class SharedProductOut(BaseModel):
    id: str
    name: str
    price_cents: int
    currency: str
    image_url: str | None
    shop: str | None
    buy_url: str
    # drawn on the picture (True), shown alongside as a match (False), unknown (None)
    on_photo: bool | None = None


class SharedLookOut(BaseModel):
    token: str
    image_url: str
    title: str
    products: list[SharedProductOut]
    total_cents: int | None = None  # when every product has the same currency
    currency: str | None = None
    created_at: datetime


class TryThisLookOut(BaseModel):
    """Where the visitor's own try-on of a shared look starts."""

    outfit_id: str | None = None
    product_id: str | None = None


def _site() -> str:
    return str(get_settings().FRONTEND_URL).rstrip("/")


def _api() -> str:
    return get_settings().PUBLIC_API_BASE_URL.rstrip("/")


async def _owned_job(db: DbSession, user_id: str, job_id: str) -> TryOnJob:
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.result)))
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Look not found")
    return job


@router.post("/tryon/{job_id}/share", response_model=ShareOut)
async def share_look(job_id: str, user: CurrentUser, db: DbSession):
    """The owner shares a finished look: the same link every time until they stop sharing."""
    job = await _owned_job(db, user.id, job_id)
    if job.status != JobStatus.COMPLETED or job.result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a finished look can be shared.")
    shared = await db.scalar(
        select(SharedLook).where(SharedLook.tryon_job_id == job.id, SharedLook.revoked_at.is_(None))
    )
    if shared is None:
        shared = SharedLook(token=secrets.token_urlsafe(12), user_id=user.id, tryon_job_id=job.id)
        db.add(shared)
        await db.commit()
        await db.refresh(shared)
    return ShareOut(token=shared.token, url=f"{_site()}/look/{shared.token}", views=shared.views)


@router.delete("/tryon/{job_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def stop_sharing(job_id: str, user: CurrentUser, db: DbSession):
    """The link stops working at once, picture included."""
    await _owned_job(db, user.id, job_id)
    await db.execute(
        update(SharedLook)
        .where(SharedLook.tryon_job_id == job_id, SharedLook.user_id == user.id, SharedLook.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _live(db: DbSession, token: str) -> tuple[SharedLook, TryOnJob]:
    shared = await db.scalar(select(SharedLook).where(SharedLook.token == token, SharedLook.revoked_at.is_(None)))
    if shared is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This look isn't shared anymore")
    job = await db.scalar(
        select(TryOnJob)
        .where(TryOnJob.id == shared.tryon_job_id)
        .options(
            selectinload(TryOnJob.result),
            selectinload(TryOnJob.product).selectinload(Product.images),
            selectinload(TryOnJob.product).selectinload(Product.retailer),
        )
    )
    if job is None or job.result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This look isn't shared anymore")
    return shared, job


def _product_out(p: Product, drawn: set[str] | None = None) -> SharedProductOut:
    return SharedProductOut(
        id=p.id,
        name=p.name,
        price_cents=p.price_cents,
        currency=p.currency,
        image_url=p.primary_image_url,
        shop=p.merchant_name or (p.retailer.name if p.retailer else None),
        buy_url=f"{_api()}/api/v1/affiliate/go/{p.id}?source=shared_look",
        on_photo=None if drawn is None else p.id in drawn,
    )


@router.get(
    "/shared/{token}",
    response_model=SharedLookOut,
    dependencies=[Depends(rate_limiter("shared_look_view", limit=600, window_seconds=3600))],
)
async def shared_look(token: str, db: DbSession):
    shared, job = await _live(db, token)
    pairs, drawn = await look_products(db, job)
    products = [p for p, _ in pairs]
    shared.views += 1
    await db.commit()
    title = products[0].name if len(products) == 1 else f"A look with {len(products)} pieces" if products else "A look"
    currencies = {p.currency.lower() for p in products}
    same = len(currencies) == 1
    return SharedLookOut(
        token=shared.token,
        image_url=f"{_api()}/api/v1/shared/{shared.token}/image",
        title=title,
        products=[_product_out(p, drawn) for p in products],
        total_cents=sum(p.price_cents for p in products) if same else None,
        currency=products[0].currency if same else None,
        created_at=shared.created_at,
    )


@router.post(
    "/shared/{token}/try",
    response_model=TryThisLookOut,
    dependencies=[Depends(rate_limiter("shared_look_try", limit=30, window_seconds=3600))],
)
async def try_this_look(token: str, user: CurrentUser, db: DbSession):
    """A visitor tries a shared look on themselves: the same products, as
    their own outfit, ready on the try-on page with their own photo."""
    from app.services.outfit_compatibility import score_outfit
    from app.services.outfit_slots import slot_for

    _, job = await _live(db, token)
    pairs, _ = await look_products(db, job)
    pairs = [(p, slot) for p, slot in pairs if p.is_active][:10]
    if not pairs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The products in this look aren't available anymore.")
    if len(pairs) == 1:
        return TryThisLookOut(product_id=pairs[0][0].id)
    slots = [slot if slot not in (None, OutfitSlot.OTHER) else slot_for(p.name) for p, slot in pairs]
    products = [p for p, _ in pairs]
    coherence = score_outfit(products, slots)
    outfit = Outfit(
        user_id=user.id,
        name="Shared look",
        compatibility_score=coherence.overall,
        compatibility_notes=coherence.notes or None,
    )
    db.add(outfit)
    await db.flush()
    for pos, (product, slot) in enumerate(zip(products, slots)):
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()
    return TryThisLookOut(outfit_id=outfit.id)


@router.get(
    "/shared/{token}/image",
    dependencies=[Depends(rate_limiter("shared_look_image", limit=1200, window_seconds=3600))],
)
async def shared_look_image(token: str, db: DbSession):
    """The picture at a link that never expires (for link previews), while it's shared."""
    _, job = await _live(db, token)
    key = job.result.storage_key
    data = get_storage().read(key)
    kind = "image/png" if key.lower().endswith(".png") else "image/webp" if key.lower().endswith(".webp") else "image/jpeg"
    # short cache: stopping sharing must take effect soon
    return Response(content=data, media_type=kind, headers={"Cache-Control": "public, max-age=600"})
