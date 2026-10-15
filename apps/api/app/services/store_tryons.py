"""Store try-on credits: a company store pays for shoppers' try-ons of its products.

Every store plan includes try-on credits. When a shopper tries on a look with
a store's product and agrees to share the picture with that store, the store
pays one credit and the shopper pays nothing. The shopper can always choose
to pay with their own credits instead and keep the picture private; the store
then only sees that its product was tried on, never the picture.

Each try-on of a store product leaves one StoreTryOn row per store product in
the look, so every store sees how often its products are tried on. A failed
try-on gives the store its credit back (credit_service.refund calls refund_job).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.outfit import OutfitItem
from app.models.product import Product
from app.models.retailer import Retailer
from app.models.store import Store, StoreProduct, StoreTryOn
from app.services import store_service as svc


@dataclass(frozen=True, slots=True)
class LookStoreProduct:
    product_id: str  # the saved Product the look uses
    store_product: StoreProduct
    store: Store


async def look_product_ids(db: AsyncSession, *, product_id: str | None, outfit_id: str | None) -> list[str]:
    """The saved products in a try-on, in look order."""
    if product_id:
        return [product_id]
    if outfit_id:
        rows = await db.execute(
            select(OutfitItem.product_id).where(OutfitItem.outfit_id == outfit_id).order_by(OutfitItem.position)
        )
        return [r for r in rows.scalars() if r]
    return []


async def store_products_in(db: AsyncSession, product_ids: list[str]) -> list[LookStoreProduct]:
    """The look's products that come from TryOnU company stores, in look order."""
    if not product_ids:
        return []
    rows = (
        await db.execute(
            select(Product.id, StoreProduct, Store)
            .join(Retailer, Retailer.id == Product.retailer_id)
            .join(StoreProduct, StoreProduct.id == Product.retailer_product_id)
            .join(Store, Store.id == StoreProduct.store_id)
            .where(Retailer.slug == "stores", Product.id.in_(product_ids))
        )
    ).all()
    by_id = {pid: LookStoreProduct(pid, sp, st) for pid, sp, st in rows}
    return [by_id[pid] for pid in product_ids if pid in by_id]


def sponsor_of(items: list[LookStoreProduct]) -> Store | None:
    """The store that pays for this try-on: the first one in the look that is
    live and still has try-on credits."""
    for item in items:
        if svc.is_live(item.store) and item.store.tryon_credits > 0:
            return item.store
    return None


async def charge(db: AsyncSession, store_id: str) -> bool:
    """Take one try-on credit from the store; False if it has none left.
    One UPDATE with the check in it, so two shoppers can't spend the last one twice."""
    result = await db.execute(
        update(Store).where(Store.id == store_id, Store.tryon_credits > 0).values(tryon_credits=Store.tryon_credits - 1)
    )
    return (result.rowcount or 0) == 1


def record(
    db: AsyncSession,
    *,
    job_id: str,
    items: list[LookStoreProduct],
    sponsor: Store | None,
    shared: bool,
    country: str | None,
) -> None:
    """One row per store product in the look. The sponsor pays once (its first
    product's row); its products are shared when the shopper agreed."""
    paid = False
    for item in items:
        is_sponsor = sponsor is not None and item.store.id == sponsor.id
        db.add(
            StoreTryOn(
                store_id=item.store.id,
                store_product_id=item.store_product.id,
                tryon_job_id=job_id,
                paid_by_store=is_sponsor and not paid,
                shared=is_sponsor and shared,
                shopper_country=country,
            )
        )
        paid = paid or is_sponsor


async def refund_job(db: AsyncSession, job_id: str) -> int:
    """A failed or cancelled try-on gives the paying store its credit back,
    once. Returns how many credits went back."""
    rows = (
        await db.execute(
            select(StoreTryOn).where(
                StoreTryOn.tryon_job_id == job_id, StoreTryOn.paid_by_store.is_(True), StoreTryOn.refunded.is_(False)
            )
        )
    ).scalars().all()
    for row in rows:
        row.refunded = True
        await db.execute(update(Store).where(Store.id == row.store_id).values(tryon_credits=Store.tryon_credits + 1))
    return len(rows)


def tryon_cost_usd_cents() -> int:
    """What one try-on costs TryOnU: FASHN credits per try-on x their price in
    PKR, in US cents (e.g. 4 x 30 PKR = 120 PKR = 43 cents at 280 PKR/USD)."""
    s = get_settings()
    pkr = s.STORE_FASHN_CREDITS_PER_TRYON * s.STORE_FASHN_CREDIT_PKR
    return round(pkr * 100 / max(s.STORE_USD_TO_PKR, 1))
