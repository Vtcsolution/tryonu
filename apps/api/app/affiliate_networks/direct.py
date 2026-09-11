"""No third-party network — the retailer's own direct affiliate/partner
program (or, for the seeded sample catalog, a plain tracking tag). This is
the only network active by default; it's what `ProductProvider.
build_affiliate_url()` already does per-retailer (see app/retailers/base.py)."""

from __future__ import annotations

from app.affiliate_networks.base import AffiliateNetworkProvider


class DirectAffiliateNetwork(AffiliateNetworkProvider):
    slug = "direct"
    display_name = "Direct"

    def build_affiliate_url(self, product_url: str, *, retailer_slug: str) -> str:
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}ref=tryonu"
