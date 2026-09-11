from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.deps import DbSession, OptionalUser
from app.models.affiliate import AffiliateClick
from app.models.enums import AffiliateSource
from app.models.product import Product
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
    source: AffiliateSource = AffiliateSource.PRODUCT_CARD,
    session_id: str | None = Query(default=None),
):
    """The actual `href` a "Shop Now" button/link points at — records the
    click, then 302s straight to the retailer's affiliate URL. Works with
    plain <a href>, no JS required."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    await _record_click(db, request, user, product=product, source=source, session_id=session_id)
    return RedirectResponse(product.affiliate_url, status_code=status.HTTP_302_FOUND)


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
