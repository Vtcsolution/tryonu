"""Company stores: a company's own account, plan, products and feed; the
admin's approval and plan prices; and the public photos of store products."""

from __future__ import annotations

import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.core.deps import AdminUser, CurrentUser, DbSession
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
        live=svc.is_live(store),
        product_count=await svc.active_product_count(db, store.id),
        feed_url=store.feed_url,
        feed_last_run_at=store.feed_last_run_at,
        feed_last_result=store.feed_last_result,
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
    store.status = payload.status
    store.status_note = payload.note
    await db.commit()
    await db.refresh(store)
    logger.info("store_status_changed", store_id=store.id, status=store.status, admin_id=admin.id)
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

