"""Share and earn: a person's invite link and what it earned, and a new
account saying which link it came from."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.services import referral_service

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ReferralSummaryOut(BaseModel):
    code: str
    link: str
    reward_credits: int
    friends_joined: int
    friends_bought: int
    credits_earned: int


class ClaimIn(BaseModel):
    ref: str = Field(min_length=1, max_length=80)


class ClaimOut(BaseModel):
    claimed: bool


@router.get("/me", response_model=ReferralSummaryOut)
async def my_referrals(user: CurrentUser, db: DbSession):
    out = await referral_service.summary(db, user.id)
    await db.commit()  # the invite code is made the first time
    return out


@router.post(
    "/claim",
    response_model=ClaimOut,
    dependencies=[Depends(rate_limiter("referral_claim", limit=20, window_seconds=3600))],
)
async def claim_referral(payload: ClaimIn, user: CurrentUser, db: DbSession):
    claimed = await referral_service.claim(db, user, payload.ref)
    await db.commit()
    return ClaimOut(claimed=claimed)
