"""Impact (impact.com) adapter — stub.

Real implementation once credentials exist: build_affiliate_url wraps the
product URL via Impact's tracking-link format (`https://goto.impact.com/...`);
fetch_conversions calls Impact's Reports API using IMPACT_ACCOUNT_SID /
IMPACT_AUTH_TOKEN basic auth.
"""

from __future__ import annotations

from app.affiliate_networks.base import AffiliateNetworkProvider
from app.affiliate_networks.errors import AffiliateNetworkNotConfiguredError


class ImpactAffiliateNetwork(AffiliateNetworkProvider):
    slug = "impact"
    display_name = "Impact"

    def __init__(self, *, account_sid: str | None, auth_token: str | None) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token

    def build_affiliate_url(self, product_url: str, *, retailer_slug: str) -> str:
        if not (self._account_sid and self._auth_token):
            raise AffiliateNetworkNotConfiguredError(
                "Impact is not configured (IMPACT_ACCOUNT_SID / IMPACT_AUTH_TOKEN)"
            )
        raise NotImplementedError("Wire up Impact's tracking-link format here once credentials exist")
