"""Deterministic catalog lookups for "find similar" / "find cheaper" —
no LLM call needed, which also makes the real-products-only guarantee
trivial here: these are plain DB queries, so there's nothing to invent."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.embeddings import cosine_similarity
from app.models.product import Product

_UNCATEGORIZED_CANDIDATE_CAP = 1000


async def _candidate_pool(db: AsyncSession, exclude_product_id: str, *, category_id: str | None) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.id != exclude_product_id)
        .options(selectinload(Product.images), selectinload(Product.retailer), selectinload(Product.category))
    )
    if category_id:
        # A real category is a natural, much smaller partition of the
        # catalog — no cap needed, and every real ingested product has one
        # (see product_ingestion_service.py). Only the uncategorized
        # fallback below needs a safety cap.
        stmt = stmt.where(Product.category_id == category_id)
    else:
        stmt = stmt.limit(_UNCATEGORIZED_CANDIDATE_CAP)
    return list((await db.execute(stmt)).scalars().unique().all())


async def find_similar(db: AsyncSession, product: Product, *, limit: int = 6) -> list[Product]:
    candidates = await _candidate_pool(db, product.id, category_id=product.category_id)
    if product.embedding:
        candidates.sort(key=lambda p: cosine_similarity(product.embedding, p.embedding or []), reverse=True)
    return candidates[:limit]


async def find_cheaper(db: AsyncSession, product: Product, *, limit: int = 6) -> list[Product]:
    candidates = await _candidate_pool(db, product.id, category_id=product.category_id)
    candidates = [p for p in candidates if p.price_cents < product.price_cents]
    if product.embedding:
        candidates.sort(key=lambda p: cosine_similarity(product.embedding, p.embedding or []), reverse=True)
    else:
        candidates.sort(key=lambda p: p.price_cents, reverse=True)  # closest-to-original-price first
    return candidates[:limit]
