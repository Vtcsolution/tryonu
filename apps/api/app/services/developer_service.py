"""The Developer API: keys, prepaid credits, and try-ons made for other sites.

A developer's server sends a person photo and a product photo with its secret
key; one credit is taken and the same try-on engine as the shop renders it.
A failed try-on gives the credit back (credit_service.refund -> refund_job).

Developer try-ons don't wait for the operator's FASHN approval: they spend
from an automatic daily allowance (DEV_API_DAILY_TRYON_CAP try-ons a day
across all developers), and only within credits developers paid for.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import new_uuid
from app.models.developer import DeveloperAccount, DeveloperApiKey, DeveloperTryOn
from app.models.enums import JobStatus, PhotoKind
from app.models.photo import UserPhoto
from app.models.tryon import TryOnJob
from app.models.wardrobe import WardrobeItem
from app.services.image_service import ProcessedImage
from app.services.storage_service import get_storage, new_key

SECRET_PREFIX = "tou_sk_"
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def new_secret_key() -> tuple[str, str, str]:
    """(the full key, shown once; what is kept: its fingerprint; and its start to recognise it)."""
    raw = SECRET_PREFIX + secrets.token_urlsafe(32)
    return raw, _hash(raw), raw[:14]


async def authenticate(db: AsyncSession, raw_key: str | None) -> tuple[DeveloperAccount, DeveloperApiKey]:
    if not raw_key or not raw_key.startswith(SECRET_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Send your secret API key as 'Authorization: Bearer tou_sk_...'.",
        )
    key = await db.scalar(select(DeveloperApiKey).where(DeveloperApiKey.key_hash == _hash(raw_key)))
    if key is None or key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This API key is not valid or was revoked.")
    account = await db.get(DeveloperAccount, key.account_id)
    if account is None or account.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This developer account is suspended.")
    key.last_used_at = datetime.now(timezone.utc)
    return account, key


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def tryons_today(db: AsyncSession) -> int:
    """Developer try-ons since midnight (UTC), all developers together, refunds excluded."""
    return int(
        await db.scalar(
            select(func.count())
            .select_from(DeveloperTryOn)
            .where(DeveloperTryOn.created_at >= _today_start(), DeveloperTryOn.refunded.is_(False))
        )
        or 0
    )


async def charge(db: AsyncSession, account_id: str, credits: int = 1) -> bool:
    """Take the credits, or False if there aren't enough. One UPDATE with the
    check inside, so two calls can't spend the last credit twice."""
    result = await db.execute(
        update(DeveloperAccount)
        .where(DeveloperAccount.id == account_id, DeveloperAccount.credits >= credits)
        .values(credits=DeveloperAccount.credits - credits)
    )
    return (result.rowcount or 0) == 1


async def refund_job(db: AsyncSession, job_id: str) -> int:
    """A failed or cancelled API try-on gives its credit back, once."""
    rows = (
        await db.execute(
            select(DeveloperTryOn).where(DeveloperTryOn.tryon_job_id == job_id, DeveloperTryOn.refunded.is_(False))
        )
    ).scalars().all()
    for row in rows:
        row.refunded = True
        await db.execute(
            update(DeveloperAccount)
            .where(DeveloperAccount.id == row.account_id)
            .values(credits=DeveloperAccount.credits + row.credits)
        )
    return len(rows)


async def is_developer_job(db: AsyncSession, job_id: str) -> bool:
    return (await db.scalar(select(DeveloperTryOn.id).where(DeveloperTryOn.tryon_job_id == job_id))) is not None


def _store(user_id: str, folder: str, image: ProcessedImage) -> tuple[str, str]:
    key = new_key("users", user_id, folder, f"{uuid.uuid4().hex}.{image.ext}")
    storage = get_storage()
    storage.put(key, image.content, image.content_type)
    return key, storage.signed_url(key)


async def create_tryon(
    db: AsyncSession,
    *,
    account: DeveloperAccount,
    api_key: DeveloperApiKey | None,
    person: ProcessedImage,
    garment: ProcessedImage,
    garment_name: str | None,
    reference: str | None,
) -> TryOnJob:
    """Charge one credit and queue the try-on (the caller commits and enqueues)."""
    from app.ai.providers.registry import get_tryon_provider

    cap = get_settings().DEV_API_DAILY_TRYON_CAP
    if await tryons_today(db) >= cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="TryOnU's API has reached today's try-on capacity. Nothing was charged; please try again tomorrow.",
        )
    if not await charge(db, account.id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No API credits left. Buy a credit pack in your TryOnU developer portal.",
        )

    user_id = account.user_id
    photo_key, photo_url = _store(user_id, "api-photos", person)
    photo = UserPhoto(
        user_id=user_id,
        kind=PhotoKind.FRONT,
        storage_key=photo_key,
        url=photo_url,
        width=person.width,
        height=person.height,
        content_type=person.content_type,
        byte_size=len(person.content),
        is_primary=False,
        is_deleted=True,  # an API customer's photo, never part of the developer's own fitting profile
    )
    garment_key, garment_url = _store(user_id, "api-garments", garment)
    item = WardrobeItem(
        user_id=user_id,
        name=(garment_name or "Product")[:255],
        storage_key=garment_key,
        is_deleted=True,  # nor of their wardrobe
    )
    item.image_url = garment_url
    db.add_all([photo, item])
    await db.flush()

    provider = get_tryon_provider()
    job = TryOnJob(
        id=new_uuid(),
        user_id=user_id,
        user_photo_id=photo.id,
        wardrobe_item_id=item.id,
        provider=provider.name,
        provider_model=provider.model,
        status=JobStatus.QUEUED,
        credit_cost=0,  # paid with developer credits, not the shopper ledger
        look_round=1,
        queued_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    db.add(
        DeveloperTryOn(
            account_id=account.id,
            api_key_id=api_key.id if api_key else None,
            tryon_job_id=job.id,
            credits=1,
            reference=(reference or None) and reference[:120],
        )
    )
    return job


def allowance_window() -> tuple[datetime, datetime]:
    """Today's automatic FASHN allowance for developer try-ons: midnight to midnight (UTC)."""
    start = _today_start()
    return start, start + timedelta(days=1)
