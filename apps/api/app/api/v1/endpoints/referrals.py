"""Share and earn: a person's invite link and what it earned, and a new
account saying which link it came from."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.services import referral_service

router = APIRouter(prefix="/referrals", tags=["referrals"])
admin_router = APIRouter(prefix="/admin/referrals", tags=["admin"])


class StoreRewardOut(BaseModel):
    plan: str
    credits: int


class ReferralSummaryOut(BaseModel):
    code: str
    link: str
    store_link: str
    reward_credits: int  # extra, on a friend's first credit purchase (0 = off)
    tryon_credits: int  # on a friend's first try-on
    store_rewards: list[StoreRewardOut] = []
    friends_joined: int
    friends_tried: int = 0
    friends_bought: int
    stores_bought: int = 0
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


# ------------------------------------------------------------------ admin: who invited whom


class AdminReferralOut(BaseModel):
    id: str
    inviter_email: str
    friend_email: str
    source: str  # "shared look" | "invite link"
    joined_at: datetime
    tried_on_at: datetime | None
    store_plan: str | None
    store_bought_at: datetime | None
    credits_earned: int


class AdminReferralsOut(BaseModel):
    invites: int
    tried_on: int
    stores_bought: int
    credits_paid: int
    rows: list[AdminReferralOut]


@admin_router.get("", response_model=AdminReferralsOut)
async def admin_referrals(_: AdminUser, db: DbSession, limit: int = 300):
    from app.models.referral import Referral
    from app.models.user import User

    inviter = aliased(User)
    friend = aliased(User)
    rows = (
        await db.execute(
            select(Referral, inviter.email, friend.email)
            .join(inviter, inviter.id == Referral.referrer_user_id)
            .join(friend, friend.id == Referral.referred_user_id)
            .order_by(Referral.created_at.desc())
            .limit(min(max(limit, 1), 1000))
        )
    ).all()
    totals = (
        await db.execute(
            select(
                func.count(Referral.id),
                func.count(Referral.tryon_rewarded_at),
                func.count(Referral.store_rewarded_at),
                func.coalesce(func.sum(Referral.reward_credits), 0),
            )
        )
    ).one()
    return AdminReferralsOut(
        invites=int(totals[0] or 0),
        tried_on=int(totals[1] or 0),
        stores_bought=int(totals[2] or 0),
        credits_paid=int(totals[3] or 0),
        rows=[
            AdminReferralOut(
                id=r.id,
                inviter_email=inviter_email,
                friend_email=friend_email,
                source="shared look" if (r.source or "").startswith("look:") else "invite link",
                joined_at=r.created_at,
                tried_on_at=r.tryon_rewarded_at,
                store_plan=r.store_plan_name,
                store_bought_at=r.store_rewarded_at,
                credits_earned=r.reward_credits or 0,
            )
            for r, inviter_email, friend_email in rows
        ],
    )
