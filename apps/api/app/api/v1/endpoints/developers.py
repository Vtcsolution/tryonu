"""The Developer API.

- /developers/...        the developer portal (signed-in users): account, keys, packs, usage
- /public/tryons ...     the API developers call from their servers, with a secret key
- /admin/developers/...  admins: accounts, credits, packs
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.models.developer import DeveloperAccount, DeveloperApiKey, DeveloperCreditPack, DeveloperTryOn
from app.models.enums import JobStatus, PaymentStatus
from app.models.subscription import Payment
from app.models.tryon import TryOnJob
from app.models.user import User
from app.payments.base import PaymentsUnavailableError
from app.payments.registry import get_payment_provider
from app.schemas.credit import PurchaseCreditsResponse
from app.schemas.developer import (
    AdminCreditsIn,
    AdminDeveloperOut,
    AdminStatusIn,
    ApiKeyCreatedOut,
    ApiKeyIn,
    ApiKeyOut,
    CreditPackOut,
    CreditPackUpdate,
    DeveloperAccountIn,
    DeveloperAccountOut,
    DeveloperPaymentOut,
    PublicCreditsOut,
    PublicTryOnIn,
    PublicTryOnOut,
    UsageOut,
)
from app.services import developer_service as dev
from app.services.image_service import ProcessedImage, optimize_bytes
from app.services.queue import enqueue_tryon_job
from app.services.safe_fetch import UnsafeURLError, check_public_url, fetch_limited

router = APIRouter(prefix="/developers", tags=["developers"])
public_router = APIRouter(prefix="/public", tags=["developer API"])
admin_router = APIRouter(prefix="/admin/developers", tags=["admin"])

MAX_KEYS = 10


# ------------------------------------------------------------------ helpers


async def _my_account(db: DbSession, user: User) -> DeveloperAccount:
    account = await db.scalar(select(DeveloperAccount).where(DeveloperAccount.user_id == user.id))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You don't have a developer account yet")
    return account


async def _account_out(db: DbSession, account: DeveloperAccount) -> DeveloperAccountOut:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    counted = (DeveloperTryOn.account_id == account.id, DeveloperTryOn.refunded.is_(False))
    total = await db.scalar(select(func.count()).select_from(DeveloperTryOn).where(*counted)) or 0
    recent = await db.scalar(
        select(func.count()).select_from(DeveloperTryOn).where(*counted, DeveloperTryOn.created_at >= since)
    ) or 0
    return DeveloperAccountOut(
        id=account.id, company_name=account.company_name, website=account.website, credits=account.credits,
        status=account.status, tryons_total=total, tryons_30d=recent, created_at=account.created_at,
    )


def _key_out(key: DeveloperApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id, name=key.name, kind=key.kind, prefix=key.prefix, allowed_domains=key.allowed_domains or [],
        last_used_at=key.last_used_at, revoked_at=key.revoked_at, created_at=key.created_at,
    )


def _pack_out(pack: DeveloperCreditPack) -> CreditPackOut:
    return CreditPackOut(
        id=pack.id, code=pack.code, name=pack.name, tryons=pack.tryons, price_cents=pack.price_cents,
        currency=pack.currency, is_active=pack.is_active,
    )


_PUBLIC_STATUS = {
    JobStatus.QUEUED: "queued",
    JobStatus.PROCESSING: "processing",
    JobStatus.COMPLETED: "completed",
    JobStatus.FAILED: "failed",
    JobStatus.CANCELLED: "failed",
}


def _public_status(job: TryOnJob) -> str:
    return _PUBLIC_STATUS.get(job.status, "processing")


# ------------------------------------------------------------------ portal


@router.post("", response_model=DeveloperAccountOut, status_code=status.HTTP_201_CREATED)
async def open_account(payload: DeveloperAccountIn, user: CurrentUser, db: DbSession):
    if await db.scalar(select(DeveloperAccount.id).where(DeveloperAccount.user_id == user.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a developer account")
    account = DeveloperAccount(
        user_id=user.id, company_name=payload.company_name.strip(), website=(payload.website or "").strip() or None
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return await _account_out(db, account)


@router.get("/me", response_model=DeveloperAccountOut)
async def my_account(user: CurrentUser, db: DbSession):
    return await _account_out(db, await _my_account(db, user))


@router.get("/keys", response_model=list[ApiKeyOut])
async def my_keys(user: CurrentUser, db: DbSession):
    account = await _my_account(db, user)
    keys = (
        await db.execute(
            select(DeveloperApiKey).where(DeveloperApiKey.account_id == account.id).order_by(DeveloperApiKey.created_at.desc())
        )
    ).scalars()
    return [_key_out(k) for k in keys]


@router.post("/keys", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def make_key(payload: ApiKeyIn, user: CurrentUser, db: DbSession):
    account = await _my_account(db, user)
    live = await db.scalar(
        select(func.count()).select_from(DeveloperApiKey).where(
            DeveloperApiKey.account_id == account.id, DeveloperApiKey.revoked_at.is_(None)
        )
    )
    if (live or 0) >= MAX_KEYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You can have {MAX_KEYS} keys. Revoke one first.")
    if payload.kind == "public":
        domains = dev.clean_domains(payload.allowed_domains)
        if not domains:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A website key needs your website's domain, for example yourshop.com.",
            )
        raw, digest, prefix = dev.new_public_key()
    else:
        domains = None
        raw, digest, prefix = dev.new_secret_key()
    key = DeveloperApiKey(
        account_id=account.id, name=payload.name.strip(), kind=payload.kind, prefix=prefix, key_hash=digest,
        allowed_domains=domains,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyCreatedOut(**_key_out(key).model_dump(), key=raw)


@router.delete("/keys/{key_id}", response_model=ApiKeyOut)
async def revoke_key(key_id: str, user: CurrentUser, db: DbSession):
    account = await _my_account(db, user)
    key = await db.get(DeveloperApiKey, key_id)
    if key is None or key.account_id != account.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(key)
    return _key_out(key)


@router.get("/packs", response_model=list[CreditPackOut])
async def packs(db: DbSession):
    rows = (
        await db.execute(
            select(DeveloperCreditPack).where(DeveloperCreditPack.is_active.is_(True)).order_by(DeveloperCreditPack.position)
        )
    ).scalars()
    return [_pack_out(p) for p in rows]


@router.post("/packs/{code}/purchase", response_model=PurchaseCreditsResponse)
async def buy_pack(code: str, user: CurrentUser, db: DbSession):
    """A pack of API try-ons, paid like a credit package (PayPal). The credits
    arrive when PayPal confirms the payment (credits/purchase/{id}/capture)."""
    account = await _my_account(db, user)
    pack = await db.scalar(
        select(DeveloperCreditPack).where(DeveloperCreditPack.code == code, DeveloperCreditPack.is_active.is_(True))
    )
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found")
    provider = get_payment_provider()
    payment = Payment(
        user_id=user.id, amount_cents=pack.price_cents, currency=pack.currency, status=PaymentStatus.PENDING,
        provider=provider.name, developer_pack_id=pack.id, developer_account_id=account.id,
    )
    db.add(payment)
    await db.flush()
    try:
        checkout = await provider.create_checkout(
            amount_cents=pack.price_cents,
            currency=pack.currency,
            user_id=user.id,
            metadata={"payment_id": payment.id, "description": f"TryOnU API {pack.name} pack, {pack.tryons} try-ons"},
        )
    except PaymentsUnavailableError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available right now. Nothing was charged; please try again later.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("developer_pack_checkout_failed", error=str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="We couldn't start the payment. Nothing was charged."
        ) from exc
    payment.external_payment_id = checkout.external_payment_id
    if checkout.status == "succeeded":  # a provider that settles at once (the mock, in development)
        payment.status = PaymentStatus.SUCCEEDED
        account.credits += pack.tryons
        await db.commit()
        return PurchaseCreditsResponse(payment_id=payment.id, status="succeeded", developer_tryons=pack.tryons)
    await db.commit()
    return PurchaseCreditsResponse(payment_id=payment.id, status=checkout.status, checkout_url=checkout.checkout_url)


@router.get("/usage", response_model=list[UsageOut])
async def usage(user: CurrentUser, db: DbSession, limit: int = 100):
    account = await _my_account(db, user)
    rows = (
        await db.execute(
            select(DeveloperTryOn, TryOnJob)
            .join(TryOnJob, TryOnJob.id == DeveloperTryOn.tryon_job_id)
            .where(DeveloperTryOn.account_id == account.id)
            .options(selectinload(TryOnJob.result))
            .order_by(DeveloperTryOn.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
    ).all()
    return [
        UsageOut(
            id=job.id, status=_public_status(job), reference=row.reference, credits=row.credits, refunded=row.refunded,
            result_image_url=job.result.image_url if job.result else None,
            error=job.error_message if job.status in (JobStatus.FAILED, JobStatus.CANCELLED) else None,
            created_at=row.created_at,
        )
        for row, job in rows
    ]


@router.get("/payments", response_model=list[DeveloperPaymentOut])
async def my_payments(user: CurrentUser, db: DbSession):
    account = await _my_account(db, user)
    rows = (
        await db.execute(
            select(Payment, DeveloperCreditPack)
            .outerjoin(DeveloperCreditPack, DeveloperCreditPack.id == Payment.developer_pack_id)
            .where(Payment.developer_account_id == account.id)
            .order_by(Payment.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        DeveloperPaymentOut(
            id=p.id, amount_cents=p.amount_cents, currency=p.currency, status=p.status.value,
            pack_name=pack.name if pack else None, tryons=pack.tryons if pack else None, created_at=p.created_at,
        )
        for p, pack in rows
    ]


# ------------------------------------------------------------------ the public API


def _key_from(authorization: str | None, x_api_key: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return (x_api_key or "").strip() or None


async def _image_from(value: object, what: str) -> ProcessedImage:
    """A photo sent as a file, or as a public link we download."""
    try:
        if isinstance(value, UploadFile):
            raw = await value.read()
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            check_public_url(value)  # never a private or internal address
            raw = await asyncio.to_thread(fetch_limited, value, max_bytes=dev.MAX_IMAGE_BYTES, timeout=20.0)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Send {what} as a file or {what}_url as a public https link.",
            )
    except UnsafeURLError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{what}_url must be a public web address.") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Couldn't download {what}_url: {str(exc)[:120]}") from exc
    return await optimize_bytes(raw)


def _public_out(job: TryOnJob, row: DeveloperTryOn, credits_left: int | None = None) -> PublicTryOnOut:
    return PublicTryOnOut(
        id=job.id,
        status=_public_status(job),
        result_image_url=job.result.image_url if job.result else None,
        error=job.error_message if job.status in (JobStatus.FAILED, JobStatus.CANCELLED) else None,
        reference=row.reference,
        credits_used=0 if row.refunded else row.credits,
        credits_left=credits_left,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@public_router.post(
    "/tryons",
    response_model=PublicTryOnOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limiter("developer_api_tryon", limit=600, window_seconds=3600))],
)
async def api_create_tryon(
    request: Request,
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    """Start a try-on: a person photo and a product photo, as files
    (multipart: person_image, garment_image) or links (JSON: person_image_url,
    garment_image_url). Uses 1 credit; a failed try-on gives it back."""
    account, key = await dev.authenticate(db, _key_from(authorization, x_api_key))
    if "application/json" in request.headers.get("content-type", ""):
        try:
            body = PublicTryOnIn(**(await request.json()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON needs person_image_url and garment_image_url (public https links).",
            ) from exc
        person_src, garment_src = body.person_image_url, body.garment_image_url
        garment_name, reference = body.garment_name, body.reference
    else:
        form = await request.form()
        person_src = form.get("person_image") or form.get("person_image_url")
        garment_src = form.get("garment_image") or form.get("garment_image_url")
        garment_name = form.get("garment_name") if isinstance(form.get("garment_name"), str) else None
        reference = form.get("reference") if isinstance(form.get("reference"), str) else None
    person = await _image_from(person_src, "person_image")
    garment = await _image_from(garment_src, "garment_image")

    job = await dev.create_tryon(
        db, account=account, api_key=key, person=person, garment=garment, garment_name=garment_name, reference=reference
    )
    await db.commit()
    enqueue_tryon_job(job.id)
    row = await db.scalar(select(DeveloperTryOn).where(DeveloperTryOn.tryon_job_id == job.id))
    await db.refresh(account)
    loaded = await db.scalar(select(TryOnJob).where(TryOnJob.id == job.id).options(selectinload(TryOnJob.result)))
    return _public_out(loaded, row, credits_left=account.credits)


@public_router.get("/tryons/{tryon_id}", response_model=PublicTryOnOut)
async def api_get_tryon(
    tryon_id: str,
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    account, _ = await dev.authenticate(db, _key_from(authorization, x_api_key))
    row = await db.scalar(
        select(DeveloperTryOn).where(DeveloperTryOn.tryon_job_id == tryon_id, DeveloperTryOn.account_id == account.id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on not found")
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == tryon_id).options(selectinload(TryOnJob.result)))
    await db.commit()  # last_used_at
    return _public_out(job, row)


@public_router.get("/credits", response_model=PublicCreditsOut)
async def api_credits(
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    account, _ = await dev.authenticate(db, _key_from(authorization, x_api_key))
    await db.commit()
    return PublicCreditsOut(credits_left=account.credits)


# ------------------------------------------------------------------ the website widget


def _page_origin(request: Request) -> str | None:
    return request.headers.get("origin") or request.headers.get("referer")


@public_router.post("/widget/tryons", response_model=PublicTryOnOut, status_code=status.HTTP_202_ACCEPTED)
async def widget_create_tryon(request: Request, db: DbSession, x_tryonu_key: str | None = Header(default=None)):
    """A shopper on a TryOnU customer's website tries a product on (the widget).
    Website key, only from the key's own domains, a few try-ons per visitor."""
    from app.core.rate_limit import check_rate_limit

    account, key = await dev.authenticate_public(db, x_tryonu_key, _page_origin(request))
    check_rate_limit(
        request, bucket=f"widget_tryon:{key.id}", limit=max(1, get_settings().WIDGET_TRYONS_PER_VISITOR_HOUR), window_seconds=3600
    )
    form = await request.form()
    person = await _image_from(form.get("person_image"), "person_image")
    garment = await _image_from(form.get("garment_image") or form.get("garment_image_url"), "garment_image")
    garment_name = form.get("garment_name") if isinstance(form.get("garment_name"), str) else None
    job = await dev.create_tryon(
        db, account=account, api_key=key, person=person, garment=garment, garment_name=garment_name,
        reference=f"widget:{(_page_origin(request) or '')[:100]}",
    )
    await db.commit()
    enqueue_tryon_job(job.id)
    row = await db.scalar(select(DeveloperTryOn).where(DeveloperTryOn.tryon_job_id == job.id))
    loaded = await db.scalar(select(TryOnJob).where(TryOnJob.id == job.id).options(selectinload(TryOnJob.result)))
    return _public_out(loaded, row)


@public_router.get("/widget/tryons/{tryon_id}", response_model=PublicTryOnOut)
async def widget_get_tryon(tryon_id: str, request: Request, db: DbSession, x_tryonu_key: str | None = Header(default=None)):
    account, _ = await dev.authenticate_public(db, x_tryonu_key, _page_origin(request))
    row = await db.scalar(
        select(DeveloperTryOn).where(DeveloperTryOn.tryon_job_id == tryon_id, DeveloperTryOn.account_id == account.id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on not found")
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == tryon_id).options(selectinload(TryOnJob.result)))
    await db.commit()
    return _public_out(job, row)


# ------------------------------------------------------------------ admin


@admin_router.get("", response_model=list[AdminDeveloperOut])
async def admin_accounts(_: AdminUser, db: DbSession):
    rows = (
        await db.execute(
            select(DeveloperAccount, User.email).join(User, User.id == DeveloperAccount.user_id).order_by(DeveloperAccount.created_at.desc())
        )
    ).all()
    out = []
    for account, email in rows:
        base = await _account_out(db, account)
        keys = await db.scalar(
            select(func.count()).select_from(DeveloperApiKey).where(
                DeveloperApiKey.account_id == account.id, DeveloperApiKey.revoked_at.is_(None)
            )
        )
        out.append(AdminDeveloperOut(**base.model_dump(), owner_email=email, keys=keys or 0))
    return out


@admin_router.post("/{account_id}/credits", response_model=DeveloperAccountOut)
async def admin_credits(account_id: str, payload: AdminCreditsIn, admin: AdminUser, db: DbSession):
    account = await db.get(DeveloperAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer account not found")
    account.credits = max(0, account.credits + payload.amount)
    await db.commit()
    logger.info("developer_credits_adjusted", account_id=account.id, amount=payload.amount, admin_id=admin.id)
    return await _account_out(db, account)


@admin_router.post("/{account_id}/status", response_model=DeveloperAccountOut)
async def admin_status(account_id: str, payload: AdminStatusIn, admin: AdminUser, db: DbSession):
    account = await db.get(DeveloperAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer account not found")
    account.status = payload.status
    await db.commit()
    logger.info("developer_status_changed", account_id=account.id, status=payload.status, admin_id=admin.id)
    return await _account_out(db, account)


@admin_router.get("/packs", response_model=list[CreditPackOut])
async def admin_packs(_: AdminUser, db: DbSession):
    rows = (await db.execute(select(DeveloperCreditPack).order_by(DeveloperCreditPack.position))).scalars()
    return [_pack_out(p) for p in rows]


@admin_router.patch("/packs/{pack_id}", response_model=CreditPackOut)
async def admin_update_pack(pack_id: str, payload: CreditPackUpdate, _: AdminUser, db: DbSession):
    pack = await db.get(DeveloperCreditPack, pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pack, field, value)
    await db.commit()
    await db.refresh(pack)
    return _pack_out(pack)
