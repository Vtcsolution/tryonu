"""Price alerts: every few hours, the products members watch are looked up
again at their shop (the shop's own current price and stock, the same way a
product is re-checked before it is saved), and members are told when one is
cheaper than when they last heard, or back in stock."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import logger
from app.models.price_watch import PriceWatch
from app.models.product import Product

# a drop worth telling: at least this much cheaper than the price the member last heard
MIN_DROP_SHARE = 0.05
MIN_DROP_CENTS = 50
_SYMBOLS = {"usd": "$", "gbp": "£", "eur": "€", "pkr": "Rs ", "inr": "₹", "aed": "AED ", "sar": "SAR "}


def price_text(cents: int, currency: str) -> str:
    symbol = _SYMBOLS.get((currency or "").lower())
    amount = f"{cents / 100:,.2f}"
    return f"{symbol}{amount}" if symbol else f"{amount} {currency.upper()}"


def in_stock(availability: str | None) -> bool:
    return (availability or "in_stock").lower() not in {"out_of_stock", "unavailable", "sold_out", "discontinued"}


async def current_offer(product: Product) -> tuple[int, str, bool] | None:
    """(price, currency, in stock) at the shop right now; None when the shop can't be asked."""
    from app.services.live_search_service import find_live_result

    if product.retailer is None:
        return None
    try:
        found = await find_live_result(product.name, retailer_slug=product.retailer.slug, retailer_product_id=product.retailer_product_id)
    except Exception as exc:  # noqa: BLE001 — try again next round
        logger.warning("price_check_failed", product_id=product.id, error=str(exc)[:160])
        return None
    if found is None:
        return (product.price_cents, product.currency, False)  # the shop no longer lists it
    return (found.raw.price_cents, found.raw.currency or product.currency, in_stock(found.raw.availability))


async def check_product(db: AsyncSession, product: Product, watches: list[PriceWatch]) -> int:
    """Look one product up again and tell its watchers what changed. Returns notifications made."""
    from app.services.notification_service import notify

    offer = await current_offer(product)
    now = datetime.now(timezone.utc)
    if offer is None:
        for w in watches:
            w.checked_at = now
        return 0
    price, currency, available = offer
    if available and price > 0:
        product.price_cents, product.currency = price, currency
    told = 0
    for w in watches:
        was_in_stock = w.in_stock
        reference = w.told_price_cents if w.told_price_cents is not None else w.start_price_cents
        if available and not was_in_stock:
            await notify(db, user_id=w.user_id, kind="back_in_stock", product_id=product.id, text=f"{product.name[:120]} · {price_text(price, currency)}")
            told += 1
        elif available and price > 0 and reference - price >= max(MIN_DROP_CENTS, int(reference * MIN_DROP_SHARE)):
            await notify(
                db, user_id=w.user_id, kind="price_drop", product_id=product.id,
                text=f"{product.name[:120]} is now {price_text(price, currency)} (was {price_text(reference, currency)})",
            )
            w.told_price_cents = price
            told += 1
        w.in_stock = available
        if available and price > 0:
            w.last_price_cents = price
        w.checked_at = now
    return told


async def check_due(db: AsyncSession, *, max_products: int = 200) -> int:
    """The watched products not checked for a while, a batch at a time."""
    hours = get_settings().PRICE_ALERT_CHECK_HOURS
    due_before = datetime.now(timezone.utc) - timedelta(hours=hours)
    watches = (
        await db.execute(
            select(PriceWatch)
            .where((PriceWatch.checked_at.is_(None)) | (PriceWatch.checked_at <= due_before))
            .order_by(PriceWatch.checked_at.asc().nulls_first())
            .limit(max_products * 5)
        )
    ).scalars().all()
    by_product: dict[str, list[PriceWatch]] = {}
    for w in watches:
        by_product.setdefault(w.product_id, []).append(w)
    product_ids = list(by_product)[:max_products]
    if not product_ids:
        return 0
    products = (
        await db.execute(select(Product).where(Product.id.in_(product_ids)).options(selectinload(Product.retailer)))
    ).scalars().all()
    told = 0
    for product in products:  # one at a time: shops limit how fast they may be asked
        told += await check_product(db, product, by_product[product.id])
        await db.commit()
    return told


async def check_forever() -> None:
    from app.db.session import AsyncSessionLocal

    await asyncio.sleep(120)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                told = await check_due(db)
            if told:
                logger.info("price_alerts_sent", count=told)
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            logger.warning("price_alert_check_failed", error=str(exc)[:200])
        await asyncio.sleep(30 * 60)
