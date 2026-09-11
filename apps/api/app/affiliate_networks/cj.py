"""Commission Junction (CJ Affiliate) adapter — stub.

Real implementation once credentials exist: build_affiliate_url wraps the
product URL via CJ's deep-link format (advertiser id + website id +
`url=` param); fetch_conversions calls CJ's GraphQL Conversion API.
"""

from __future__ import annotations

from app.affiliate_networks.base import AffiliateNetworkProvider
from app.affiliate_networks.errors import AffiliateNetworkNotConfiguredError


class CJAffiliateNetwork(AffiliateNetworkProvider):
    slug = "cj"
    display_name = "CJ Affiliate"

    def __init__(self, *, api_token: str | None, website_id: str | None) -> None:
        self._api_token = api_token
        self._website_id = website_id

    def build_affiliate_url(self, product_url: str, *, retailer_slug: str) -> str:
        if not (self._api_token and self._website_id):
            raise AffiliateNetworkNotConfiguredError(
                "CJ Affiliate is not configured (CJ_API_TOKEN / CJ_WEBSITE_ID)"
            )
        raise NotImplementedError("Wire up CJ's deep-link format here once credentials exist")
