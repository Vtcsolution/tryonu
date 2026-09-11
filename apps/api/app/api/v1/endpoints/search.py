"""Thin alias over the product search engine at the URL the spec names
explicitly — GET /api/v1/products already does the same thing (keyword +
filters + pgvector-ready semantic rerank, see services/search_service.py);
this exists so /api/v1/search/* is also a valid entry point without a
second implementation."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import DbSession
from app.models.enums import Gender
from app.schemas.common import Page
from app.schemas.product import ProductOut, ProductSearchFilters
from app.services.search_service import search_products

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=Page[ProductOut])
async def search(
    db: DbSession,
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
    items, total = await search_products(db, filters)
    return Page(items=items, total=total, limit=limit, offset=offset)
