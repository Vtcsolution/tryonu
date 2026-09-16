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
