from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DbSession, OptionalUser
from app.models.affiliate import AffiliateClick
from app.models.enums import AffiliateSource
from app.models.product import Product
from app.models.retailer import Retailer
from app.models.store import Store
from app.services import store_service, whatsapp
from app.services.price_alert_service import price_text
from app.schemas.affiliate import RecordClickRequest, RecordClickResponse

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


def _hash_ip(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    return hashlib.sha256(ip.encode()).hexdigest()[:32] if ip else None


async def _record_click(
    db: DbSession, request: Request, user: OptionalUser, *, product: Product, source: AffiliateSource, session_id: str | None
) -> None:
    db.add(
        AffiliateClick(
            user_id=user.id if user else None,
            product_id=product.id,
            retailer_id=product.retailer_id,
            source=source,
            session_id=session_id,
            ip_hash=_hash_ip(request),
            user_agent=request.headers.get("user-agent", "")[:512] or None,
            referrer=request.headers.get("referer", "")[:1024] or None,
        )
    )
    await db.commit()


@router.get("/go/{product_id}")
async def go(
    product_id: str,
    request: Request,
    db: DbSession,
    user: OptionalUser,
    source: str = Query(default=AffiliateSource.PRODUCT_CARD.value, max_length=32),
    session_id: str | None = Query(default=None),
):
    """The actual `href` a "Shop Now" button/link points at — records the
    click, then 302s straight to the retailer's affiliate URL. Works with
    plain <a href>, no JS required.

    `source` only says where the click came from: one we don't know is
    counted as a product-card click, never refused — a shopper on their way
    to buy must always reach the shop (saved looks, community posts and
    shared looks once sent labels this list didn't have, and got an error page)."""
    try:
        where = AffiliateSource(source)
    except ValueError:
        where = AffiliateSource.PRODUCT_CARD
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    await _record_click(db, request, user, product=product, source=where, session_id=session_id)
    return RedirectResponse(product.affiliate_url, status_code=status.HTTP_302_FOUND)


async def _whatsapp_store(db: DbSession, product: Product) -> Store | None:
    """The TryOnU store selling this product, when it takes orders on WhatsApp."""
    if not product.merchant_id:
        return None
    retailer = await db.get(Retailer, product.retailer_id)
    if retailer is None or retailer.slug != "stores":
        return None
    store = await db.get(Store, product.merchant_id)
    return store if store is not None and store.whatsapp and store_service.is_live(store) else None


@router.get("/order-options/{product_id}")
async def order_options(product_id: str, db: DbSession):
    """Whether this product can also be ordered on WhatsApp (local stores)."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {"whatsapp": await _whatsapp_store(db, product) is not None}


@router.get("/whatsapp/{product_id}")
async def order_on_whatsapp(
    product_id: str,
    request: Request,
    db: DbSession,
    user: OptionalUser,
    source: str = Query(default=AffiliateSource.PRODUCT_CARD.value, max_length=32),
):
    """Opens WhatsApp with the store, the message already written ("Hi, I'd like
    to order ..."). Counted as a shop click in the store's stats. A store without
    WhatsApp sends the shopper to its own product page instead."""
    try:
        where = AffiliateSource(source)
    except ValueError:
        where = AffiliateSource.PRODUCT_CARD
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    store = await _whatsapp_store(db, product)
    await _record_click(db, request, user, product=product, source=where, session_id=None)
    if store is None:
        return RedirectResponse(product.affiliate_url, status_code=status.HTTP_302_FOUND)
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    message = (
        f"Hi {store.name}, I'd like to order: {product.name} "
        f"({price_text(product.price_cents, product.currency)}).\n"
        f"{product.product_url}\n"
        f"(I found it on TryOnU: {site}/stores/{store.slug})"
    )
    return RedirectResponse(whatsapp.chat_link(store.whatsapp or "", message), status_code=status.HTTP_302_FOUND)


@router.post("/click", response_model=RecordClickResponse)
async def record_click(payload: RecordClickRequest, request: Request, db: DbSession, user: OptionalUser):
    """SPA-friendly variant: record the click, get the URL back, navigate
    however the frontend wants (new tab, etc.)."""
    result = await db.execute(select(Product).where(Product.id == payload.product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    await _record_click(db, request, user, product=product, source=payload.source, session_id=payload.session_id)
    return RecordClickResponse(redirect_url=product.affiliate_url)
