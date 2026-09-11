from __future__ import annotations

from sqlalchemy import select

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.outfit import SavedLook
from app.models.preference import UserPreference
from app.models.tryon import TryOnResult
from app.schemas.common import Message
from app.schemas.user import UpdateProfileRequest, UserOut, UserPreferenceOut, UserPreferenceUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UpdateProfileRequest, user: CurrentUser, db: DbSession):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me/preferences", response_model=UserPreferenceOut)
async def get_preferences(user: CurrentUser, db: DbSession):
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = UserPreference(user_id=user.id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


@router.put("/me/preferences", response_model=UserPreferenceOut)
async def update_preferences(payload: UserPreferenceUpdate, user: CurrentUser, db: DbSession):
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = UserPreference(user_id=user.id)
        db.add(pref)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    return pref


@router.get("/me/saved-looks")
async def list_saved_looks(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(SavedLook)
        .where(SavedLook.user_id == user.id)
        .options(selectinload(SavedLook.tryon_result))
        .order_by(SavedLook.created_at.desc())
    )
    looks = result.scalars().all()
    return [
        {
            "id": look.id,
            "title": look.title,
            "image_url": look.tryon_result.image_url if look.tryon_result else None,
            "created_at": look.created_at,
        }
        for look in looks
    ]


@router.post("/me/saved-looks/{tryon_result_id}", status_code=status.HTTP_201_CREATED)
async def save_look(tryon_result_id: str, user: CurrentUser, db: DbSession, title: str | None = None):
    result = await db.get(TryOnResult, tryon_result_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on result not found")

    look = SavedLook(user_id=user.id, tryon_result_id=tryon_result_id, title=title)
    db.add(look)
    await db.commit()
    await db.refresh(look)
    return {"id": look.id}


@router.delete("/me/saved-looks/{look_id}", response_model=Message)
async def unsave_look(look_id: str, user: CurrentUser, db: DbSession):
    look = await db.get(SavedLook, look_id)
    if look is None or look.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved look not found")
    await db.delete(look)
    await db.commit()
    return Message(detail="Removed")
