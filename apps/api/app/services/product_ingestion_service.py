"""Fetches from every registered ProductProvider, normalizes, and upserts
into the catalog. This is the *only* place retailer data enters the
database — search, the stylist, and try-on all read from `Product`
afterwards and never talk to a retailer directly.

Run via `python -m app.scripts.ingest_products` or the `sync_products`
worker task (see app/workers/tasks/ingestion_tasks.py) on a schedule.
"""

from __future__ import annotations

from datetime import datetime, timezone

from slugify import slugify
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_text, product_embedding_text
from app.core.logging import logger
from app.models.enums import Availability, Gender
from app.models.product import Product, ProductImage
from app.models.retailer import ProductCategory, Retailer
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError
from app.retailers.registry import get_all_providers

_TRACKING_TAG = "tryonu-20"  # affiliate/tracking id used when a provider has no program-specific scheme


async def _get_or_create_retailer(db: AsyncSession, provider: ProductProvider) -> Retailer:
    result = await db.execute(select(Retailer).where(Retailer.slug == provider.slug))
    retailer = result.scalar_one_or_none()
    if retailer is None:
        retailer = Retailer(slug=provider.slug, name=provider.display_name)
        db.add(retailer)
        await db.flush()
    return retailer


async def _get_or_create_category(db: AsyncSession, slug: str | None) -> ProductCategory | None:
    if not slug:
        return None
    slug = slugify(slug)
    result = await db.execute(select(ProductCategory).where(ProductCategory.slug == slug))
    category = result.scalar_one_or_none()
    if category is None:
        category = ProductCategory(slug=slug, name=slug.replace("-", " ").title())
        db.add(category)
        await db.flush()
    return category


async def _upsert_product(
    db: AsyncSession, retailer: Retailer, category: ProductCategory | None, raw: RawProduct, provider: ProductProvider
) -> Product:
    result = await db.execute(
        select(Product).where(
            Product.retailer_id == retailer.id,
            Product.retailer_product_id == raw.retailer_product_id,
        )
    )
    product = result.scalar_one_or_none()

    affiliate_url = provider.build_affiliate_url(raw.product_url, tracking_tag=_TRACKING_TAG)
    try:
        gender = Gender(raw.gender)
    except ValueError:
        gender = Gender.UNISEX
    try:
        availability = Availability(raw.availability)
    except ValueError:
        availability = Availability.IN_STOCK

    if product is None:
        product = Product(
            retailer_id=retailer.id,
            retailer_product_id=raw.retailer_product_id,
        )
        db.add(product)

    product.category_id = category.id if category else None
    product.name = raw.name
    product.brand = raw.brand
    product.merchant_name = raw.merchant_name
    product.merchant_id = raw.merchant_id
    product.description = raw.description
    product.subcategory = raw.subcategory
    product.gender = gender
    product.color = raw.color
    product.sizes = raw.sizes
    product.style_tags = raw.style_tags
    product.price_cents = raw.price_cents
    product.currency = raw.currency
    product.rating = raw.rating
    product.rating_count = raw.rating_count
    product.product_url = raw.product_url
    product.affiliate_url = affiliate_url
    product.availability = availability
    product.is_active = True
    product.last_synced_at = datetime.now(timezone.utc)

    embedding_text = product_embedding_text(
        name=raw.name,
        brand=raw.brand,
        category=raw.category_slug,
        color=raw.color,
        description=raw.description,
        style_tags=raw.style_tags,
    )
    product.embedding = await embed_text(embedding_text)

    await db.flush()

    # Replace images via a bulk statement rather than touching the
    # `.images` relationship — avoids an implicit lazy-load, which
    # AsyncSession disallows outside of a greenlet context.
    await db.execute(delete(ProductImage).where(ProductImage.product_id == product.id))
    for i, url in enumerate(raw.images):
        db.add(ProductImage(product_id=product.id, url=url, position=i, is_primary=(i == 0)))

    return product


async def persist_single_product(db: AsyncSession, provider: ProductProvider, raw: RawProduct) -> Product:
    """The one place a *live-searched* result (see live_search_service.py)
    becomes a real, saved row — called only when a user actually selects
    that specific product (for a try-on, or via the AI stylist choosing
    it), never speculatively for a whole search-results page. Reuses the
    exact same normalization/upsert logic as the bulk sync path, so a
    product looked up live and one that happened to already be synced
    come out identical."""
    retailer = await _get_or_create_retailer(db, provider)
    category = await _get_or_create_category(db, raw.category_slug)
    product = await _upsert_product(db, retailer, category, raw, provider)
    await db.commit()
    await db.refresh(product)
    return product


async def sync_all_retailers(db: AsyncSession, *, limit_per_retailer: int = 200) -> dict[str, int]:
    """Returns {retailer_slug: products_upserted}. Never raises for a single
    misconfigured/unreachable retailer — that retailer is skipped and
    logged so the rest of the sync still completes."""
    results: dict[str, int] = {}

    for provider in get_all_providers():
        try:
            raw_products = await provider.fetch_products(limit=limit_per_retailer)
        except RetailerNotConfiguredError as exc:
            logger.info("retailer_skipped", retailer=provider.slug, reason=str(exc))
            continue
        except NotImplementedError:
            logger.info("retailer_not_implemented", retailer=provider.slug)
            continue
        except Exception as exc:  # noqa: BLE001 — one bad retailer must not abort the sync
            logger.warning("retailer_sync_failed", retailer=provider.slug, error=str(exc))
            continue

        retailer = await _get_or_create_retailer(db, provider)
        count = 0
        for raw in raw_products:
            category = await _get_or_create_category(db, raw.category_slug)
            await _upsert_product(db, retailer, category, raw, provider)
            count += 1

        await db.commit()
        results[provider.slug] = count
        logger.info("retailer_synced", retailer=provider.slug, products=count)

    return results
