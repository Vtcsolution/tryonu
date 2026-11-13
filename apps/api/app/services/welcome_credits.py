"""Free welcome credits (enough for one outfit), once per person.

A new account gets them once its email is confirmed (Google accounts at once),
unless the same person already had them:
- the same mailbox: Gmail ignores dots and "+anything", so a.b+2@gmail.com
  is ab@gmail.com;
- the same browser: the website keeps a random device id and sends it;
- the same network: at most WELCOME_MAX_PER_IP grants per address in
  WELCOME_IP_WINDOW_DAYS (homes and offices share one address, so more than one);
- a throwaway mailbox (mailinator and the like).
A refused account still works and can buy credits; it just starts at 0.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.core.time import as_aware
from app.models.enums import CreditReason
from app.models.user import User
from app.models.welcome_claim import WelcomeClaim
from app.services import credit_service

# accounts made before free credits came back don't collect them by confirming an old email
WELCOME_FROM = datetime(2026, 11, 13, tzinfo=timezone.utc)

_GMAIL = {"gmail.com", "googlemail.com"}
DISPOSABLE = frozenset(
    """mailinator.com guerrillamail.com guerrillamail.net guerrillamailblock.com sharklasers.com grr.la
    10minutemail.com 10minutemail.net tempmail.com temp-mail.org temp-mail.io tempmail.net tempmailo.com
    tempail.com tempr.email yopmail.com yopmail.net yopmail.fr trashmail.com trashmail.de getnada.com nada.email
    maildrop.cc dispostable.com throwawaymail.com fakeinbox.com mintemail.com emailondeck.com mohmal.com
    moakt.com mailnesia.com spamgourmet.com mytemp.email burnermail.io inboxkitten.com mailcatch.com
    discard.email emailfake.com fakemail.net tmail.ws tmpmail.org tmpmail.net 1secmail.com 1secmail.org
    1secmail.net mail.tm mail.gw linshiyouxiang.net minuteinbox.com spambox.us""".split()
)
_DEVICE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def email_key(email: str) -> str:
    local, _, domain = email.strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in _GMAIL:
        local, domain = local.replace(".", ""), "gmail.com"
    return hashlib.sha256(f"{local}@{domain}".encode()).hexdigest()


def is_disposable(email: str) -> bool:
    domain = email.strip().lower().rpartition("@")[2]
    return domain in DISPOSABLE or any(domain.endswith("." + d) for d in DISPOSABLE)


def clean_device(value: str | None) -> str | None:
    return value if value and _DEVICE.match(value) else None


async def _refusal(db: AsyncSession, user: User, key: str, ip: str | None, device: str | None) -> str | None:
    s = get_settings()
    if is_disposable(user.email):
        return "disposable_email"
    granted = select(WelcomeClaim).where(WelcomeClaim.granted.is_(True))
    if (await db.execute(granted.where(WelcomeClaim.email_key == key).limit(1))).first():
        return "same_email"
    if device and (await db.execute(granted.where(WelcomeClaim.device_id == device).limit(1))).first():
        return "same_device"
    if ip:
        since = datetime.now(timezone.utc) - timedelta(days=s.WELCOME_IP_WINDOW_DAYS)
        n = await db.scalar(
            select(func.count()).select_from(WelcomeClaim).where(
                WelcomeClaim.granted.is_(True), WelcomeClaim.ip == ip, WelcomeClaim.created_at >= since
            )
        )
        if (n or 0) >= s.WELCOME_MAX_PER_IP:
            return "same_network"
    return None


async def try_grant(db: AsyncSession, user: User, *, ip: str | None, device: str | None) -> int:
    """Give the welcome credits if this person hasn't had them. Returns the
    credits given (0 when refused or already decided). The caller commits."""
    amount = get_settings().SIGNUP_FREE_CREDITS
    if amount <= 0:
        return 0
    # (not loaded yet on an account made in this request: that one is new)
    created = user.__dict__.get("created_at")
    if created is not None and as_aware(created) < WELCOME_FROM:
        return 0
    if (await db.execute(select(WelcomeClaim.id).where(WelcomeClaim.user_id == user.id))).first():
        return 0  # decided before (one try per account)
    device = clean_device(device)
    key = email_key(user.email)
    reason = await _refusal(db, user, key, ip, device)
    db.add(WelcomeClaim(user_id=user.id, email_key=key, ip=(ip or "")[:64] or None, device_id=device, granted=reason is None, reason=reason or "granted"))
    if reason:
        logger.info("welcome_credits_refused", user_id=user.id, reason=reason)
        return 0
    await credit_service.grant(
        db,
        user_id=user.id,
        amount=amount,
        reason=CreditReason.SIGNUP_BONUS,
        reference_type="user",
        reference_id=user.id,
        note="Welcome: your first outfit is free",
    )
    logger.info("welcome_credits_granted", user_id=user.id, amount=amount)
    return amount
