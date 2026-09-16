"""Thin alias over the product search engine at the URL the spec names
explicitly — GET /api/v1/products already does the same thing (keyword +
filters + pgvector-ready semantic rerank, see services/search_service.py);
this exists so /api/v1/search/* is also a valid entry point without a
second implementation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import DbSession, OptionalUser
from app.models.enums import Gender
from app.schemas.common import Page
from app.schemas.product import LiveProductOut, ProductOut, ProductSearchFilters
from app.services import history_service
from app.services.live_search_service import live_search, to_live_product_out
from app.services.search_service import search_products

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/live", response_model=list[LiveProductOut])
async def search_live(q: str = Query(..., min_length=1), limit: int = Query(default=24, le=48)):
    """Fetched fresh from retailer APIs (eBay today) on every call — never
    reads from or writes to our product catalog. See
    POST /api/v1/products/select-live for turning one result into a real,
    saved product once a user actually picks it."""
    if not q.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="q must not be empty")
    results = await live_search(q.strip(), limit=limit)
    return [to_live_product_out(r) for r in results]


@router.get("", response_model=Page[ProductOut])
async def search(
    db: DbSession,
    user: OptionalUser,
    q: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    color: str | None = None,
    gender: Gender | None = None,
    retailer: str | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    style: str | None = None,
    sort: str = "relevance",
    limit: int = Query(default=24, le=100),
    offset: int = 0,
):
    filters = ProductSearchFilters(
        q=q,
        category=category,
        brand=brand,
        color=color,
        gender=gender,
        retailer=retailer,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        style=style,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items, total = await search_products(db, filters, user_id=user.id if user else None)
    await history_service.log_search(db, user_id=user.id if user else None, filters=filters, result_count=total)
    return Page(items=items, total=total, limit=limit, offset=offset)
