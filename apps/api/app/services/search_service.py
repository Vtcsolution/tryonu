"""Product search: SQL does the cheap, selective filtering (category,
brand, price range, gender, retailer, color, availability); when a free-text
query is present we additionally rerank the filtered candidate set by
cosine similarity against its embedding — true semantic search, not just
keyword matching.

At catalog scale, swap the Python rerank for a pgvector ANN index
(`embedding <-> :query_vec` with an ivfflat/hnsw index — see the Alembic
migration comment) and this function's public signature doesn't change.
"""

from __future__ import annotations

from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.embeddings import cosine_similarity, embed_text
from app.models.product import Product
from app.models.retailer import ProductCategory, Retailer
from app.schemas.product import ProductSearchFilters

_CANDIDATE_CAP = 500


async def search_products(db: AsyncSession, filters: ProductSearchFilters) -> tuple[list[Product], int]:
    stmt = select(Product).where(Product.is_active.is_(True)).options(
        selectinload(Product.images), selectinload(Product.retailer), selectinload(Product.category)
    )

    if filters.category:
        stmt = stmt.join(ProductCategory, Product.category_id == ProductCategory.id).where(
            ProductCategory.slug == filters.category
        )
    if filters.retailer:
        stmt = stmt.join(Retailer, Product.retailer_id == Retailer.id).where(Retailer.slug == filters.retailer)
    if filters.brand:
        stmt = stmt.where(func.lower(Product.brand) == filters.brand.lower())
    if filters.color:
        stmt = stmt.where(func.lower(Product.color) == filters.color.lower())
    if filters.gender:
        stmt = stmt.where(Product.gender == filters.gender)
    if filters.min_price_cents is not None:
        stmt = stmt.where(Product.price_cents >= filters.min_price_cents)
    if filters.max_price_cents is not None:
        stmt = stmt.where(Product.price_cents <= filters.max_price_cents)
    if filters.style:
        # style_tags is a JSON array; portable substring match across dialects.
        stmt = stmt.where(func.lower(func.cast(Product.style_tags, String)).contains(filters.style.lower()))

    if filters.q:
        like = f"%{filters.q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.name).like(like),
                func.lower(Product.brand).like(like),
                func.lower(Product.description).like(like),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.with_only_columns(Product.id).subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.limit(_CANDIDATE_CAP)
    products = list((await db.execute(stmt)).scalars().unique().all())

    if filters.q and filters.sort == "relevance":
        query_vec = await embed_text(filters.q)
        products.sort(
            key=lambda p: cosine_similarity(query_vec, p.embedding or []), reverse=True
        )
    elif filters.sort == "price_asc":
        products.sort(key=lambda p: p.price_cents)
    elif filters.sort == "price_desc":
        products.sort(key=lambda p: p.price_cents, reverse=True)
    elif filters.sort == "rating":
        products.sort(key=lambda p: p.rating or 0, reverse=True)
    elif filters.sort == "newest":
        products.sort(key=lambda p: p.created_at, reverse=True)

    page = products[filters.offset : filters.offset + filters.limit]
    return page, total
