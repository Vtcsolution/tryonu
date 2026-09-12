from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, OptionalUser
from app.models.enums import Gender
from app.models.product import Product
from app.models.retailer import ProductCategory, Retailer
from app.schemas.common import Page
from app.schemas.product import ProductOut, ProductSearchFilters, RetailerOut
from app.services import history_service
from app.services.search_service import search_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=Page[ProductOut])
async def list_products(
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


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: DbSession, user: OptionalUser):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.is_active.is_(True))
        .options(selectinload(Product.images), selectinload(Product.retailer), selectinload(Product.category))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await history_service.log_product_view(db, user_id=user.id if user else None, product_id=product.id, source="detail")
    return product


@router.get("/meta/retailers", response_model=list[RetailerOut])
async def list_retailers(db: DbSession):
    result = await db.execute(select(Retailer).where(Retailer.is_active.is_(True)))
    return list(result.scalars().all())


@router.get("/meta/categories")
async def list_categories(db: DbSession):
    result = await db.execute(select(ProductCategory))
    return [{"slug": c.slug, "name": c.name} for c in result.scalars().all()]
