"""Company stores as a product source, next to eBay, AliExpress and Admitad.

Searches the products of stores that are approved and have a paid plan. The
shopper's own country comes first (shopper_context), and live_search puts
those local store products ahead of every other source. A product's link is
the store's own product page, used as it is.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.store import Store, StoreProduct
from app.retailers.base import ProductProvider, RawProduct
from app.services import store_service as svc
from app.services.shopper_context import current_country


def _raw(product: StoreProduct, store: Store, featured: bool = False) -> RawProduct | None:
    images = [svc.image_url(i) for i in product.images or []]
    if not images:
        return None  # nothing to show or try on
    return RawProduct(
        retailer_product_id=product.id,
        name=product.name,
        price_cents=product.price_cents,
        product_url=product.product_url,
        images=images,
        currency=product.currency,
        brand=store.name,
        subcategory=product.category,
        gender=product.gender,
        color=product.color,
        description=product.description,
        merchant_name=store.name,
        merchant_id=store.id,
        origin_country=store.country,
        featured=featured,
    )


class StoreProductProvider(ProductProvider):
    slug = "stores"
    display_name = "TryOnU stores"

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # noqa: ARG002
        return []  # searched on demand, never bulk-synced into the catalogue

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        async with AsyncSessionLocal() as db:
            rows = await svc.search_store_products(db, query, limit, current_country())
            featured = await svc.featured_ids(db, [s for _, s in rows])
        return [raw for raw in (_raw(p, s, p.id in featured) for p, s in rows) if raw is not None]

    async def fetch_by_id(self, retailer_product_id: str) -> RawProduct | None:
        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(
                    select(StoreProduct, Store)
                    .join(Store, Store.id == StoreProduct.store_id)
                    .where(StoreProduct.id == retailer_product_id)
                )
            ).first()
        if row is None or not svc.is_live(row[1]) or not row[0].is_active:
            return None
        return _raw(row[0], row[1])

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:  # noqa: ARG002
        return product_url  # the store's own page
