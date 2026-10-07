"""Admitad programmes as a product source, next to eBay and AliExpress.

Admitad has no live product search: the approved programmes' feeds are
imported daily into admitad_feed_items (app/scripts/admitad_import.py) and
this provider searches that table. Each product names its shop (Allegra K,
Symbol, ...) as the merchant; its link is already the tracked Admitad link
for our ad space, so it is used exactly as it is.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.admitad_feed import AdmitadFeedItem
from app.retailers.base import ProductProvider, RawProduct
from app.services.admitad_feeds import search_feed


def _raw(item: AdmitadFeedItem) -> RawProduct:
    return RawProduct(
        retailer_product_id=f"{item.campaign_id}:{item.offer_id}",
        name=item.name,
        price_cents=item.price_cents,
        product_url=item.product_url,
        images=[item.image_url],
        currency=item.currency,
        brand=item.vendor,
        subcategory=item.category,
        description=item.description,
        availability="in_stock" if item.available else "out_of_stock",
        merchant_name=item.campaign_name,
        merchant_id=str(item.campaign_id),
    )


class AdmitadFeedProvider(ProductProvider):
    slug = "admitad"
    display_name = "Admitad"

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # noqa: ARG002
        # the feeds are imported by app/scripts/admitad_import.py, not by the
        # catalogue sync; they are searched on demand instead
        return []

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        async with AsyncSessionLocal() as db:
            return [_raw(item) for item in await search_feed(db, query, limit)]

    async def fetch_by_id(self, retailer_product_id: str) -> RawProduct | None:
        campaign, _, offer = retailer_product_id.partition(":")
        if not campaign.isdigit() or not offer:
            return None
        async with AsyncSessionLocal() as db:
            item = (
                await db.execute(
                    select(AdmitadFeedItem).where(
                        AdmitadFeedItem.campaign_id == int(campaign), AdmitadFeedItem.offer_id == offer
                    )
                )
            ).scalar_one_or_none()
        return _raw(item) if item else None

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:  # noqa: ARG002
        # already the tracked Admitad link for our ad space
        return product_url
