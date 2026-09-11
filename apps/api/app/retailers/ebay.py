"""eBay Partner Network / Browse API adapter — stub.

Real implementation: OAuth2 client-credentials grant with EBAY_CLIENT_ID /
EBAY_CLIENT_SECRET, call the Browse API's `item_summary/search`, map results
into RawProduct, and build affiliate links via the Partner Network's
campid/EPN tracking parameters.
"""

from __future__ import annotations

from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError


class EbayProductProvider(ProductProvider):
    slug = "ebay"
    display_name = "eBay"

    def __init__(self, *, client_id: str | None, client_secret: str | None, campaign_id: str | None) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._campaign_id = campaign_id

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        if not (self._client_id and self._client_secret):
            raise RetailerNotConfiguredError(
                "eBay API credentials not set (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET)"
            )
        raise NotImplementedError("Wire up the Browse API item_summary/search call here")

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        sep = "&" if "?" in product_url else "?"
        campid = self._campaign_id or tracking_tag
        return f"{product_url}{sep}campid={campid}"
