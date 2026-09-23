"""Recording affiliate clicks from places other than a product card."""

from __future__ import annotations

import hashlib

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.affiliate import AffiliateClick
from app.models.enums import AffiliateSource
from app.models.product import Product
from app.models.saved_product import SavedProduct
from app.models.user import User


def hash_ip(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    return hashlib.sha256(ip.encode()).hexdigest()[:32] if ip else None


async def record_saved_click(
    db: AsyncSession,
    request: Request,
    *,
    user: User,
    saved: SavedProduct,
    source: AffiliateSource = AffiliateSource.SAVED,
) -> None:
    """A click from the shopper's saved list.

    A click is only recorded when the catalog row still exists — the
    click table is keyed to it. The redirect happens either way: the
    saved snapshot carries its own affiliate URL, so a sale still earns
    even after we've forgotten the product itself."""
    product = await db.get(Product, saved.product_id) if saved.product_id else None
    if product is None:
        logger.info("affiliate_click_unrecorded", reason="product row gone", saved_product_id=saved.id)
        return
    db.add(
        AffiliateClick(
            user_id=user.id,
            product_id=product.id,
            retailer_id=product.retailer_id,
            source=source,
            session_id=None,
            ip_hash=hash_ip(request),
            user_agent=request.headers.get("user-agent", "")[:512] or None,
            referrer=request.headers.get("referer", "")[:1024] or None,
        )
    )
    await db.commit()
