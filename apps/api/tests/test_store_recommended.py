"""Products of TryOnU company stores are recommended: first in search, first
among an item's other options, and flagged to the stylist AI."""

from __future__ import annotations

from app.retailers.base import RawProduct
from app.services import stylist_service as st
from app.services.live_search_service import LiveSearchResult, _local_stores_first


class _P:
    def __init__(self, slug: str) -> None:
        self.slug = slug


def _r(slug: str, rid: str, price: int = 2000, country: str | None = None, featured: bool = False) -> LiveSearchResult:
    raw = RawProduct(retailer_product_id=rid, name=f"Pink lehenga {rid}", price_cents=price,
                     product_url="https://x.example.com", images=["https://x.example.com/a.jpg"], origin_country=country,
                     featured=featured)
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


def test_featured_and_local_products_lead_in_that_order():
    from app.services.shopper_context import set_country

    r = _r

    set_country("PK")
    try:
        results = [
            r("ebay", "e1"),
            r("stores", "other", country="GB"),
            r("stores", "other_featured", country="GB", featured=True),
            r("stores", "local", country="PK"),
            r("stores", "local_featured", country="PK", featured=True),
        ]
        ordered = [x.raw.retailer_product_id for x in _local_stores_first(results)]
        assert ordered == ["local_featured", "local", "other_featured", "other", "e1"]
    finally:
        set_country(None)


def _tiered(rid: str, name: str, tier: int) -> LiveSearchResult:
    raw = RawProduct(retailer_product_id=rid, name=name, price_cents=3000, product_url="https://x.example.com",
                     images=["https://x.example.com/a.jpg"], origin_country="PK", store_tier=tier)
    return LiveSearchResult(provider=_P("stores"), raw=raw)  # type: ignore[arg-type]


def test_same_product_in_three_stores_premium_first_then_standard_then_basic():
    results = [
        _r("ebay", "e1"),
        _tiered("basic", "Red Silk Dress", 1),
        _tiered("premium", "Red Silk Dress", 3),
        _tiered("standard", "Red Silk Dress", 2),
    ]
    ordered = [r.raw.retailer_product_id for r in _local_stores_first(results, "red silk dress")]
    assert ordered == ["premium", "standard", "basic", "e1"]


def test_a_better_match_beats_a_bigger_plan():
    # the shopper asked for red silk: Premium's dress is blue, Standard's is red silk
    results = [
        _tiered("basic", "Red Silk Dress", 1),
        _tiered("premium", "Blue Cotton Dress", 3),
        _tiered("standard", "Red Silk Dress", 2),
    ]
    ordered = [r.raw.retailer_product_id for r in _local_stores_first(results, "red silk dress")]
    assert ordered == ["standard", "basic", "premium"]


def test_the_stylist_swaps_in_the_premium_stores_product():
    picked = st._Candidate(result=_r("ebay", "ebay-dress"), term="women dress")
    pool = [
        picked,
        st._Candidate(result=_tiered("basic", "Women Floral Dress", 1), term="women dress"),
        st._Candidate(result=_tiered("premium", "Women Floral Dress", 3), term="women dress"),
        st._Candidate(result=_tiered("standard", "Women Floral Dress", 2), term="women dress"),
    ]
    chosen, swapped = st._prefer_store_items([picked], pool)
    assert swapped and chosen[0].result.raw.retailer_product_id == "premium"
