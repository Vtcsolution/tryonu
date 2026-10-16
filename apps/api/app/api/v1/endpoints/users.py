from __future__ import annotations

from sqlalchemy import select

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.core.taxonomy import normalize_selection
from app.models.outfit import SavedLook
from app.models.preference import UserPreference
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult
from app.schemas.common import Message
from app.services.look_products import look_products
from app.schemas.saved_look import SavedLookItemOut, SavedLookOut
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

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("preferred_categories") is not None:
        # unknown ids (e.g. from an older client) are dropped rather than stored
        changes["preferred_categories"] = normalize_selection(changes["preferred_categories"])
    for field, value in changes.items():
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    return pref


@router.get("/me/saved-looks", response_model=list[SavedLookOut])
async def list_saved_looks(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(SavedLook)
        .where(SavedLook.user_id == user.id)
        .options(
            selectinload(SavedLook.tryon_result)
            .selectinload(TryOnResult.job)
            .selectinload(TryOnJob.product)
            .selectinload(Product.images),
            selectinload(SavedLook.tryon_result)
            .selectinload(TryOnResult.job)
            .selectinload(TryOnJob.product)
            .selectinload(Product.retailer),
        )
        .order_by(SavedLook.created_at.desc())
    )
    looks = result.scalars().all()
    out: list[SavedLookOut] = []
    for look in looks:
        job = look.tryon_result.job if look.tryon_result else None
        items: list[SavedLookItemOut] = []
        if job is not None:
            full = await db.scalar(select(TryOnJob).where(TryOnJob.id == job.id).options(selectinload(TryOnJob.result)))
            pairs, drawn = await look_products(db, full)
            items = [
                SavedLookItemOut(
                    id=p.id,
                    name=p.name,
                    price_cents=p.price_cents,
                    currency=p.currency,
                    image_url=p.primary_image_url,
                    shop=p.merchant_name or (p.retailer.name if p.retailer else None),
                    on_photo=None if drawn is None else p.id in drawn,
                )
                for p, _ in pairs
            ]
        same = len({i.currency.lower() for i in items}) == 1
        out.append(
            SavedLookOut(
                id=look.id,
                title=look.title,
                image_url=look.tryon_result.image_url if look.tryon_result else None,
                product=job.product if job else None,
                created_at=look.created_at,
                tryon_job_id=job.id if job else None,
                items=items,
                total_cents=sum(i.price_cents for i in items) if same else None,
                currency=items[0].currency if same else None,
            )
        )
    return out


@router.post("/me/saved-looks/{tryon_result_id}", status_code=status.HTTP_201_CREATED)
async def save_look(tryon_result_id: str, user: CurrentUser, db: DbSession, title: str | None = None):
    result = await db.execute(
        select(TryOnResult).where(TryOnResult.id == tryon_result_id).options(selectinload(TryOnResult.job))
    )
    tryon_result = result.scalar_one_or_none()
    if tryon_result is None or tryon_result.job.user_id != user.id:
        # Same 404 either way — never reveal that a result exists but
        # belongs to someone else.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on result not found")

    # pressing Save twice keeps one copy
    existing = await db.scalar(
        select(SavedLook).where(SavedLook.user_id == user.id, SavedLook.tryon_result_id == tryon_result_id)
    )
    if existing is not None:
        return {"id": existing.id}
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
