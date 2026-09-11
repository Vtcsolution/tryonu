"""Flipkart Affiliate API adapter — stub.

Real implementation: `Fk-Affiliate-Id` / `Fk-Affiliate-Token` headers
against the Affiliate API's product feed endpoints, map into RawProduct.
"""

from __future__ import annotations

from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError


class FlipkartProductProvider(ProductProvider):
    slug = "flipkart"
    display_name = "Flipkart"

    def __init__(self, *, affiliate_id: str | None, affiliate_token: str | None) -> None:
        self._affiliate_id = affiliate_id
        self._affiliate_token = affiliate_token

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        if not (self._affiliate_id and self._affiliate_token):
            raise RetailerNotConfiguredError(
                "Flipkart affiliate credentials not set (FLIPKART_AFFILIATE_ID / FLIPKART_AFFILIATE_TOKEN)"
            )
        raise NotImplementedError("Wire up the Flipkart Affiliate API product feed here")

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}affid={self._affiliate_id or tracking_tag}"
