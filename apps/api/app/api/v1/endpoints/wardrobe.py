from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.wardrobe import WardrobeItem
from app.schemas.common import Message
from app.schemas.wardrobe import WardrobeItemCreate, WardrobeItemOut, WardrobeItemUpdate
from app.services.image_service import validate_and_optimize
from app.services.storage_service import get_storage, new_key

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])

MAX_ITEMS_PER_USER = 200


async def _get_owned_item(db: DbSession, item_id: str, user_id: str) -> WardrobeItem:
    item = await db.get(WardrobeItem, item_id)
    if item is None or item.user_id != user_id or item.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found")
    return item


@router.get("", response_model=list[WardrobeItemOut])
async def list_wardrobe(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user.id, WardrobeItem.is_deleted.is_(False))
        .order_by(WardrobeItem.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=WardrobeItemOut, status_code=status.HTTP_201_CREATED)
async def create_wardrobe_item(payload: WardrobeItemCreate, user: CurrentUser, db: DbSession):
    count = (
        await db.execute(
            select(WardrobeItem).where(WardrobeItem.user_id == user.id, WardrobeItem.is_deleted.is_(False))
        )
    ).scalars().all()
    if len(count) >= MAX_ITEMS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Wardrobe already has the maximum of {MAX_ITEMS_PER_USER} items"
        )

    item = WardrobeItem(user_id=user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=WardrobeItemOut)
async def update_wardrobe_item(item_id: str, payload: WardrobeItemUpdate, user: CurrentUser, db: DbSession):
    item = await _get_owned_item(db, item_id, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.post(
    "/{item_id}/photo",
    response_model=WardrobeItemOut,
    dependencies=[Depends(rate_limiter("wardrobe_photo_upload", limit=40, window_seconds=3600))],
)
async def upload_wardrobe_photo(item_id: str, user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    item = await _get_owned_item(db, item_id, user.id)

    processed = await validate_and_optimize(file)
    key = new_key("users", user.id, "wardrobe", f"{uuid.uuid4().hex}.{processed.ext}")

    storage = get_storage()
    if item.storage_key:
        storage.delete(item.storage_key)
    storage.put(key, processed.content, processed.content_type)

    item.storage_key = key
    item.image_url = storage.signed_url(key)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", response_model=Message)
async def delete_wardrobe_item(item_id: str, user: CurrentUser, db: DbSession):
    item = await _get_owned_item(db, item_id, user.id)
    if item.storage_key:
        get_storage().delete(item.storage_key)
    item.is_deleted = True
    await db.commit()
    return Message(detail="Wardrobe item removed")
