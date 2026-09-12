"""Rakuten Advertising — admin-only operational endpoints.

Mounted under /admin (not a public /retailers/rakuten/* surface) because
every response here is internal business data — which advertisers we're
partnered with, commission terms, raw catalog preview data before it's
been through ingestion's normalization/dedup — never something a shopper
needs directly. Shoppers see Rakuten products the same way they see every
other retailer's: through the existing /api/v1/products and /api/v1/search
endpoints, once ingestion has synced them (see services/
product_ingestion_service.py) — no separate public Rakuten route needed.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import AdminUser
from app.retailers.errors import RetailerNotConfiguredError
from app.retailers.rakuten import RakutenAPIError
from app.retailers.registry import get_rakuten_provider
from app.schemas.rakuten import (
    RakutenAdvertiserOut,
    RakutenCouponOut,
    RakutenOfferOut,
    RakutenPartnershipOut,
    RakutenProductPreviewOut,
    RakutenStatusOut,
)

router = APIRouter(prefix="/admin/rakuten", tags=["admin", "rakuten"])


def _handle_provider_errors(exc: Exception) -> None:
    if isinstance(exc, RetailerNotConfiguredError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, RakutenAPIError):
        # Safe to surface to an admin: RakutenAPIError messages only ever
        # contain Rakuten's own status code/response text, never our
        # credentials (see app/retailers/rakuten.py — the token itself is
        # never interpolated into an error message).
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    raise


@router.get("/status", response_model=RakutenStatusOut)
async def rakuten_status(_: AdminUser):
    provider = get_rakuten_provider()
    return RakutenStatusOut(**provider.describe_configuration())


@router.get("/search", response_model=list[RakutenProductPreviewOut])
async def rakuten_search_preview(_: AdminUser, keyword: str = Query(...), limit: int = Query(default=10, le=50)):
    """A raw, unsaved preview of what Rakuten's Product Search API returns
    for one keyword — for verifying the integration before/without running
    a full catalog sync. Real catalog ingestion happens via
    services/product_ingestion_service.py, not this endpoint."""
    provider = get_rakuten_provider()
    try:
        raw_products = await provider.preview_search(keyword=keyword, limit=limit)
    except (RetailerNotConfiguredError, RakutenAPIError) as exc:
        _handle_provider_errors(exc)
        raise  # unreachable, satisfies type checkers

    return [
        RakutenProductPreviewOut(
            retailer_product_id=p.retailer_product_id,
            name=p.name,
            brand=p.brand,
            merchant_name=p.merchant_name,
            merchant_id=p.merchant_id,
            price_cents=p.price_cents,
            currency=p.currency,
            product_url=p.product_url,
            images=p.images,
            category_slug=p.category_slug,
        )
        for p in raw_products
    ]


@router.get("/advertisers", response_model=list[RakutenAdvertiserOut])
async def rakuten_advertisers(_: AdminUser, keyword: str | None = None, limit: int = Query(default=50, le=200)):
    provider = get_rakuten_provider()
    try:
        advertisers = await provider.list_advertisers(keyword=keyword, limit=limit)
    except (RetailerNotConfiguredError, RakutenAPIError) as exc:
        _handle_provider_errors(exc)
        raise
    return [RakutenAdvertiserOut(**asdict(a)) for a in advertisers]


@router.get("/partnerships", response_model=list[RakutenPartnershipOut])
async def rakuten_partnerships(_: AdminUser, advertiser_ids: str = Query(..., description="Comma-separated advertiser ids to check — confirmed live that this endpoint checks specific advertisers, not a full list")):
    provider = get_rakuten_provider()
    try:
        partnerships = await provider.list_partnerships(advertiser_ids=advertiser_ids.split(","))
    except (RetailerNotConfiguredError, RakutenAPIError) as exc:
        _handle_provider_errors(exc)
        raise
    return [RakutenPartnershipOut(**asdict(p)) for p in partnerships]


@router.get("/offers", response_model=list[RakutenOfferOut])
async def rakuten_offers(_: AdminUser, mid: str | None = None):
    provider = get_rakuten_provider()
    try:
        offers = await provider.list_offers(mid=mid)
    except (RetailerNotConfiguredError, RakutenAPIError) as exc:
        _handle_provider_errors(exc)
        raise
    return [RakutenOfferOut(**asdict(o)) for o in offers]


@router.get("/coupons", response_model=list[RakutenCouponOut])
async def rakuten_coupons(_: AdminUser, mid: str | None = None):
    provider = get_rakuten_provider()
    try:
        coupons = await provider.list_coupons(mid=mid)
    except (RetailerNotConfiguredError, RakutenAPIError) as exc:
        _handle_provider_errors(exc)
        raise
    return [RakutenCouponOut(**asdict(c)) for c in coupons]
