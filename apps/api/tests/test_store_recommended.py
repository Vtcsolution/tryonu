"""Products of TryOnU company stores are recommended: first in search, first
among an item's other options, and flagged to the stylist AI."""

from __future__ import annotations

from app.retailers.base import RawProduct
from app.services import stylist_service as st
from app.services.live_search_service import LiveSearchResult, _local_stores_first


class _P:
    def __init__(self, slug: str) -> None:
        self.slug = slug


def _r(slug: str, rid: str, price: int = 2000, country: str | None = None) -> LiveSearchResult:
    raw = RawProduct(retailer_product_id=rid, name=f"Pink lehenga {rid}", price_cents=price,
                     product_url="https://x.example.com", images=["https://x.example.com/a.jpg"], origin_country=country)
    return LiveSearchResult(provider=_P(slug), raw=raw)  # type: ignore[arg-type]


def test_search_puts_store_products_first_even_for_shoppers_elsewhere():
    results = [_r("ebay", "e1"), _r("aliexpress", "a1"), _r("stores", "s1", country="PK"), _r("ebay", "e2")]
    ordered = [r.raw.retailer_product_id for r in _local_stores_first(results)]
    assert ordered[0] == "s1" and set(ordered) == {"e1", "a1", "s1", "e2"}


def test_store_options_lead_an_items_alternatives():
    chosen = st._Candidate(result=_r("ebay", "picked"), term="lehenga")
    pool = [st._Candidate(result=_r("ebay", f"e{i}", price=1000 + i * 500), term="lehenga") for i in range(8)]
    pool.append(st._Candidate(result=_r("stores", "s1", price=9000), term="lehenga"))
    alts = st._alternatives_for(chosen, pool, {"picked"})
    assert alts[0].raw.retailer_product_id == "s1"
    assert len(alts) == 9  # every option still offered, the store's first
