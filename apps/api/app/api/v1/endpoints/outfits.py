from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.outfit import Outfit, OutfitItem
from app.models.product import Product
from app.schemas.common import Message
from app.schemas.outfit import (
    CompatibilityPreviewRequest,
    CompatibilityPreviewResponse,
    CreateOutfitRequest,
    OutfitOut,
)
from app.models.enums import OutfitSlot
from app.services.outfit_compatibility import score_outfit
from app.services.outfit_slots import slot_for

router = APIRouter(prefix="/outfits", tags=["outfits"])

_LOAD_OPTS = (
    selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.images),
    selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.retailer),
)


@router.post("", response_model=OutfitOut, status_code=status.HTTP_201_CREATED)
async def create_outfit(payload: CreateOutfitRequest, user: CurrentUser, db: DbSession):
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An outfit needs at least one item")
    if len(payload.items) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many items (max 10)")

    product_ids = [i.product_id for i in payload.items]
    result = await db.execute(select(Product).where(Product.id.in_(product_ids), Product.is_active.is_(True)))
    found = {p.id: p for p in result.scalars().all()}
    missing = [pid for pid in product_ids if pid not in found]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Products not found: {missing}")

    ordered_products = [found[i.product_id] for i in payload.items]
    # "other" is what older outfits carried for items the classifier didn't
    # know yet (a kurta pajama) — swapping an item copies the slot, so
    # classify those from the product instead of passing "other" along
    slots = [
        slot_for(p.name) if i.slot == OutfitSlot.OTHER else i.slot for i, p in zip(payload.items, ordered_products)
    ]
    coherence = score_outfit(ordered_products, slots)

    outfit = Outfit(
        user_id=user.id,
        name=payload.name,
        occasion=payload.occasion,
        compatibility_score=coherence.overall,
        compatibility_notes=coherence.notes or None,
    )
    db.add(outfit)
    await db.flush()
    for pos, (item, slot) in enumerate(zip(payload.items, slots)):
        db.add(OutfitItem(outfit_id=outfit.id, product_id=item.product_id, slot=slot, position=pos))
    await db.commit()

    result = await db.execute(select(Outfit).where(Outfit.id == outfit.id).options(*_LOAD_OPTS))
    return result.scalar_one()


@router.post("/preview-compatibility", response_model=CompatibilityPreviewResponse)
async def preview_compatibility(payload: CompatibilityPreviewRequest, user: CurrentUser, db: DbSession):
    """Scores a candidate set without persisting anything — lets the
    builder UI show a live score as the user adds/removes items, instead
    of creating a row per keystroke."""
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least one item")

    product_ids = [i.product_id for i in payload.items]
    result = await db.execute(select(Product).where(Product.id.in_(product_ids), Product.is_active.is_(True)))
    found = {p.id: p for p in result.scalars().all()}
    missing = [pid for pid in product_ids if pid not in found]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Products not found: {missing}")

    ordered_products = [found[i.product_id] for i in payload.items]
    coherence = score_outfit(ordered_products, [i.slot for i in payload.items])
    return CompatibilityPreviewResponse(
        overall=coherence.overall, color=coherence.color, style=coherence.style, notes=coherence.notes
    )


@router.get("", response_model=list[OutfitOut])
async def list_outfits(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Outfit).where(Outfit.user_id == user.id).options(*_LOAD_OPTS).order_by(Outfit.created_at.desc())
    )
    return list(result.scalars().unique().all())


@router.get("/{outfit_id}", response_model=OutfitOut)
async def get_outfit(outfit_id: str, user: CurrentUser, db: DbSession):
    result = await db.execute(select(Outfit).where(Outfit.id == outfit_id).options(*_LOAD_OPTS))
    outfit = result.scalar_one_or_none()
    if outfit is None or outfit.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found")
    return outfit


@router.delete("/{outfit_id}", response_model=Message)
async def delete_outfit(outfit_id: str, user: CurrentUser, db: DbSession):
    outfit = await db.get(Outfit, outfit_id)
    if outfit is None or outfit.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found")
    await db.delete(outfit)
    await db.commit()
    return Message(detail="Outfit deleted")
