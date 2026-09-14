from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.enums import PhotoKind
from app.models.photo import UserPhoto
from app.schemas.common import Message
from app.schemas.photo import FittingProfileStatus, UserPhotoOut
from app.services.image_service import validate_and_optimize
from app.services.storage_service import get_storage, new_key

router = APIRouter(prefix="/photos", tags=["photos"])

MAX_PHOTOS_PER_USER = 10


@router.get("", response_model=list[UserPhotoOut])
async def list_photos(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(UserPhoto)
        .where(UserPhoto.user_id == user.id, UserPhoto.is_deleted.is_(False))
        .order_by(UserPhoto.created_at)
    )
    return list(result.scalars().all())


@router.get("/status", response_model=FittingProfileStatus)
async def fitting_profile_status(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(UserPhoto).where(UserPhoto.user_id == user.id, UserPhoto.is_deleted.is_(False))
    )
    photos = list(result.scalars().all())
    kinds = {p.kind for p in photos}
    has_front = PhotoKind.FRONT in kinds
    has_back = PhotoKind.BACK in kinds
    return FittingProfileStatus(
        photos=photos,
        has_front=has_front,
        has_back=has_back,
        is_ready=has_front and has_back,
    )


@router.post(
    "",
    response_model=UserPhotoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("photo_upload", limit=40, window_seconds=3600))],
)
async def upload_photo(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    kind: PhotoKind = Form(...),
):
    result = await db.execute(
        select(UserPhoto).where(UserPhoto.user_id == user.id, UserPhoto.is_deleted.is_(False))
    )
    existing = list(result.scalars().all())
    if len(existing) >= MAX_PHOTOS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fitting profile already has the maximum of {MAX_PHOTOS_PER_USER} photos",
        )

    processed = await validate_and_optimize(file)
    key = new_key("users", user.id, "photos", f"{uuid.uuid4().hex}.{processed.ext}")

    storage = get_storage()
    storage.put(key, processed.content, processed.content_type)
    url = storage.signed_url(key)

    is_primary = kind in (PhotoKind.FRONT, PhotoKind.FULL_BODY) and not any(
        p.kind == kind for p in existing
    )

    photo = UserPhoto(
        user_id=user.id,
        kind=kind,
        storage_key=key,
        url=url,
        width=processed.width,
        height=processed.height,
        content_type=processed.content_type,
        byte_size=len(processed.content),
        is_primary=is_primary,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


@router.delete("/{photo_id}", response_model=Message)
async def delete_photo(photo_id: str, user: CurrentUser, db: DbSession):
    photo = await db.get(UserPhoto, photo_id)
    if photo is None or photo.user_id != user.id or photo.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    get_storage().delete(photo.storage_key)
    photo.is_deleted = True
    await db.commit()
    return Message(detail="Photo deleted")
