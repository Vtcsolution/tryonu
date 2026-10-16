"""Share and earn.

Someone opens a shared look (tryonu.app/look/<token>) or an invite link
(tryonu.app/?ref=<code>) and creates an account: the browser remembers where
they came from and claims it once signed in (claim). When that friend first
buys credits, the person who shared earns REFERRAL_REWARD_CREDITS, once
(reward_first_purchase, called from credit_service.grant on a purchase).
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
    return max(0, get_settings().REFERRAL_REWARD_CREDITS)


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
    referral.reward_credits = amount
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
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    return {
        "code": code,
        "link": f"{site}/?ref={code}",
        "reward_credits": reward_credits(),
        "friends_joined": int(joined),
        "friends_bought": int(bought),
        "credits_earned": int(earned),
    }
