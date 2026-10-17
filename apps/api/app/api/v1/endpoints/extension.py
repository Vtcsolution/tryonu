"""The TryOnU browser extensions.

Shoppers ("TryOnU – Try It On"): on any shop (eBay, AliExpress, a brand's own
site), the product on the page goes onto the person's own TryOnU photo, paid
with their normal TryOnU credits.

Store owners ("TryOnU for Stores"): any product page, their own site included,
becomes a product in their TryOnU store, within their plan's limits.

Both sign in with an extension token made on tryonu.app/extension/connect
(Authorization: Bearer tou_ext_...).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.extension import ExtensionToken
from app.models.outfit import SavedLook
from app.models.photo import UserPhoto
from app.models.product import Product, ProductImage
from app.models.retailer import Retailer
from app.models.store import Store, StoreProduct
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services.safe_fetch import UnsafeURLError, check_public_url

router = APIRouter(prefix="/extension", tags=["browser extension"])

TOKEN_PREFIX = "tou_ext_"
WEB_RETAILER_SLUG = "web"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def extension_user(
    db: DbSession, authorization: Annotated[str | None, Header()] = None
) -> tuple[User, ExtensionToken]:
    raw = authorization.split(" ", 1)[1].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if not raw.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connect the extension to your TryOnU account first.")
    token = await db.scalar(select(ExtensionToken).where(ExtensionToken.token_hash == _hash(raw)))
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This browser was disconnected. Connect it again.")
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This TryOnU account isn't available.")
    token.last_used_at = datetime.now(timezone.utc)
    return user, token


ExtensionAuth = Annotated[tuple[User, ExtensionToken], Depends(extension_user)]


def _public_url(url: str | None) -> str | None:
    """Our own media links are relative (/media/...): the extension needs the full address."""
    if not url:
        return None
    if url.startswith("http"):
        return url
    return f"{get_settings().PUBLIC_API_BASE_URL.rstrip('/')}{url}"


def _check_page_link(url: str, what: str) -> str:
    try:
        check_public_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{what} must be a public web address.") from exc
    return url[:2048]


# ------------------------------------------------------------------ connecting a browser


class ConnectIn(BaseModel):
    kind: str = Field(default="shopper", pattern=r"^(shopper|store)$")
    label: str | None = Field(default=None, max_length=120)


class ConnectOut(BaseModel):
    token: str


class ConnectedBrowserOut(BaseModel):
    id: str
    kind: str
    label: str | None
    created_at: datetime
    last_used_at: datetime | None


@router.post(
    "/token",
    response_model=ConnectOut,
    dependencies=[Depends(rate_limiter("extension_connect", limit=20, window_seconds=3600))],
)
async def connect_browser(payload: ConnectIn, user: CurrentUser, db: DbSession):
    """Signed in on tryonu.app: a token for this browser's extension (shown to it once)."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    db.add(ExtensionToken(user_id=user.id, token_hash=_hash(raw), kind=payload.kind, label=payload.label))
    await db.commit()
    return ConnectOut(token=raw)


@router.get("/tokens", response_model=list[ConnectedBrowserOut])
async def connected_browsers(user: CurrentUser, db: DbSession):
    rows = (
        await db.execute(
            select(ExtensionToken)
            .where(ExtensionToken.user_id == user.id, ExtensionToken.revoked_at.is_(None))
            .order_by(ExtensionToken.created_at.desc())
        )
    ).scalars()
    return [
        ConnectedBrowserOut(id=t.id, kind=t.kind, label=t.label, created_at=t.created_at, last_used_at=t.last_used_at)
        for t in rows
    ]


@router.delete("/tokens", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_all(user: CurrentUser, db: DbSession):
    await db.execute(
        update(ExtensionToken)
        .where(ExtensionToken.user_id == user.id, ExtensionToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_this_browser(auth: ExtensionAuth, db: DbSession):
    _, token = auth
    token.revoked_at = datetime.now(timezone.utc)
    await db.commit()


# ------------------------------------------------------------------ who is signed in


class StoreSummaryOut(BaseModel):
    name: str
    slug: str
    plan_active: bool
    products: int
    product_limit: int


class ExtensionMeOut(BaseModel):
    email: str
    name: str | None
    credits: int
    tryon_cost: int
    has_photo: bool
    store: StoreSummaryOut | None = None


async def _primary_photo(db: DbSession, user_id: str) -> UserPhoto | None:
    photos = (
        await db.execute(
            select(UserPhoto)
            .where(UserPhoto.user_id == user_id, UserPhoto.is_deleted.is_(False))
            .order_by(UserPhoto.created_at.desc())
        )
    ).scalars().all()
    by_kind = {p.kind.value if hasattr(p.kind, "value") else str(p.kind): p for p in reversed(photos)}
    return by_kind.get("front") or by_kind.get("full_body") or (photos[0] if photos else None)


@router.get("/me", response_model=ExtensionMeOut)
async def extension_me(auth: ExtensionAuth, db: DbSession):
    from app.services import store_service as svc

    user, _ = auth
    store = await db.scalar(select(Store).where(Store.owner_user_id == user.id))
    summary = None
    if store is not None:
        summary = StoreSummaryOut(
            name=store.name,
            slug=store.slug,
            plan_active=svc.plan_active(store),
            products=await svc.active_product_count(db, store.id),
            product_limit=store.plan_product_limit or 0,
        )
    out = ExtensionMeOut(
        email=user.email,
        name=user.full_name,
        credits=user.credits_balance,
        tryon_cost=get_settings().TRYON_CREDIT_COST,
        has_photo=(await _primary_photo(db, user.id)) is not None,
        store=summary,
    )
    await db.commit()  # last_used_at
    return out


# ------------------------------------------------------------------ shoppers: try on the product on this page


class PageProductIn(BaseModel):
    image_url: str = Field(min_length=8, max_length=2048)
    page_url: str = Field(min_length=8, max_length=2048)
    name: str = Field(default="", max_length=500)
    price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    currency: str | None = Field(default=None, max_length=8)
    description: str | None = Field(default=None, max_length=4000)


class ExtensionTryOnOut(BaseModel):
    id: str
    status: str  # queued | processing | completed | failed
    result_image_url: str | None = None
    error: str | None = None
    credits_left: int
    product_name: str
    page_url: str
    saved: bool = False


async def _web_retailer(db: DbSession) -> Retailer:
    retailer = await db.scalar(select(Retailer).where(Retailer.slug == WEB_RETAILER_SLUG))
    if retailer is None:
        retailer = Retailer(slug=WEB_RETAILER_SLUG, name="Online stores")
        db.add(retailer)
        await db.flush()
    return retailer


async def _page_product(db: DbSession, payload: PageProductIn) -> Product:
    """The product on the shopper's page, saved once (hidden from catalog search):
    its picture is what the try-on uses, its page is where Shop now goes."""
    page_url = _check_page_link(payload.page_url, "The page")
    image_url = _check_page_link(payload.image_url, "The product picture")
    retailer = await _web_retailer(db)
    key = hashlib.sha1(f"{page_url}|{image_url}".encode()).hexdigest()
    product = await db.scalar(
        select(Product).where(Product.retailer_id == retailer.id, Product.retailer_product_id == key)
    )
    host = (urlparse(page_url).hostname or "").removeprefix("www.")
    if product is None:
        product = Product(retailer_id=retailer.id, retailer_product_id=key)
        db.add(product)
    product.name = (payload.name or "").strip()[:500] or f"Product from {host}"
    product.merchant_name = host[:255] or None
    product.description = payload.description
    product.price_cents = payload.price_cents or 0
    product.currency = (payload.currency or "usd").lower()[:8]
    product.product_url = page_url
    product.affiliate_url = page_url
    # only ever reached through this person's try-on; never shown in search or suggestions
    product.is_active = False
    await db.flush()
    existing = await db.scalar(select(ProductImage.id).where(ProductImage.product_id == product.id))
    if existing is None:
        db.add(ProductImage(product_id=product.id, url=image_url, position=0, is_primary=True))
        await db.flush()
    return product


async def _tryon_out(db: DbSession, job: TryOnJob, user: User) -> ExtensionTryOnOut:
    from app.models.enums import JobStatus

    product = await db.get(Product, job.product_id) if job.product_id else None
    saved = False
    if job.result is not None:
        saved = (
            await db.scalar(
                select(SavedLook.id).where(SavedLook.user_id == user.id, SavedLook.tryon_result_id == job.result.id)
            )
        ) is not None
    if job.status == JobStatus.COMPLETED and job.result is not None:
        state = "completed"
    elif job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
        state = "failed"
    elif job.status == JobStatus.QUEUED:
        state = "queued"
    else:
        state = "processing"
    await db.refresh(user, attribute_names=["credits_balance"])
    return ExtensionTryOnOut(
        id=job.id,
        status=state,
        result_image_url=_public_url(job.result.image_url) if job.result else None,
        error=job.error_message if state == "failed" else None,
        credits_left=user.credits_balance,
        product_name=product.name if product else "Product",
        page_url=product.product_url if product else "",
        saved=saved,
    )


async def _load(db: DbSession, job_id: str, user: User) -> TryOnJob:
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.result)))
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on not found")
    return job


@router.post(
    "/tryon",
    response_model=ExtensionTryOnOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("extension_tryon", limit=30, window_seconds=600))],
)
async def extension_tryon(payload: PageProductIn, auth: ExtensionAuth, db: DbSession):
    from app.api.v1.endpoints.tryon import _create_one_job

    user, _ = auth
    photo = await _primary_photo(db, user.id)
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add a photo of yourself on tryonu.app first (Try-on studio), then try again.",
        )
    product = await _page_product(db, payload)
    job_id = await _create_one_job(
        db,
        user,
        photo=photo,
        product_id=product.id,
        outfit_id=None,
        wardrobe_item_id=None,
        cost=get_settings().TRYON_CREDIT_COST,
    )
    return await _tryon_out(db, await _load(db, job_id, user), user)


@router.get("/tryon/{job_id}", response_model=ExtensionTryOnOut)
async def extension_tryon_status(job_id: str, auth: ExtensionAuth, db: DbSession):
    user, _ = auth
    out = await _tryon_out(db, await _load(db, job_id, user), user)
    await db.commit()
    return out


@router.get("/tryons", response_model=list[ExtensionTryOnOut])
async def extension_recent(auth: ExtensionAuth, db: DbSession, limit: int = 5):
    """The person's latest try-ons made with the extension."""
    user, _ = auth
    retailer = await db.scalar(select(Retailer).where(Retailer.slug == WEB_RETAILER_SLUG))
    if retailer is None:
        return []
    jobs = (
        await db.execute(
            select(TryOnJob)
            .join(Product, Product.id == TryOnJob.product_id)
            .where(TryOnJob.user_id == user.id, Product.retailer_id == retailer.id)
            .options(selectinload(TryOnJob.result))
            .order_by(TryOnJob.created_at.desc())
            .limit(min(max(limit, 1), 20))
        )
    ).scalars().all()
    out = [await _tryon_out(db, j, user) for j in jobs]
    await db.commit()
    return out


@router.post("/tryon/{job_id}/save", response_model=ExtensionTryOnOut)
async def extension_save_look(job_id: str, auth: ExtensionAuth, db: DbSession):
    """Keep the finished look in the person's Saved looks on tryonu.app."""
    user, _ = auth
    job = await _load(db, job_id, user)
    if job.result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This try-on isn't finished yet.")
    exists = await db.scalar(
        select(SavedLook.id).where(SavedLook.user_id == user.id, SavedLook.tryon_result_id == job.result.id)
    )
    if exists is None:
        product = await db.get(Product, job.product_id) if job.product_id else None
        db.add(SavedLook(user_id=user.id, tryon_result_id=job.result.id, title=(product.name if product else None)))
        await db.commit()
    return await _tryon_out(db, job, user)


# ------------------------------------------------------------------ store owners: add the product on this page


class StoreProductFromPageIn(BaseModel):
    name: str = Field(min_length=2, max_length=512)
    price_cents: int = Field(gt=0, le=100_000_000)
    currency: str = Field(default="usd", min_length=3, max_length=8)
    product_url: str = Field(min_length=8, max_length=2048)
    image_url: str = Field(min_length=8, max_length=2048)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=120)
    gender: str = Field(default="unisex", pattern=r"^(women|men|unisex|girls|boys)$")


class StoreProductAddedOut(BaseModel):
    id: str
    name: str
    products: int
    product_limit: int
    dashboard_url: str


@router.post(
    "/store/products",
    response_model=StoreProductAddedOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("extension_store_add", limit=120, window_seconds=3600))],
)
async def extension_add_store_product(payload: StoreProductFromPageIn, auth: ExtensionAuth, db: DbSession):
    import uuid

    from app.services import store_service as svc

    user, _ = auth
    store = await db.scalar(select(Store).where(Store.owner_user_id == user.id))
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You don't have a TryOnU store yet. Open one at tryonu.app/sell.")
    if not svc.plan_active(store):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Unlock a plan to add products.")
    used = await svc.active_product_count(db, store.id)
    if used + 1 > (store.plan_product_limit or 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your plan allows {store.plan_product_limit} products. Upgrade your plan to add more.",
        )
    product_url = _check_page_link(payload.product_url, "The product link")
    image_url = _check_page_link(payload.image_url, "The product picture")
    duplicate = await db.scalar(
        select(StoreProduct.id).where(StoreProduct.store_id == store.id, StoreProduct.product_url == product_url)
    )
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This product is already in your store.")
    product = StoreProduct(
        store_id=store.id,
        source="manual",
        external_id=f"x-{uuid.uuid4().hex[:16]}",
        name=payload.name.strip(),
        description=payload.description,
        price_cents=payload.price_cents,
        currency=payload.currency.lower(),
        product_url=product_url,
        category=payload.category,
        gender=payload.gender,
        images=[image_url],
        is_active=True,
    )
    db.add(product)
    await db.commit()
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    return StoreProductAddedOut(
        id=product.id,
        name=product.name,
        products=used + 1,
        product_limit=store.plan_product_limit or 0,
        dashboard_url=f"{site}/business#products",
    )
