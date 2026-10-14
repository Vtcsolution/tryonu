"""Company stores: a company's own account, plan, products and feed; the
admin's approval and plan prices; and the public photos of store products."""

from __future__ import annotations

import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select

from app.core.deps import AdminUser, CurrentUser, DbSession, OptionalUser
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.models.enums import PaymentStatus
from app.models.store import Store, StorePlan, StoreProduct
from app.models.subscription import Payment
from app.models.user import User
from app.payments.base import PaymentsUnavailableError
from app.payments.registry import get_payment_provider
from app.schemas.credit import PurchaseCreditsResponse
from app.schemas.store import (
    AdminGrantPlanIn,
    AdminProductToggleIn,
    AdminStoreDetailOut,
    AdminStoreSummaryOut,
    PublicStoreOut,
    SelectedProductOut,
    StorePaymentOut,
    StoreStatsOut,
    AdminStoreOut,
    AdminStorePlanUpdate,
    AdminStoreStatusIn,
    StoreCreate,
    StoreFeedIn,
    StoreFeedResult,
    StoreOut,
    StorePlanOut,
    StoreProductIn,
    StoreProductOut,
    StoreProductUpdate,
    StoreUpdate,
    SubscriptionStartOut,
    SubscriptionSyncOut,
)
from app.services import store_service as svc
from app.services.image_service import validate_and_optimize
from app.services.safe_fetch import UnsafeURLError, check_public_url
from app.services.storage_service import get_storage, new_key

router = APIRouter(prefix="/stores", tags=["stores"])
admin_router = APIRouter(prefix="/admin/stores", tags=["admin"])


# ------------------------------------------------------------------ helpers


async def _out(db: DbSession, store: Store) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        slug=store.slug,
        country=store.country,
        description=store.description,
        website_url=store.website_url,
        contact_email=store.contact_email,
        logo_url=svc.image_url(store.logo_key) if store.logo_key else None,
        status=store.status,
        status_note=store.status_note,
        plan_code=store.plan_code,
        plan_product_limit=store.plan_product_limit,
        plan_expires_at=store.plan_expires_at,
        plan_active=svc.plan_active(store),
        plan_free=store.plan_free,
        live=svc.is_live(store),
        product_count=await svc.active_product_count(db, store.id),
        feed_url=store.feed_url,
        feed_last_run_at=store.feed_last_run_at,
        feed_last_result=store.feed_last_result,
        auto_renew=store.auto_renew,
        subscription_status=store.subscription_status,
        subscription_plan_code=store.subscription_plan_code,
    )


def _product_out(p: StoreProduct) -> StoreProductOut:
    return StoreProductOut(
        id=p.id, source=p.source, name=p.name, description=p.description, price_cents=p.price_cents,
        currency=p.currency, images=[svc.image_url(i) for i in p.images or []], product_url=p.product_url,
        category=p.category, gender=p.gender, color=p.color, is_active=p.is_active, updated_at=p.updated_at,
    )


async def _my_store(db: DbSession, user: User) -> Store:
    store = await db.scalar(select(Store).where(Store.owner_user_id == user.id))
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You don't have a store yet")
    return store


async def _my_product(db: DbSession, store: Store, product_id: str) -> StoreProduct:
    product = await db.get(StoreProduct, product_id)
    if product is None or product.store_id != store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _check_link(url: str | None, what: str) -> str | None:
    if not url:
        return None
    try:
        return check_public_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{what}: {exc}") from exc


async def _room_check(db: DbSession, store: Store, adding: int = 1) -> None:
    if not svc.plan_active(store):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Unlock a plan to add products.")
    if await svc.active_product_count(db, store.id) + adding > store.plan_product_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your plan allows {store.plan_product_limit} products. Upgrade your plan to add more.",
        )


# ------------------------------------------------------------- public routes


@router.get("/plans", response_model=list[StorePlanOut])
async def list_plans(db: DbSession):
    plans = (
        await db.execute(select(StorePlan).where(StorePlan.is_active.is_(True)).order_by(StorePlan.position))
    ).scalars()
    return [StorePlanOut.model_validate(p, from_attributes=True) for p in plans]


@router.get("/media/{key:path}")
async def store_media(key: str):
    """Store product photos and logos, public and long-cached (keys are unguessable)."""
    if not key.startswith("stores/") or ".." in key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        data = get_storage().read(key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    media_type = mimetypes.guess_type(key)[0] or "image/jpeg"
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ----------------------------------------------------------- company routes


@router.post("", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
async def create_store(payload: StoreCreate, user: CurrentUser, db: DbSession):
    if await db.scalar(select(Store.id).where(Store.owner_user_id == user.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a store")
    store = Store(
        owner_user_id=user.id,
        name=payload.name.strip(),
        slug=await svc.unique_slug(db, payload.name),
        country=payload.country.upper(),
        description=payload.description,
        website_url=_check_link(payload.website_url, "Website"),
        contact_email=payload.contact_email or user.email,
        status="pending",
        plan_product_limit=0,
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return await _out(db, store)


@router.get("/me", response_model=StoreOut)
async def my_store(user: CurrentUser, db: DbSession):
    return await _out(db, await _my_store(db, user))


@router.patch("/me", response_model=StoreOut)
async def update_store(payload: StoreUpdate, user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    data = payload.model_dump(exclude_unset=True)
    if "website_url" in data:
        data["website_url"] = _check_link(data["website_url"], "Website")
    if data.get("country"):
        data["country"] = data["country"].upper()
    for field, value in data.items():
        setattr(store, field, value)
    await db.commit()
    await db.refresh(store)
    return await _out(db, store)


@router.post(
    "/me/logo",
    response_model=StoreOut,
    dependencies=[Depends(rate_limiter("store_logo_upload", limit=20, window_seconds=3600))],
)
async def upload_logo(user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    store = await _my_store(db, user)
    processed = await validate_and_optimize(file)
    key = new_key("stores", store.id, f"logo-{uuid.uuid4().hex}.{processed.ext}")
    storage = get_storage()
    storage.put(key, processed.content, processed.content_type)
    if store.logo_key:
        storage.delete(store.logo_key)
    store.logo_key = key
    await db.commit()
    await db.refresh(store)
    return await _out(db, store)


@router.post("/me/plans/{code}/purchase", response_model=PurchaseCreditsResponse)
async def buy_plan(code: str, user: CurrentUser, db: DbSession):
    """A 30-day pass for the store, paid like a credit package (PayPal). The
    plan is unlocked when PayPal confirms the payment (credits/purchase/{id}/capture)."""
    store = await _my_store(db, user)
    plan = await db.scalar(select(StorePlan).where(StorePlan.code == code, StorePlan.is_active.is_(True)))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    provider = get_payment_provider()
    payment = Payment(
        user_id=user.id,
        amount_cents=plan.price_cents,
        currency=plan.currency,
        status=PaymentStatus.PENDING,
        provider=provider.name,
        store_plan_id=plan.id,
        store_id=store.id,
    )
    db.add(payment)
    await db.flush()
    try:
        checkout = await provider.create_checkout(
            amount_cents=plan.price_cents,
            currency=plan.currency,
            user_id=user.id,
            metadata={
                "payment_id": payment.id,
                "store_plan_id": plan.id,
                "description": f"TryOnU {plan.name} store plan, {plan.duration_days} days",
            },
        )
    except PaymentsUnavailableError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available right now. Nothing was charged; please try again later.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("store_plan_checkout_failed", error=str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="We couldn't start the payment. Nothing was charged."
        ) from exc
    payment.external_payment_id = checkout.external_payment_id
    if checkout.status == "succeeded":  # a provider that settles at once (the mock, in development)
        payment.status = PaymentStatus.SUCCEEDED
        svc.activate_plan(store, plan)
        await db.commit()
        return PurchaseCreditsResponse(payment_id=payment.id, status="succeeded")
    await db.commit()
    return PurchaseCreditsResponse(payment_id=payment.id, status=checkout.status, checkout_url=checkout.checkout_url)


@router.get("/me/products", response_model=list[StoreProductOut])
async def my_products(user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    rows = (
        await db.execute(
            select(StoreProduct).where(StoreProduct.store_id == store.id).order_by(StoreProduct.updated_at.desc()).limit(2000)
        )
    ).scalars()
    return [_product_out(p) for p in rows]


@router.post("/me/products", response_model=StoreProductOut, status_code=status.HTTP_201_CREATED)
async def add_product(payload: StoreProductIn, user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    if payload.is_active:
        await _room_check(db, store)
    elif not svc.plan_active(store):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Unlock a plan to add products.")
    data = payload.model_dump()
    data["product_url"] = _check_link(data["product_url"], "Product link")
    data["currency"] = data["currency"].lower()
    product = StoreProduct(store_id=store.id, source="manual", external_id=f"m-{uuid.uuid4().hex[:16]}", images=[], **data)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _product_out(product)


@router.patch("/me/products/{product_id}", response_model=StoreProductOut)
async def edit_product(product_id: str, payload: StoreProductUpdate, user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    product = await _my_product(db, store, product_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_active") and not product.is_active:
        await _room_check(db, store)
    if "product_url" in data:
        data["product_url"] = _check_link(data["product_url"], "Product link")
    if data.get("currency"):
        data["currency"] = data["currency"].lower()
    for field, value in data.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return _product_out(product)


@router.delete("/me/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    product = await _my_product(db, store, product_id)
    storage = get_storage()
    for entry in product.images or []:
        if entry.startswith("stores/"):
            storage.delete(entry)
    await db.delete(product)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/products/{product_id}/images",
    response_model=StoreProductOut,
    dependencies=[Depends(rate_limiter("store_image_upload", limit=300, window_seconds=3600))],
)
async def add_product_image(product_id: str, user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    store = await _my_store(db, user)
    product = await _my_product(db, store, product_id)
    if len(product.images or []) >= svc.MAX_IMAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"At most {svc.MAX_IMAGES} photos per product.")
    processed = await validate_and_optimize(file)
    key = new_key("stores", store.id, "products", f"{uuid.uuid4().hex}.{processed.ext}")
    get_storage().put(key, processed.content, processed.content_type)
    product.images = [*(product.images or []), key]
    await db.commit()
    await db.refresh(product)
    return _product_out(product)


@router.delete("/me/products/{product_id}/images/{index}", response_model=StoreProductOut)
async def remove_product_image(product_id: str, index: int, user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    product = await _my_product(db, store, product_id)
    images = list(product.images or [])
    if not 0 <= index < len(images):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    removed = images.pop(index)
    if removed.startswith("stores/"):
        get_storage().delete(removed)
    product.images = images
    await db.commit()
    await db.refresh(product)
    return _product_out(product)


@router.put("/me/feed", response_model=StoreOut)
async def set_feed(payload: StoreFeedIn, user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    store.feed_url = _check_link(payload.feed_url, "Feed link")
    await db.commit()
    await db.refresh(store)
    return await _out(db, store)


@router.post(
    "/me/feed/import",
    response_model=StoreFeedResult,
    dependencies=[Depends(rate_limiter("store_feed_import", limit=6, window_seconds=3600))],
)
async def import_feed_now(user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    if not svc.plan_active(store):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Unlock a plan to import products.")
    return StoreFeedResult(result=await svc.import_store_feed(db, store))


# -------------------------------------------------------------- admin routes


@admin_router.get("", response_model=list[AdminStoreOut])
async def admin_list_stores(_: AdminUser, db: DbSession, status_filter: str | None = None):
    query = select(Store, User.email).join(User, User.id == Store.owner_user_id).order_by(Store.created_at.desc())
    if status_filter:
        query = query.where(Store.status == status_filter)
    out = []
    for store, email in (await db.execute(query.limit(500))).all():
        base = await _out(db, store)
        out.append(AdminStoreOut(**base.model_dump(), owner_email=email, created_at=store.created_at))
    return out


@admin_router.post("/{store_id}/status", response_model=AdminStoreOut)
async def admin_set_status(store_id: str, payload: AdminStoreStatusIn, admin: AdminUser, db: DbSession):
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    changed = store.status != payload.status
    store.status = payload.status
    store.status_note = payload.note
    await db.commit()
    await db.refresh(store)
    logger.info("store_status_changed", store_id=store.id, status=store.status, admin_id=admin.id)
    if changed and payload.status in svc.STATUS_EMAILS:
        subject, body = svc.STATUS_EMAILS[payload.status]
        note = f" Reason: {payload.note}" if payload.note else ""
        await svc.notify_owner(db, store, subject, body.format(name=store.name, note=note))
    owner_email = await db.scalar(select(User.email).where(User.id == store.owner_user_id))
    base = await _out(db, store)
    return AdminStoreOut(**base.model_dump(), owner_email=owner_email or "", created_at=store.created_at)


@admin_router.get("/plans", response_model=list[StorePlanOut])
async def admin_list_plans(_: AdminUser, db: DbSession):
    plans = (await db.execute(select(StorePlan).order_by(StorePlan.position))).scalars()
    return [StorePlanOut.model_validate(p, from_attributes=True) for p in plans]


@admin_router.patch("/plans/{plan_id}", response_model=StorePlanOut)
async def admin_update_plan(plan_id: str, payload: AdminStorePlanUpdate, _: AdminUser, db: DbSession):
    plan = await db.get(StorePlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return StorePlanOut.model_validate(plan, from_attributes=True)




# ------------------------------------------------- company: stats, payments, file


async def _payments(db, store_id: str) -> list[StorePaymentOut]:  # noqa: ANN001
    rows = (
        await db.execute(
            select(Payment, StorePlan.name)
            .outerjoin(StorePlan, StorePlan.id == Payment.store_plan_id)
            .where(Payment.store_id == store_id)
            .order_by(Payment.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        StorePaymentOut(
            id=p.id, amount_cents=p.amount_cents, currency=p.currency, status=p.status.value,
            plan_name=name, created_at=p.created_at,
        )
        for p, name in rows
    ]


@router.get("/me/stats", response_model=StoreStatsOut)
async def my_stats(user: CurrentUser, db: DbSession, days: int = 30):
    store = await _my_store(db, user)
    return await svc.store_stats(db, store.id, days=max(1, min(days, 365)))


@router.get("/me/payments", response_model=list[StorePaymentOut])
async def my_payments(user: CurrentUser, db: DbSession):
    store = await _my_store(db, user)
    return await _payments(db, store.id)


@router.post(
    "/me/products/import-file",
    response_model=StoreFeedResult,
    dependencies=[Depends(rate_limiter("store_file_import", limit=20, window_seconds=3600))],
)
async def import_file(user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    """Many products at once from a CSV or JSON file (same columns as a feed)."""
    store = await _my_store(db, user)
    if not svc.plan_active(store):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Unlock a plan to add products.")
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Files up to 10 MB, please.")
    return StoreFeedResult(result=await svc.import_store_file(db, store, data))


# ----------------------------------------------------------- public store page


async def _live_store(db, slug: str) -> Store:  # noqa: ANN001
    store = await db.scalar(select(Store).where(Store.slug == slug))
    if store is None or not svc.is_live(store):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


@router.get("/public/{slug}", response_model=PublicStoreOut)
async def public_store(slug: str, db: DbSession):
    store = await _live_store(db, slug)
    products = (
        await db.execute(
            select(StoreProduct)
            .where(StoreProduct.store_id == store.id, StoreProduct.is_active.is_(True))
            .order_by(StoreProduct.updated_at.desc())
            .limit(1000)
        )
    ).scalars()
    shown = [p for p in products if p.images]
    await svc.record_views(db, [p.id for p in shown])
    return PublicStoreOut(
        name=store.name, slug=store.slug, country=store.country, description=store.description,
        website_url=store.website_url, logo_url=svc.image_url(store.logo_key) if store.logo_key else None,
        products=[_product_out(p) for p in shown],
    )


@router.post(
    "/public/{slug}/products/{product_id}/select",
    response_model=SelectedProductOut,
    dependencies=[Depends(rate_limiter("store_product_select", limit=120, window_seconds=3600))],
)
async def select_store_product(slug: str, product_id: str, db: DbSession, _: OptionalUser):
    """A store product as a saved product, for Try on and Buy (the shop link
    and the try-on both work on saved products)."""
    from app.retailers.stores import StoreProductProvider
    from app.services.product_ingestion_service import persist_single_product

    store = await _live_store(db, slug)
    provider = StoreProductProvider()
    raw = await provider.fetch_by_id(product_id)
    if raw is None or raw.merchant_id != store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product = await persist_single_product(db, provider, raw)
    return SelectedProductOut(product_id=product.id)


# ------------------------------------------------- admin: summary, detail, actions


@admin_router.get("/summary", response_model=AdminStoreSummaryOut)
async def admin_summary(_: AdminUser, db: DbSession):
    by_status = {k: int(v) for k, v in (await db.execute(select(Store.status, func.count()).group_by(Store.status))).all()}
    stores = (await db.execute(select(Store))).scalars().all()
    products = int(await db.scalar(select(func.count()).select_from(StoreProduct).where(StoreProduct.is_active.is_(True))) or 0)
    revenue = {
        cur: int(total or 0)
        for cur, total in (
            await db.execute(
                select(Payment.currency, func.sum(Payment.amount_cents))
                .where(Payment.store_plan_id.is_not(None), Payment.status == PaymentStatus.SUCCEEDED)
                .group_by(Payment.currency)
            )
        ).all()
    }
    return AdminStoreSummaryOut(by_status=by_status, live=sum(1 for s in stores if svc.is_live(s)), products=products, plan_revenue=revenue)


async def _admin_store(db, store_id: str) -> Store:  # noqa: ANN001
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


async def _admin_detail(db, store: Store) -> AdminStoreDetailOut:  # noqa: ANN001
    owner_email = await db.scalar(select(User.email).where(User.id == store.owner_user_id))
    base = await _out(db, store)
    products = (
        await db.execute(select(StoreProduct).where(StoreProduct.store_id == store.id).order_by(StoreProduct.updated_at.desc()).limit(2000))
    ).scalars()
    return AdminStoreDetailOut(
        **base.model_dump(),
        owner_email=owner_email or "",
        created_at=store.created_at,
        stats=StoreStatsOut(**await svc.store_stats(db, store.id)),
        payments=await _payments(db, store.id),
        products=[_product_out(p) for p in products],
    )


@admin_router.get("/{store_id}", response_model=AdminStoreDetailOut)
async def admin_store_detail(store_id: str, _: AdminUser, db: DbSession):
    return await _admin_detail(db, await _admin_store(db, store_id))


@admin_router.post("/{store_id}/plan", response_model=AdminStoreDetailOut)
async def admin_grant_plan(store_id: str, payload: AdminGrantPlanIn, admin: AdminUser, db: DbSession):
    """Give or extend a plan without payment (a partner, a refund, a fix)."""
    store = await _admin_store(db, store_id)
    plan = await db.scalar(select(StorePlan).where(StorePlan.code == payload.plan_code))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    granted = StorePlan(code=plan.code, name=plan.name, price_cents=plan.price_cents, currency=plan.currency,
                        product_limit=plan.product_limit, duration_days=payload.days)
    svc.activate_plan(store, granted, free=True)
    await db.commit()
    await db.refresh(store)
    logger.info("store_plan_granted", store_id=store.id, plan=plan.code, days=payload.days, admin_id=admin.id)
    return await _admin_detail(db, store)


@admin_router.post("/{store_id}/plan/end", response_model=AdminStoreDetailOut)
async def admin_end_plan(store_id: str, admin: AdminUser, db: DbSession):
    """Stop the store's plan now (e.g. a free plan that's over). A PayPal
    auto-renew is not cancelled here; the owner or PayPal does that."""
    store = await _admin_store(db, store_id)
    svc.end_plan(store)
    await db.commit()
    await db.refresh(store)
    logger.info("store_plan_ended", store_id=store.id, admin_id=admin.id)
    return await _admin_detail(db, store)


@admin_router.patch("/{store_id}/products/{product_id}", response_model=AdminStoreDetailOut)
async def admin_toggle_product(store_id: str, product_id: str, payload: AdminProductToggleIn, _: AdminUser, db: DbSession):
    store = await _admin_store(db, store_id)
    product = await _my_product(db, store, product_id)
    product.is_active = payload.is_active
    await db.commit()
    return await _admin_detail(db, store)


@admin_router.delete("/{store_id}/products/{product_id}", response_model=AdminStoreDetailOut)
async def admin_delete_product(store_id: str, product_id: str, _: AdminUser, db: DbSession):
    store = await _admin_store(db, store_id)
    product = await _my_product(db, store, product_id)
    storage = get_storage()
    for entry in product.images or []:
        if entry.startswith("stores/"):
            storage.delete(entry)
    await db.delete(product)
    await db.commit()
    return await _admin_detail(db, store)



# ------------------------------------------------------- auto-renew (PayPal)


def _paypal():  # noqa: ANN202
    from app.payments.paypal_provider import PayPalPaymentProvider

    provider = get_payment_provider()
    if not isinstance(provider, PayPalPaymentProvider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auto-renew needs PayPal to be the payment provider. Unlock the plan for 30 days instead.",
        )
    return provider


@router.post("/me/plans/{code}/subscribe", response_model=SubscriptionStartOut)
async def subscribe_plan(code: str, user: CurrentUser, db: DbSession):
    """Auto-renew: a PayPal subscription that pays for the plan every period.
    The plan unlocks when PayPal confirms the first payment (subscription/sync)."""
    from app.core.config import get_settings

    store = await _my_store(db, user)
    if store.auto_renew and store.subscription_status == "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Auto-renew is already on. Turn it off first to switch plans.",
        )
    plan = await db.scalar(select(StorePlan).where(StorePlan.code == code, StorePlan.is_active.is_(True)))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    provider = _paypal()
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    try:
        product_id, plan_id, key = await provider.store_billing_plan(
            name=plan.name, price_cents=plan.price_cents, currency=plan.currency, days=plan.duration_days,
            product_id=plan.paypal_product_id, plan_id=plan.paypal_plan_id, plan_key=plan.paypal_plan_key,
        )
        plan.paypal_product_id, plan.paypal_plan_id, plan.paypal_plan_key = product_id, plan_id, key
        subscription_id, approve = await provider.start_store_subscription(
            plan_id=plan_id,
            custom_id=store.id,
            return_url=f"{site}/business?subscription=done",
            cancel_url=f"{site}/business?subscription=cancelled",
        )
    except PaymentsUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Payments are not available right now.") from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("store_subscription_start_failed", error=str(exc)[:200])
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="We couldn't start auto-renew with PayPal. Nothing was charged.") from exc
    store.subscription_id = subscription_id
    store.subscription_plan_code = plan.code
    store.subscription_status = "APPROVAL_PENDING"
    store.subscription_last_paid_at = None
    await db.commit()
    return SubscriptionStartOut(checkout_url=approve)


@router.post("/me/subscription/sync", response_model=SubscriptionSyncOut)
async def sync_my_subscription(user: CurrentUser, db: DbSession):
    """Back from PayPal (or 'check now'): PayPal is asked what was paid; the
    browser's word counts for nothing."""
    store = await _my_store(db, user)
    if not store.subscription_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No auto-renew set up")
    try:
        result = await svc.sync_subscription(db, store, _paypal())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("store_subscription_sync_failed", store_id=store.id, error=str(exc)[:200])
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="We couldn't check with PayPal. Try again in a moment.") from exc
    await db.refresh(store)
    return SubscriptionSyncOut(result=result, store=await _out(db, store))


@router.post("/me/subscription/cancel", response_model=StoreOut)
async def cancel_my_subscription(user: CurrentUser, db: DbSession):
    """Turns auto-renew off. The plan stays active until its end date."""
    store = await _my_store(db, user)
    if not store.subscription_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No auto-renew set up")
    try:
        await _paypal().cancel_store_subscription(store.subscription_id, "Turned off by the store owner on TryOnU")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="PayPal couldn't turn auto-renew off. Try again.") from exc
    store.auto_renew = False
    store.subscription_status = "CANCELLED"
    await db.commit()
    await db.refresh(store)
    return await _out(db, store)
