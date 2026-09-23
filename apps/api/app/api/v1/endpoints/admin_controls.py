"""State-changing admin actions. Every mutation here writes an
AdminAuditLog row in the same transaction as the change itself."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.tryon import _LOAD_OPTS as TRYON_LOAD_OPTS
from app.core.config import get_settings
from app.core.deps import AdminUser, DbSession
from app.db.base import new_uuid
from app.models.admin_audit import AdminAuditLog
from app.models.affiliate import AffiliateClick
from app.models.credit import CreditPackage, CreditTransaction
from app.models.enums import CreditReason, JobStatus
from app.models.photo import UserPhoto
from app.models.product import Product
from app.models.retailer import Retailer
from app.models.tryon import TryOnJob
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.retailers.base import ProductProvider
from app.retailers.registry import get_all_providers
from app.schemas.admin import (
    AdminAuditLogOut,
    AdminCreditAdjustment,
    AdminCreditPackageCreate,
    AdminCreditPackageOut,
    AdminCreditPackageUpdate,
    AdminProductOut,
    AdminProductUpdate,
    AdminRetailerOut,
    AdminRetailerUpdate,
    AdminSystemStatus,
    AdminTryOnJobOut,
    AdminUserDetail,
    AdminUserOut,
    AdminUserUpdate,
)
from app.schemas.common import Page
from app.schemas.credit import CreditTransactionOut
from app.schemas.tryon import TryOnJobOut
from app.services import credit_service
from app.services.auth_service import revoke_all_refresh_tokens

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit(
    db: DbSession, admin: User, action: str, target_type: str, target_id: str, detail: dict | None = None
) -> None:
    db.add(
        AdminAuditLog(admin_id=admin.id, action=action, target_type=target_type, target_id=target_id, detail=detail)
    )


# ---------------------------------------------------------------- users


async def _get_user(db: DbSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def _count(db: DbSession, column, *where) -> int:  # noqa: ANN001
    return (await db.execute(select(func.count(column)).where(*where))).scalar_one()


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(user_id: str, _: AdminUser, db: DbSession):
    user = await _get_user(db, user_id)
    txns = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(20)
    )
    return AdminUserDetail(
        user=AdminUserOut.model_validate(user),
        tryon_jobs_total=await _count(db, TryOnJob.id, TryOnJob.user_id == user_id),
        photos_total=await _count(db, UserPhoto.id, UserPhoto.user_id == user_id, UserPhoto.is_deleted.is_(False)),
        wardrobe_items_total=await _count(
            db, WardrobeItem.id, WardrobeItem.user_id == user_id, WardrobeItem.is_deleted.is_(False)
        ),
        affiliate_clicks_total=await _count(db, AffiliateClick.id, AffiliateClick.user_id == user_id),
        recent_transactions=[CreditTransactionOut.model_validate(t) for t in txns.scalars().all()],
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(user_id: str, payload: AdminUserUpdate, admin: AdminUser, db: DbSession):
    user = await _get_user(db, user_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    # an admin locking themselves out (or dropping the last admin role by
    # accident) can't be undone from the panel they just lost access to
    if user.id == admin.id and (changes.get("is_active") is False or changes.get("is_admin") is False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You can't suspend or demote your own account"
        )

    before = {field: getattr(user, field) for field in changes}
    for field, value in changes.items():
        setattr(user, field, value)

    if changes.get("is_active") is False:
        # access tokens are re-checked against is_active on every request;
        # revoking refresh tokens also stops them silently signing back in
        await revoke_all_refresh_tokens(db, user.id)

    if changes:
        _audit(db, admin, "user.update", "user", user.id, {"before": before, "after": changes, "email": user.email})
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/credits", response_model=AdminUserOut)
async def adjust_user_credits(user_id: str, payload: AdminCreditAdjustment, admin: AdminUser, db: DbSession):
    user = await _get_user(db, user_id)
    if payload.amount == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount can't be zero")

    reference_id = new_uuid()
    note = f"Admin ({admin.email}): {payload.note}"[:255]
    common = dict(
        user_id=user.id,
        amount=abs(payload.amount),
        reason=CreditReason.ADMIN_ADJUSTMENT,
        reference_type="admin_adjustment",
        reference_id=reference_id,
        note=note,
    )
    if payload.amount > 0:
        await credit_service.grant(db, **common)
    else:
        await credit_service.debit(db, **common)

    _audit(
        db,
        admin,
        "user.credits",
        "user",
        user.id,
        {"amount": payload.amount, "note": payload.note, "email": user.email},
    )
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------- try-on jobs


@router.post("/tryon-jobs/{job_id}/cancel", response_model=AdminTryOnJobOut)
async def cancel_tryon_job(job_id: str, admin: AdminUser, db: DbSession):
    job = await db.get(TryOnJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on job not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.PROCESSING):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job already finished")

    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = "Cancelled by an admin"
    await credit_service.refund(
        db,
        user_id=job.user_id,
        amount=job.credit_cost,
        reference_type="tryon_job",
        reference_id=job.id,
        note="Refund — cancelled by admin",
    )
    _audit(db, admin, "tryon.cancel", "tryon_job", job.id, {"user_id": job.user_id, "refunded": job.credit_cost})
    await db.commit()

    result = await db.execute(
        select(TryOnJob).where(TryOnJob.id == job_id).options(*TRYON_LOAD_OPTS, selectinload(TryOnJob.user))
    )
    reloaded = result.scalar_one()
    return AdminTryOnJobOut(
        **TryOnJobOut.model_validate(reloaded).model_dump(),
        user_email=reloaded.user.email if reloaded.user else None,
    )


# ---------------------------------------------------------------- products


def _product_out(p: Product) -> AdminProductOut:
    return AdminProductOut(
        id=p.id,
        name=p.name,
        brand=p.brand,
        retailer_slug=p.retailer.slug,
        retailer_name=p.retailer.name,
        price_cents=p.price_cents,
        currency=p.currency,
        image_url=p.primary_image_url,
        product_url=p.product_url,
        is_active=p.is_active,
        created_at=p.created_at,
    )


@router.get("/products", response_model=Page[AdminProductOut])
async def list_products(
    _: AdminUser,
    db: DbSession,
    q: str | None = None,
    retailer: str | None = None,
    active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(Product).join(Retailer, Product.retailer_id == Retailer.id)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Product.name).like(like), func.lower(Product.brand).like(like)))
    if retailer:
        stmt = stmt.where(Retailer.slug == retailer)
    if active is not None:
        stmt = stmt.where(Product.is_active.is_(active))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(
        stmt.options(selectinload(Product.images), selectinload(Product.retailer))
        .order_by(Product.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page(items=[_product_out(p) for p in result.scalars().all()], total=total, limit=limit, offset=offset)


@router.patch("/products/{product_id}", response_model=AdminProductOut)
async def update_product(product_id: str, payload: AdminProductUpdate, admin: AdminUser, db: DbSession):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images), selectinload(Product.retailer))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    product.is_active = payload.is_active
    _audit(
        db,
        admin,
        "product.show" if payload.is_active else "product.hide",
        "product",
        product.id,
        {"name": product.name, "retailer": product.retailer.slug},
    )
    await db.commit()
    return _product_out(product)


# ---------------------------------------------------------------- retailers


def _credential_status(slug: str) -> tuple[bool, bool | None]:
    """(credentials configured, commission tracking configured) — read from
    settings only; never exposes the values themselves."""
    s = get_settings()
    return {
        "ebay": (bool(s.EBAY_CLIENT_ID and s.EBAY_CLIENT_SECRET), bool(s.EBAY_CAMPAIGN_ID)),
        # the two halves are independent: the Associate ID earns commission
        # on any link we build, while PA-API keys are what let us *find*
        # products at all — an account can have the first without the second
        "amazon": (bool(s.AMAZON_ACCESS_KEY and s.AMAZON_SECRET_KEY), bool(s.AMAZON_PARTNER_TAG)),
        "cj": (bool(s.CJ_API_TOKEN and s.CJ_WEBSITE_ID), None),
        "rakuten": (bool(s.RAKUTEN_ENABLED and s.RAKUTEN_CLIENT_ID), None),
        "flipkart": (bool(s.FLIPKART_AFFILIATE_ID and s.FLIPKART_AFFILIATE_TOKEN), None),
        "daraz": (bool(s.DARAZ_API_KEY), None),
    }.get(slug, (False, None))


def _integration_built(provider: ProductProvider) -> bool:
    return type(provider).search_live is not ProductProvider.search_live


@router.get("/retailers", response_model=list[AdminRetailerOut])
async def list_retailers(_: AdminUser, db: DbSession):
    rows = {
        r.slug: r
        for r in (await db.execute(select(Retailer).options(selectinload(Retailer.network)))).scalars().all()
    }
    counts = dict(
        (await db.execute(select(Product.retailer_id, func.count(Product.id)).group_by(Product.retailer_id))).all()
    )

    out: list[AdminRetailerOut] = []
    seen: set[str] = set()
    for provider in get_all_providers():
        seen.add(provider.slug)
        row = rows.get(provider.slug)
        creds, tracking = _credential_status(provider.slug)
        out.append(
            AdminRetailerOut(
                slug=provider.slug,
                name=row.name if row else provider.display_name,
                is_active=row.is_active if row else True,
                base_commission_pct=row.base_commission_pct if row else None,
                affiliate_network=(row.network.name if row.network else row.affiliate_network) if row else None,
                integration_built=_integration_built(provider),
                credentials_configured=creds,
                commission_tracking_configured=tracking,
                saved_products=counts.get(row.id, 0) if row else 0,
            )
        )
    for slug, row in rows.items():
        if slug in seen:
            continue
        out.append(
            AdminRetailerOut(
                slug=slug,
                name=row.name,
                is_active=row.is_active,
                base_commission_pct=row.base_commission_pct,
                affiliate_network=row.network.name if row.network else row.affiliate_network,
                integration_built=False,
                credentials_configured=False,
                commission_tracking_configured=None,
                saved_products=counts.get(row.id, 0),
            )
        )
    return out


@router.patch("/retailers/{slug}", response_model=list[AdminRetailerOut])
async def update_retailer(slug: str, payload: AdminRetailerUpdate, admin: AdminUser, db: DbSession):
    row = (await db.execute(select(Retailer).where(Retailer.slug == slug))).scalar_one_or_none()
    if row is None:
        provider = next((p for p in get_all_providers() if p.slug == slug), None)
        if provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retailer not found")
        # a retailer with no saved products yet has no row — create one so
        # it can still be disabled before anything is ever persisted from it
        row = Retailer(slug=provider.slug, name=provider.display_name)
        db.add(row)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(row, field, value)
    _audit(db, admin, "retailer.update", "retailer", slug, changes)
    await db.commit()
    return await list_retailers(admin, db)


# ---------------------------------------------------------------- credit packages


@router.get("/credit-packages", response_model=list[AdminCreditPackageOut])
async def list_credit_packages(_: AdminUser, db: DbSession):
    result = await db.execute(select(CreditPackage).order_by(CreditPackage.price_cents))
    return list(result.scalars().all())


@router.post("/credit-packages", response_model=AdminCreditPackageOut, status_code=status.HTTP_201_CREATED)
async def create_credit_package(payload: AdminCreditPackageCreate, admin: AdminUser, db: DbSession):
    package = CreditPackage(**payload.model_dump() | {"currency": payload.currency.lower()})
    db.add(package)
    await db.flush()
    _audit(db, admin, "credit_package.create", "credit_package", package.id, payload.model_dump())
    await db.commit()
    await db.refresh(package)
    return package


@router.patch("/credit-packages/{package_id}", response_model=AdminCreditPackageOut)
async def update_credit_package(
    package_id: str, payload: AdminCreditPackageUpdate, admin: AdminUser, db: DbSession
):
    package = await db.get(CreditPackage, package_id)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit package not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(package, field, value)
    _audit(db, admin, "credit_package.update", "credit_package", package.id, changes)
    await db.commit()
    await db.refresh(package)
    return package


# ---------------------------------------------------------------- system + audit


@router.get("/system", response_model=AdminSystemStatus)
async def system_status(_: AdminUser):
    s = get_settings()
    return AdminSystemStatus(
        env=s.ENV,
        tryon_provider=s.VIRTUAL_TRYON_PROVIDER,
        fashn_model=s.FASHN_MODEL,
        llm_provider=s.LLM_PROVIDER,
        payment_provider=s.PAYMENT_PROVIDER,
        email_provider=s.EMAIL_PROVIDER,
        storage="s3" if s.S3_ENDPOINT_URL else "local disk",
        job_queue="redis" if s.REDIS_URL else "in-process",
        signup_free_credits=s.SIGNUP_FREE_CREDITS,
        tryon_credit_cost=s.TRYON_CREDIT_COST,
        outfit_tryon_credit_cost=s.OUTFIT_TRYON_CREDIT_COST,
    )


@router.get("/audit-log", response_model=Page[AdminAuditLogOut])
async def list_audit_log(_: AdminUser, db: DbSession, limit: int = 50, offset: int = 0):
    total = (await db.execute(select(func.count(AdminAuditLog.id)))).scalar_one()
    result = await db.execute(
        select(AdminAuditLog)
        .options(selectinload(AdminAuditLog.admin))
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        AdminAuditLogOut(
            id=row.id,
            admin_email=row.admin.email if row.admin else None,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            detail=row.detail,
            created_at=row.created_at,
        )
        for row in result.scalars().all()
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)
