"""Your size: the member's measurements, and the size they suggest."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.preference import UserPreference
from app.services.size_service import suggest

router = APIRouter(prefix="/users/me/size", tags=["users"])


class MySizeIn(BaseModel):
    gender: str | None = Field(default=None, pattern=r"^(women|men)$")
    height_cm: int | None = Field(default=None, ge=100, le=230)
    weight_kg: int | None = Field(default=None, ge=25, le=250)
    bust_cm: int | None = Field(default=None, ge=50, le=200)
    waist_cm: int | None = Field(default=None, ge=40, le=200)
    hips_cm: int | None = Field(default=None, ge=50, le=200)
    shoe_eu: int | None = Field(default=None, ge=30, le=50)
    fit: str | None = Field(default=None, pattern=r"^(regular|loose|slim)$")


class MySizeOut(MySizeIn):
    suggestion: dict | None = None


def _out(pref: UserPreference | None) -> MySizeOut:
    if pref is None:
        return MySizeOut()
    gender = pref.gender.value if pref.gender is not None and pref.gender.value in ("women", "men") else None
    values = {
        "height_cm": pref.height_cm, "weight_kg": pref.weight_kg, "bust_cm": pref.bust_cm, "waist_cm": pref.waist_cm,
        "hips_cm": pref.hips_cm, "shoe_eu": pref.shoe_eu, "fit": pref.fit,
    }
    found = suggest(gender=gender, **values)
    return MySizeOut(gender=gender, **values, suggestion=found.as_dict() if found else None)


@router.get("", response_model=MySizeOut)
async def my_size(me: CurrentUser, db: DbSession):
    return _out(await db.scalar(select(UserPreference).where(UserPreference.user_id == me.id)))


@router.put("", response_model=MySizeOut)
async def save_my_size(payload: MySizeIn, me: CurrentUser, db: DbSession):
    from app.models.enums import Gender

    pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == me.id))
    if pref is None:
        pref = UserPreference(user_id=me.id)
        db.add(pref)
    data = payload.model_dump()
    gender = data.pop("gender")
    if gender:
        pref.gender = Gender(gender)
    for key, value in data.items():
        setattr(pref, key, value)
    await db.commit()
    await db.refresh(pref)
    return _out(pref)
