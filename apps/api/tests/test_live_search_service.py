"""live_search_service: fans a query out to every provider that supports
search_live, skips ones that don't (NotImplementedError) or aren't
configured, never fails the whole search because one retailer errored,
and find_live_result re-locates one specific prior result by identity."""

from __future__ import annotations

from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError
from app.services.live_search_service import find_live_result, live_search


class _FakeProvider(ProductProvider):
    def __init__(self, slug: str, *, items: list[RawProduct] | None = None, error: Exception | None = None):
        self.slug = slug
        self.display_name = slug.title()
        self._items = items or []
        self._error = error

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # pragma: no cover - unused here
        return self._items

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        if self._error:
            raise self._error
        return self._items[:limit]


class _NoLiveSearchProvider(ProductProvider):
    slug = "no-live"
    display_name = "No Live"

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # pragma: no cover - unused here
        return []
    # search_live not overridden -> base class raises NotImplementedError


def _raw(pid: str, name: str = "Item") -> RawProduct:
    return RawProduct(
        retailer_product_id=pid, name=name, price_cents=1000, product_url=f"https://example.com/{pid}", images=[]
    )


async def test_live_search_fans_out_to_every_supporting_provider(monkeypatch):
    a = _FakeProvider("a", items=[_raw("a1"), _raw("a2")])
    b = _FakeProvider("b", items=[_raw("b1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a, b])

    results = await live_search("jacket", limit=10)
    assert {r.raw.retailer_product_id for r in results} == {"a1", "a2", "b1"}


async def test_live_search_skips_a_provider_without_live_search_support(monkeypatch):
    supported = _FakeProvider("a", items=[_raw("a1")])
    unsupported = _NoLiveSearchProvider()
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [unsupported, supported])

    results = await live_search("jacket", limit=10)
    assert [r.raw.retailer_product_id for r in results] == ["a1"]


async def test_live_search_skips_an_unconfigured_provider(monkeypatch):
    unconfigured = _FakeProvider("a", error=RetailerNotConfiguredError("no creds"))
    configured = _FakeProvider("b", items=[_raw("b1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [unconfigured, configured])

    results = await live_search("jacket", limit=10)
    assert [r.raw.retailer_product_id for r in results] == ["b1"]


async def test_live_search_does_not_fail_the_whole_search_when_one_provider_errors(monkeypatch):
    broken = _FakeProvider("a", error=RuntimeError("boom"))
    working = _FakeProvider("b", items=[_raw("b1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [broken, working])

    results = await live_search("jacket", limit=10)
    assert [r.raw.retailer_product_id for r in results] == ["b1"]


async def test_live_search_respects_the_limit_across_providers(monkeypatch):
    a = _FakeProvider("a", items=[_raw("a1"), _raw("a2"), _raw("a3")])
    b = _FakeProvider("b", items=[_raw("b1"), _raw("b2")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a, b])

    results = await live_search("jacket", limit=4)
    assert len(results) == 4


async def test_find_live_result_locates_the_matching_item(monkeypatch):
    a = _FakeProvider("a", items=[_raw("a1", "Jacket One"), _raw("a2", "Jacket Two")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])

    found = await find_live_result("jacket", retailer_slug="a", retailer_product_id="a2")
    assert found is not None
    assert found.raw.name == "Jacket Two"


async def test_find_live_result_returns_none_when_the_item_is_gone(monkeypatch):
    a = _FakeProvider("a", items=[_raw("a1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])

    found = await find_live_result("jacket", retailer_slug="a", retailer_product_id="does-not-exist")
    assert found is None


async def test_every_retailer_is_asked_even_when_the_first_one_fills_the_page(monkeypatch):
    """The bug this replaced: providers were asked in turn until the limit
    was full, so whichever came first in the registry answered everything
    and a newly connected retailer changed nothing a shopper could see."""
    busy = _FakeProvider("busy", items=[_raw(f"busy{i}", f"Busy Item {i}") for i in range(24)])
    new = _FakeProvider("new", items=[_raw("new1", "New Retailer Kurta")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [busy, new])

    ids = [r.raw.retailer_product_id for r in await live_search("kurta", limit=12)]
    assert "new1" in ids
    assert ids[0] == "busy0" and ids[1] == "new1"  # interleaved, not one then the other


async def test_retailers_are_asked_at_the_same_time_not_one_after_another(monkeypatch):
    """Ten searches for a ten-item prompt is slow enough without making
    the retailers queue behind each other."""
    import asyncio

    both_in = asyncio.Event()
    arrived = 0

    class _Slow(_FakeProvider):
        async def search_live(self, *, query: str, limit: int = 24):
            nonlocal arrived
            arrived += 1
            if arrived == 2:
                both_in.set()
            await asyncio.wait_for(both_in.wait(), timeout=5)  # deadlocks if sequential
            return self._items

    a, b = _Slow("a", items=[_raw("a1")]), _Slow("b", items=[_raw("b1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a, b])
    results = await live_search("kurta", limit=10)
    assert {r.raw.retailer_product_id for r in results} == {"a1", "b1"}


async def test_the_same_product_from_two_networks_is_shown_once(monkeypatch):
    same = "Casio LQ-142E Women Analog Watch"
    a = _FakeProvider("a", items=[_raw("a1", same)])
    b = _FakeProvider("b", items=[_raw("b1", "Casio LQ 142E Women Analog Watch!")])  # same thing, same price
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a, b])

    results = await live_search("casio", limit=10)
    assert [r.raw.retailer_product_id for r in results] == ["a1"]


async def test_two_variants_from_one_retailer_are_both_kept(monkeypatch):
    """Same title, same price, same shop — that's the red one and the blue
    one, which is a choice a shopper wants, not a duplicate."""
    a = _FakeProvider(
        "a", items=[_raw("red", "Embroidered Lawn Shalwar Kameez"), _raw("blue", "Embroidered Lawn Shalwar Kameez")]
    )
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])

    results = await live_search("shalwar kameez", limit=10)
    assert [r.raw.retailer_product_id for r in results] == ["red", "blue"]


async def test_the_same_listing_twice_from_one_retailer_is_shown_once(monkeypatch):
    a = _FakeProvider("a", items=[_raw("x", "Kurta"), _raw("x", "Kurta")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])

    assert len(await live_search("kurta", limit=10)) == 1


async def test_a_repeated_search_is_served_from_memory(monkeypatch):
    """The stylist fires one search per item in a prompt; a ten-item
    bridal look must not re-hit every retailer for words it just asked."""
    calls: list[str] = []

    class _Counting(_FakeProvider):
        async def search_live(self, *, query: str, limit: int = 24):
            calls.append(query)
            return self._items

    a = _Counting("a", items=[_raw("a1", "Maang Tikka Gold")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])

    first = await live_search("maang tikka", limit=10)
    second = await live_search("maang tikka", limit=10)
    assert len(calls) == 1
    assert [r.raw.retailer_product_id for r in first] == [r.raw.retailer_product_id for r in second]


class _ByIdProvider(_FakeProvider):
    """A retailer that can look one listing up directly."""

    def __init__(self, slug: str, items: list[RawProduct]):
        super().__init__(slug, items=items)
        self.searches = 0
        self.lookups: list[str] = []

    async def search_live(self, *, query: str, limit: int = 24):
        self.searches += 1
        return self._items[:limit]

    async def fetch_by_id(self, retailer_product_id: str):
        self.lookups.append(retailer_product_id)
        return next((i for i in self._items if i.retailer_product_id == retailer_product_id), None)


async def test_a_click_asks_the_retailer_for_that_exact_listing(monkeypatch):
    """Live: a shopper clicked "Try on" on a watch sitting on screen and
    was told it was no longer available, because re-finding it meant
    asking the retailer to rank it back onto page one for the same words."""
    a = _ByIdProvider("a", [_raw("a1", "CURREN Women's Analog Dress Watch")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])

    found = await find_live_result("nothing like it", retailer_slug="a", retailer_product_id="a1")
    assert found is not None and found.raw.retailer_product_id == "a1"
    assert a.lookups == ["a1"]
    assert a.searches == 0  # no search was needed at all


async def test_an_id_the_retailer_does_not_know_is_still_not_found(monkeypatch):
    """Nothing is invented to avoid an empty answer."""
    a = _ByIdProvider("a", [_raw("a1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [a])
    assert await find_live_result("anything", retailer_slug="a", retailer_product_id="ghost") is None


async def test_a_retailer_without_id_lookup_still_falls_back_to_searching(monkeypatch):
    plain = _FakeProvider("a", items=[_raw("a1"), _raw("a2")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [plain])
    found = await find_live_result("jacket", retailer_slug="a", retailer_product_id="a2")
    assert found is not None and found.raw.retailer_product_id == "a2"
