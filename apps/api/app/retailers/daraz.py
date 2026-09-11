"""Daraz (Alibaba affiliate network / Involve Asia) adapter — stub.

Real implementation: usually accessed through an affiliate network (Involve
Asia, Admitad) rather than a direct Daraz API — swap in that network's SDK
here once credentials exist.
"""

from __future__ import annotations

from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError


class DarazProductProvider(ProductProvider):
    slug = "daraz"
    display_name = "Daraz"

    def __init__(self, *, api_key: str | None) -> None:
        self._api_key = api_key

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        if not self._api_key:
            raise RetailerNotConfiguredError("Daraz/affiliate-network API key not set (DARAZ_API_KEY)")
        raise NotImplementedError("Wire up the Daraz/affiliate-network product feed here")

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}aff_id={tracking_tag}"
