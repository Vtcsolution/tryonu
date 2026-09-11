"""Amazon Product Advertising API (PA-API 5.0) adapter — stub.

Real implementation: sign requests with AWS Signature V4 using
AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY / AMAZON_PARTNER_TAG (set as env vars
+ added to app/core/config.py), call `SearchItems`/`GetItems`, map the
response into RawProduct. Left unimplemented here for lack of credentials —
the ingestion service skips any provider that raises
RetailerNotConfiguredError rather than failing the whole sync.
"""

from __future__ import annotations

from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError


class AmazonProductProvider(ProductProvider):
    slug = "amazon"
    display_name = "Amazon"

    def __init__(self, *, access_key: str | None, secret_key: str | None, partner_tag: str | None) -> None:
        self._access_key = access_key
        self._secret_key = secret_key
        self._partner_tag = partner_tag

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        if not (self._access_key and self._secret_key and self._partner_tag):
            raise RetailerNotConfiguredError(
                "Amazon PA-API credentials not set (AMAZON_ACCESS_KEY / "
                "AMAZON_SECRET_KEY / AMAZON_PARTNER_TAG)"
            )
        raise NotImplementedError("Wire up PA-API SearchItems/GetItems here once credentials exist")

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}tag={self._partner_tag or tracking_tag}"
