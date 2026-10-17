"""Share and earn.

Someone opens a shared look (tryonu.app/look/<token>) or an invite link
(tryonu.app/?ref=<code>, or /sell?ref=<code> for stores) and creates an
account: the browser remembers where they came from and claims it once signed
in (claim). The person who shared then earns, once each:

- REFERRAL_TRYON_CREDITS when the friend's first try-on paid with their own
  credits finishes (reward_first_tryon, from the try-on worker);
- the plan's referral_credits when the friend's store buys its first plan
  (reward_store_plan, from every place a store plan payment succeeds);
- REFERRAL_REWARD_CREDITS (off by default) on the friend's first credit
  purchase (reward_first_purchase, from credit_service.grant).
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import CreditReason
from app.models.referral import Referral, ReferralCode
from app.models.shared_look import SharedLook
from app.models.user import User

# only a brand-new account can say who invited it
CLAIM_WINDOW = timedelta(days=3)
_ALPHABET = string.ascii_lowercase + string.digits


def reward_credits() -> int:
    """Extra reward on the friend's first credit purchase (0 = off)."""
    return max(0, get_settings().REFERRAL_REWARD_CREDITS)


def tryon_credits() -> int:
    return max(0, get_settings().REFERRAL_TRYON_CREDITS)


async def code_for(db: AsyncSession, user_id: str) -> str:
    row = await db.scalar(select(ReferralCode).where(ReferralCode.user_id == user_id))
    if row is not None:
        return row.code
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        if await db.scalar(select(ReferralCode.id).where(ReferralCode.code == code)) is None:
            break
    db.add(ReferralCode(user_id=user_id, code=code))
    await db.flush()
    return code


async def _referrer_for(db: AsyncSession, ref: str) -> tuple[str | None, str]:
    ref = (ref or "").strip()[:80]
    if ref.startswith("look:"):
        token = ref[5:]
        owner = await db.scalar(select(SharedLook.user_id).where(SharedLook.token == token))
        return owner, f"look:{token}"[:64]
    owner = await db.scalar(select(ReferralCode.user_id).where(ReferralCode.code == ref.lower()))
    return owner, "link"


async def claim(db: AsyncSession, user: User, ref: str) -> bool:
    """The new account came from this link: remember who shared it (once)."""
    created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > CLAIM_WINDOW:
        return False
    if await db.scalar(select(Referral.id).where(Referral.referred_user_id == user.id)) is not None:
        return False
    referrer_id, source = await _referrer_for(db, ref)
    if not referrer_id or referrer_id == user.id:
        return False
    db.add(Referral(referrer_user_id=referrer_id, referred_user_id=user.id, source=source))
    await db.flush()
    return True


async def reward_first_purchase(db: AsyncSession, buyer_id: str) -> int:
    """The friend bought credits: the person who shared earns, once."""
    from app.services import credit_service

    referral = await db.scalar(
        select(Referral).where(Referral.referred_user_id == buyer_id, Referral.rewarded_at.is_(None)).with_for_update()
    )
    amount = reward_credits()
    if referral is None or amount <= 0:
        return 0
    referral.rewarded_at = datetime.now(timezone.utc)
    referral.reward_credits = (referral.reward_credits or 0) + amount
    await credit_service.grant(
        db,
        user_id=referral.referrer_user_id,
        amount=amount,
        reason=CreditReason.REFERRAL_REWARD,
        reference_type="referral",
        reference_id=referral.id,
        note="A friend you invited bought credits",
    )
    return amount


async def reward_first_tryon(db: AsyncSession, job) -> int:  # noqa: ANN001
    """The friend's first finished try-on, paid with their own credits: the
    person who invited them earns, once. Free try-ons (paid by a store, or the
    developer API) don't count, so an account made only to collect rewards
    has to pay for its try-on first."""
    from app.services import credit_service

    if (job.credit_cost or 0) <= 0:
        return 0
    amount = tryon_credits()
    if amount <= 0:
        return 0
    referral = await db.scalar(
        select(Referral)
        .where(Referral.referred_user_id == job.user_id, Referral.tryon_rewarded_at.is_(None))
        .with_for_update()
    )
    if referral is None:
        return 0
    referral.tryon_rewarded_at = datetime.now(timezone.utc)
    referral.reward_credits = (referral.reward_credits or 0) + amount
    await credit_service.grant(
        db,
        user_id=referral.referrer_user_id,
        amount=amount,
        reason=CreditReason.REFERRAL_REWARD,
        reference_type="referral_tryon",
        reference_id=referral.id,
        note="A friend you invited did their first try-on",
    )
    return amount


async def reward_store_plan(db: AsyncSession, owner_user_id: str, plan) -> int:  # noqa: ANN001
    """The friend's store bought its first plan: the person who invited them
    earns that plan's reward (Basic 10, Standard 20, Premium 30 by default), once."""
    from app.services import credit_service

    amount = max(0, getattr(plan, "referral_credits", 0) or 0)
    if amount <= 0:
        return 0
    referral = await db.scalar(
        select(Referral)
        .where(Referral.referred_user_id == owner_user_id, Referral.store_rewarded_at.is_(None))
        .with_for_update()
    )
    if referral is None:
        return 0
    referral.store_rewarded_at = datetime.now(timezone.utc)
    referral.store_plan_name = (plan.name or "")[:80]
    referral.reward_credits = (referral.reward_credits or 0) + amount
    await credit_service.grant(
        db,
        user_id=referral.referrer_user_id,
        amount=amount,
        reason=CreditReason.REFERRAL_REWARD,
        reference_type="referral_store",
        reference_id=referral.id,
        note=f"A store you invited bought the {plan.name} plan",
    )
    return amount


async def store_plan_rewards(db: AsyncSession) -> list[dict]:
    from app.models.store import StorePlan

    plans = (
        await db.execute(
            select(StorePlan).where(StorePlan.is_active.is_(True), StorePlan.referral_credits > 0).order_by(StorePlan.position)
        )
    ).scalars()
    return [{"plan": p.name, "credits": p.referral_credits} for p in plans]


async def summary(db: AsyncSession, user_id: str) -> dict:
    code = await code_for(db, user_id)
    joined = await db.scalar(select(func.count()).select_from(Referral).where(Referral.referrer_user_id == user_id)) or 0
    bought = (
        await db.scalar(
            select(func.count())
            .select_from(Referral)
            .where(Referral.referrer_user_id == user_id, Referral.rewarded_at.is_not(None))
        )
        or 0
    )
    earned = (
        await db.scalar(select(func.coalesce(func.sum(Referral.reward_credits), 0)).where(Referral.referrer_user_id == user_id))
        or 0
    )
    tried = (
        await db.scalar(
            select(func.count())
            .select_from(Referral)
            .where(Referral.referrer_user_id == user_id, Referral.tryon_rewarded_at.is_not(None))
        )
        or 0
    )
    stores = (
        await db.scalar(
            select(func.count())
            .select_from(Referral)
            .where(Referral.referrer_user_id == user_id, Referral.store_rewarded_at.is_not(None))
        )
        or 0
    )
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    return {
        "code": code,
        "link": f"{site}/?ref={code}",
        "store_link": f"{site}/sell?ref={code}",
        "reward_credits": reward_credits(),
        "tryon_credits": tryon_credits(),
        "store_rewards": await store_plan_rewards(db),
        "friends_joined": int(joined),
        "friends_tried": int(tried),
        "friends_bought": int(bought),
        "stores_bought": int(stores),
        "credits_earned": int(earned),
    }
