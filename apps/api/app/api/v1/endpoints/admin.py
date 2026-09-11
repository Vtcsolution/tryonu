from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import AdminUser, DbSession
from app.models.affiliate import AffiliateClick
from app.models.ai_usage import AIUsage
from app.models.enums import JobStatus, PaymentStatus, SubscriptionStatus
from app.models.product import Product
from app.models.retailer import Retailer
from app.models.subscription import Payment, Subscription
from app.models.tryon import TryOnJob
from app.models.user import User
from app.schemas.admin import AdminOverview
from app.schemas.common import Page
from app.schemas.tryon import TryOnJobOut
from app.schemas.user import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
async def overview(_: AdminUser, db: DbSession):
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d1 = now - timedelta(days=1)
    d30 = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    new_users_7d = (await db.execute(select(func.count(User.id)).where(User.created_at >= d7))).scalar_one()

    active_subscriptions = (
        await db.execute(select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.ACTIVE))
    ).scalar_one()

    total_credits_outstanding = (await db.execute(select(func.coalesce(func.sum(User.credits_balance), 0)))).scalar_one()

    tryon_jobs_total = (await db.execute(select(func.count(TryOnJob.id)))).scalar_one()
    tryon_jobs_24h = (await db.execute(select(func.count(TryOnJob.id)).where(TryOnJob.created_at >= d1))).scalar_one()
    tryon_jobs_failed_24h = (
        await db.execute(
            select(func.count(TryOnJob.id)).where(TryOnJob.created_at >= d1, TryOnJob.status == JobStatus.FAILED)
        )
    ).scalar_one()

    status_rows = await db.execute(select(TryOnJob.status, func.count(TryOnJob.id)).group_by(TryOnJob.status))
    tryon_jobs_by_status = {s.value: c for s, c in status_rows.all()}

    total_products = (await db.execute(select(func.count(Product.id)).where(Product.is_active.is_(True)))).scalar_one()
    active_retailers = (await db.execute(select(func.count(Retailer.id)).where(Retailer.is_active.is_(True)))).scalar_one()

    affiliate_clicks_total = (await db.execute(select(func.count(AffiliateClick.id)))).scalar_one()
    affiliate_clicks_7d = (
        await db.execute(select(func.count(AffiliateClick.id)).where(AffiliateClick.created_at >= d7))
    ).scalar_one()

    revenue_cents_total = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(Payment.status == PaymentStatus.SUCCEEDED)
        )
    ).scalar_one()
    revenue_cents_30d = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                Payment.status == PaymentStatus.SUCCEEDED, Payment.created_at >= d30
            )
        )
    ).scalar_one()

    ai_cost_usd_cents_30d = (
        await db.execute(select(func.coalesce(func.sum(AIUsage.cost_usd_cents), 0.0)).where(AIUsage.created_at >= d30))
    ).scalar_one()
    ai_calls_30d = (await db.execute(select(func.count(AIUsage.id)).where(AIUsage.created_at >= d30))).scalar_one()

    return AdminOverview(
        total_users=total_users,
        new_users_7d=new_users_7d,
        active_subscriptions=active_subscriptions,
        total_credits_outstanding=total_credits_outstanding,
        tryon_jobs_total=tryon_jobs_total,
        tryon_jobs_24h=tryon_jobs_24h,
        tryon_jobs_failed_24h=tryon_jobs_failed_24h,
        tryon_jobs_by_status=tryon_jobs_by_status,
        total_products=total_products,
        active_retailers=active_retailers,
        affiliate_clicks_total=affiliate_clicks_total,
        affiliate_clicks_7d=affiliate_clicks_7d,
        revenue_cents_total=revenue_cents_total,
        revenue_cents_30d=revenue_cents_30d,
        ai_cost_usd_cents_30d=ai_cost_usd_cents_30d,
        ai_calls_30d=ai_calls_30d,
    )


@router.get("/users", response_model=Page[UserOut])
async def list_users(_: AdminUser, db: DbSession, limit: int = 50, offset: int = 0):
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    return Page(items=list(result.scalars().all()), total=total, limit=limit, offset=offset)


@router.get("/tryon-jobs", response_model=Page[TryOnJobOut])
async def list_all_tryon_jobs(
    _: AdminUser, db: DbSession, status_filter: JobStatus | None = None, limit: int = 50, offset: int = 0
):
    from sqlalchemy.orm import selectinload

    stmt = select(TryOnJob)
    if status_filter:
        stmt = stmt.where(TryOnJob.status == status_filter)

    total = len((await db.execute(stmt.with_only_columns(TryOnJob.id))).all())
    result = await db.execute(
        stmt.options(
            selectinload(TryOnJob.product).selectinload(Product.images),
            selectinload(TryOnJob.product).selectinload(Product.retailer),
            selectinload(TryOnJob.result),
        )
        .order_by(TryOnJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page(items=list(result.scalars().all()), total=total, limit=limit, offset=offset)


@router.get("/ai-usage")
async def list_ai_usage(_: AdminUser, db: DbSession, limit: int = 50, offset: int = 0):
    result = await db.execute(
        select(AIUsage).order_by(AIUsage.created_at.desc()).limit(limit).offset(offset)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "kind": r.kind.value,
            "provider": r.provider,
            "model": r.model,
            "success": r.success,
            "latency_ms": r.latency_ms,
            "cost_usd_cents": r.cost_usd_cents,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/affiliate-clicks")
async def list_affiliate_clicks(_: AdminUser, db: DbSession, limit: int = 50, offset: int = 0):
    result = await db.execute(
        select(AffiliateClick).order_by(AffiliateClick.created_at.desc()).limit(limit).offset(offset)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "product_id": r.product_id,
            "retailer_id": r.retailer_id,
            "user_id": r.user_id,
            "source": r.source.value,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/retailers")
async def list_retailers(_: AdminUser, db: DbSession):
    from sqlalchemy.orm import selectinload

    result = await db.execute(select(Retailer).options(selectinload(Retailer.network)))
    return [
        {
            "id": r.id,
            "slug": r.slug,
            "name": r.name,
            "is_active": r.is_active,
            "affiliate_network": r.network.name if r.network else r.affiliate_network,
            "base_commission_pct": r.base_commission_pct,
        }
        for r in result.scalars().all()
    ]


@router.get("/payments")
async def list_payments(_: AdminUser, db: DbSession, limit: int = 50, offset: int = 0):
    result = await db.execute(select(Payment).order_by(Payment.created_at.desc()).limit(limit).offset(offset))
    rows = result.scalars().all()
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "amount_cents": p.amount_cents,
            "currency": p.currency,
            "status": p.status.value,
            "provider": p.provider,
            "external_payment_id": p.external_payment_id,
            "created_at": p.created_at,
        }
        for p in rows
    ]
