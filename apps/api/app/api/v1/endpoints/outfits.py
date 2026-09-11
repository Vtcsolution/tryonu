from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.outfit import Outfit, OutfitItem
from app.models.product import Product
from app.schemas.common import Message
from app.schemas.outfit import CreateOutfitRequest, OutfitOut

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

    outfit = Outfit(user_id=user.id, name=payload.name, occasion=payload.occasion)
    db.add(outfit)
    await db.flush()
    for pos, item in enumerate(payload.items):
        db.add(OutfitItem(outfit_id=outfit.id, product_id=item.product_id, slot=item.slot, position=pos))
    await db.commit()

    result = await db.execute(select(Outfit).where(Outfit.id == outfit.id).options(*_LOAD_OPTS))
    return result.scalar_one()


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
