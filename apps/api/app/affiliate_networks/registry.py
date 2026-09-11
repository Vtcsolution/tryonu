"""Every known affiliate network, configured or not — mirrors
app/retailers/registry.py's pattern. Callers (e.g. an admin "sync
conversions" job) try each and skip the ones that raise
AffiliateNetworkNotConfiguredError.
"""

from __future__ import annotations

from app.affiliate_networks.awin import AwinAffiliateNetwork
from app.affiliate_networks.base import AffiliateNetworkProvider
from app.affiliate_networks.cj import CJAffiliateNetwork
from app.affiliate_networks.direct import DirectAffiliateNetwork
from app.affiliate_networks.impact import ImpactAffiliateNetwork
from app.core.config import get_settings


def get_all_affiliate_networks() -> list[AffiliateNetworkProvider]:
    settings = get_settings()
    return [
        DirectAffiliateNetwork(),
        AwinAffiliateNetwork(api_token=settings.AWIN_API_TOKEN, publisher_id=settings.AWIN_PUBLISHER_ID),
        CJAffiliateNetwork(api_token=settings.CJ_API_TOKEN, website_id=settings.CJ_WEBSITE_ID),
        ImpactAffiliateNetwork(account_sid=settings.IMPACT_ACCOUNT_SID, auth_token=settings.IMPACT_AUTH_TOKEN),
    ]
