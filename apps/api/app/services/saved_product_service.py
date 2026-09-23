"""Saving the products a shopper actually reached for.

Two rules shape this. Nothing is taken on the client's word: a live
search result is re-located against the retailer first (the same check
POST /products/select-live does), so a saved price or affiliate link is
one the retailer really gave us. And what is saved is a snapshot — the
name, image, links and price as they were at that moment — so the
shopper's list survives the retailer editing the listing or pulling it
entirely, which is the whole point of having saved it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import SavedProductStatus
from app.models.product import Product
from app.models.saved_product import SavedProduct
from app.services.live_search_service import LiveSearchResult, find_live_result
from app.services.product_ingestion_service import persist_single_product


class ProductGone(Exception):
    """The retailer no longer lists it, so there is nothing honest to save."""


async def _snapshot_from_product(product: Product) -> dict:
    return {
        "product_id": product.id,
        "retailer_slug": product.retailer.slug,
        "retailer_name": product.retailer.name,
        "retailer_product_id": product.retailer_product_id,
        "name": product.name,
        "image_url": product.primary_image_url,
        "product_url": product.product_url,
        "affiliate_url": product.affiliate_url,
        "price_cents": product.price_cents,
        "currency": product.currency,
    }


async def _from_live(db: AsyncSession, result: LiveSearchResult) -> dict:
    """A live result becomes a real Product row first — that is where the
    affiliate URL is built, and it keeps the one place that happens."""
    product = await persist_single_product(db, result.provider, result.raw)
    reloaded = await db.execute(
        select(Product)
        .where(Product.id == product.id)
        .options(selectinload(Product.images), selectinload(Product.retailer))
    )
    return await _snapshot_from_product(reloaded.scalar_one())


async def save_product(
    db: AsyncSession,
    *,
    user_id: str,
    status: SavedProductStatus,
    product_id: str | None = None,
    retailer_slug: str | None = None,
    retailer_product_id: str | None = None,
    query: str | None = None,
) -> SavedProduct:
    """Save (or re-save) one product for this shopper.

    Either a product we already hold, or a live result identified by
    retailer + id + the query that found it, which is re-fetched from the
    retailer before anything is written down."""
    if product_id:
        found = await db.execute(
            select(Product).where(Product.id == product_id).options(selectinload(Product.retailer), selectinload(Product.images))
        )
        product = found.scalar_one_or_none()
        if product is None:
            raise ProductGone("We don't have that product")
        snapshot = await _snapshot_from_product(product)
    else:
        if not (retailer_slug and retailer_product_id and query):
            raise ValueError("a live product needs retailer_slug, retailer_product_id and query")
        result = await find_live_result(
            query, retailer_slug=retailer_slug, retailer_product_id=retailer_product_id
        )
        if result is None:
            raise ProductGone("That item is no longer listed by the retailer")
        snapshot = await _from_live(db, result)

    existing = await db.scalar(
        select(SavedProduct).where(
            SavedProduct.user_id == user_id,
            SavedProduct.retailer_slug == snapshot["retailer_slug"],
            SavedProduct.retailer_product_id == snapshot["retailer_product_id"],
        )
    )
    if existing is not None:
        # saving something twice moves the existing row on (saved ->
        # favourite -> purchased) and refreshes the snapshot to what the
        # retailer says today, rather than leaving a stale duplicate
        for field, value in snapshot.items():
            setattr(existing, field, value)
        existing.status = status
        await db.commit()
        await db.refresh(existing)
        return existing

    saved = SavedProduct(user_id=user_id, status=status, **snapshot)
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return saved


async def list_saved(
    db: AsyncSession, *, user_id: str, status: SavedProductStatus | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[SavedProduct], int]:
    from sqlalchemy import func

    where = [SavedProduct.user_id == user_id]
    if status is not None:
        where.append(SavedProduct.status == status)
    total = await db.scalar(select(func.count(SavedProduct.id)).where(*where)) or 0
    rows = await db.execute(
        select(SavedProduct).where(*where).order_by(SavedProduct.created_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.scalars().all()), total


async def get_saved(db: AsyncSession, *, user_id: str, saved_id: str) -> SavedProduct | None:
    return await db.scalar(
        select(SavedProduct).where(SavedProduct.id == saved_id, SavedProduct.user_id == user_id)
    )
