"""Price alerts: "tell me when this gets cheaper or is back in stock"."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.price_watch import PriceWatch
from app.models.product import Product

router = APIRouter(prefix="/price-alerts", tags=["price alerts"])
MAX_ALERTS = 100


class PriceAlertOut(BaseModel):
    product_id: str
    name: str
    image_url: str | None
    shop: str | None
    currency: str
    start_price_cents: int
    price_cents: int  # the latest price we know
    in_stock: bool
    checked_at: datetime | None
    created_at: datetime


def _out(w: PriceWatch, p: Product) -> PriceAlertOut:
    return PriceAlertOut(
        product_id=p.id, name=p.name, image_url=p.primary_image_url,
        shop=p.merchant_name or (p.retailer.name if p.retailer else None), currency=p.currency,
        start_price_cents=w.start_price_cents, price_cents=w.last_price_cents, in_stock=w.in_stock, checked_at=w.checked_at,
        created_at=w.created_at,
    )


@router.get("", response_model=list[PriceAlertOut])
async def my_alerts(me: CurrentUser, db: DbSession):
    rows = (
        await db.execute(
            select(PriceWatch, Product)
            .join(Product, Product.id == PriceWatch.product_id)
            .where(PriceWatch.user_id == me.id)
            .options(selectinload(Product.images), selectinload(Product.retailer))
            .order_by(PriceWatch.created_at.desc())
        )
    ).all()
    return [_out(w, p) for w, p in rows]


@router.get("/ids", response_model=list[str])
async def my_alert_ids(me: CurrentUser, db: DbSession):
    """The products I watch (for the alert buttons)."""
    return list((await db.execute(select(PriceWatch.product_id).where(PriceWatch.user_id == me.id))).scalars())


@router.post("/{product_id}", response_model=PriceAlertOut, dependencies=[Depends(rate_limiter("price_alert", limit=120, window_seconds=3600))])
async def add_alert(product_id: str, me: CurrentUser, db: DbSession):
    product = await db.scalar(
        select(Product).where(Product.id == product_id).options(selectinload(Product.images), selectinload(Product.retailer))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    watch = await db.scalar(select(PriceWatch).where(PriceWatch.user_id == me.id, PriceWatch.product_id == product.id))
    if watch is None:
        count = await db.scalar(select(func.count()).select_from(PriceWatch).where(PriceWatch.user_id == me.id))
        if int(count or 0) >= MAX_ALERTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You can have up to {MAX_ALERTS} price alerts. Remove one first.")
        watch = PriceWatch(user_id=me.id, product_id=product.id, start_price_cents=product.price_cents, last_price_cents=product.price_cents)
        db.add(watch)
        await db.commit()
        await db.refresh(watch)
    return _out(watch, product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_alert(product_id: str, me: CurrentUser, db: DbSession):
    await db.execute(delete(PriceWatch).where(PriceWatch.user_id == me.id, PriceWatch.product_id == product_id))
    await db.commit()
