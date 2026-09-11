"""Affiliate-network abstraction — deliberately separate from
`ProductProvider` (app/retailers/base.py). A *retailer* is where the
product catalog comes from (Amazon, eBay, Flipkart, Daraz, ...); a
*network* is who pays the commission and provides the tracking link for
that retailer (Awin, CJ, Impact, or a retailer's own direct program).
One retailer's products can be routed through different networks in
different regions, which is why these aren't the same concept.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConversionRecord:
    """One reported sale/conversion — shape for the reporting pipeline
    mentioned in the spec (clicks/products/retailers/users/conversion
    data). Populated once a real network integration lands."""

    network_slug: str
    external_click_id: str | None
    order_id: str | None
    commission_cents: int
    currency: str
    occurred_at: str  # ISO 8601


class AffiliateNetworkProvider(ABC):
    #: matches AffiliateNetwork.slug in the DB
    slug: str
    display_name: str

    @abstractmethod
    def build_affiliate_url(self, product_url: str, *, retailer_slug: str) -> str:
        """Wraps a retailer's product URL in this network's tracking link."""
        ...

    async def fetch_conversions(self, *, since_iso: str) -> list[ConversionRecord]:  # noqa: ARG002
        """Pull reported conversions since a given time. Every real network
        adapter implements this once credentials exist; until then it's a
        clear, explicit not-yet-available signal rather than fake data."""
        raise NotImplementedError(f"{self.display_name} conversion reporting is not yet connected")
