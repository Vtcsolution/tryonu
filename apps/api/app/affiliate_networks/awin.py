"""Awin adapter — stub.

Application has been submitted and is pending approval (per project status
as of 2026-09). Real implementation once approved: build_affiliate_url
wraps the retailer's product URL as
`https://www.awin1.com/cread.php?awinmid=<merchant_id>&awinaffid=<AWIN_PUBLISHER_ID>&clickref=<tracking_tag>&p=<urlencoded product_url>`
(merchant_id is per-retailer and would live on Retailer/AffiliateNetwork
config once known); fetch_conversions calls Awin's Reports API.
"""

from __future__ import annotations

from app.affiliate_networks.base import AffiliateNetworkProvider
from app.affiliate_networks.errors import AffiliateNetworkNotConfiguredError


class AwinAffiliateNetwork(AffiliateNetworkProvider):
    slug = "awin"
    display_name = "Awin"

    def __init__(self, *, api_token: str | None, publisher_id: str | None) -> None:
        self._api_token = api_token
        self._publisher_id = publisher_id

    def build_affiliate_url(self, product_url: str, *, retailer_slug: str) -> str:
        if not self._publisher_id:
            raise AffiliateNetworkNotConfiguredError(
                "Awin is not configured yet (AWIN_API_TOKEN / AWIN_PUBLISHER_ID) — "
                "application is pending approval"
            )
        raise NotImplementedError("Wire up the real Awin merchant-id mapping once the application is approved")
