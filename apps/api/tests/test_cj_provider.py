"""CJ Affiliate provider: request/response shape locked in from a live
schema introspection against https://ads.api.cj.com/query (companyId is a
required, non-nullable argument on `products`; linkCode.clickUrl is the
ready-made tracked affiliate link) — no real CJ product data is fetched in
tests, but the shape this asserts against is real, not guessed."""

from __future__ import annotations

import httpx
import pytest

from app.retailers.base import RawProduct
from app.retailers.cj import CJProductProvider
from app.retailers.errors import RetailerNotConfiguredError


async def test_fetch_products_without_credentials_raises_not_configured():
    provider = CJProductProvider(api_token=None, company_id=None)
    with pytest.raises(RetailerNotConfiguredError):
        await provider.fetch_products(limit=10)


async def test_fetch_products_without_company_id_raises_not_configured():
    """companyId is a required, non-nullable GraphQL argument — a token
    alone is not enough (confirmed via live introspection)."""
    provider = CJProductProvider(api_token="some-token", company_id=None)
    with pytest.raises(RetailerNotConfiguredError):
        await provider.fetch_products(limit=10)


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_fetch_products_sends_company_id_and_maps_real_response_shape(monkeypatch):
    captured = {}

    dress_item = {
        "id": "pid_123",
        "title": "Red Evening Gown",
        "description": "A floor-length gown.",
        "brand": "Lulus",
        "imageLink": "https://cj.example/main.jpg",
        "additionalImageLink": ["https://cj.example/alt.jpg"],
        "link": "https://retailer.example/gown",
        "linkCode": {"clickUrl": "https://www.dpbolvw.net/click-1234-5678?url=..."},
        "price": {"amount": "49.99", "currency": "USD"},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://ads.api.cj.com/query"
        assert request.headers["Authorization"] == "Bearer test-token"
        body = request.content.decode()
        import json

        payload = json.loads(body)
        captured["variables"] = payload["variables"]
        return httpx.Response(200, json={"data": {"products": {"resultList": [dress_item]}}})

    _patch_transport(monkeypatch, handler)

    provider = CJProductProvider(api_token="test-token", company_id="cid_999")
    products = await provider.fetch_products(limit=5)

    assert captured["variables"]["companyId"] == "cid_999"

    assert len(products) >= 1
    p = products[0]
    assert isinstance(p, RawProduct)
    assert p.retailer_product_id == "pid_123"
    assert p.name == "Red Evening Gown"
    assert p.brand == "Lulus"
    assert p.price_cents == 4999
    assert p.currency == "usd"
    # the tracked clickUrl is used as product_url, not the raw `link`
    assert p.product_url == "https://www.dpbolvw.net/click-1234-5678?url=..."
    assert p.images == ["https://cj.example/main.jpg", "https://cj.example/alt.jpg"]


async def test_fetch_products_falls_back_to_raw_link_when_no_click_url(monkeypatch):
    item = {
        "id": "pid_no_link_code",
        "title": "Plain Item",
        "link": "https://retailer.example/plain",
        "linkCode": None,
        "price": {"amount": "10.00", "currency": "USD"},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"products": {"resultList": [item]}}})

    _patch_transport(monkeypatch, handler)

    provider = CJProductProvider(api_token="test-token", company_id="cid_999")
    products = await provider.fetch_products(limit=5)
    assert products[0].product_url == "https://retailer.example/plain"


async def test_fetch_products_sends_pid_for_link_generation(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["variables"] = json.loads(request.content.decode())["variables"]
        return httpx.Response(200, json={"data": {"products": {"resultList": []}}})

    _patch_transport(monkeypatch, handler)

    provider = CJProductProvider(api_token="test-token", company_id="cid_999")
    await provider.fetch_products(limit=5)
    assert captured["variables"]["pid"] == "cid_999"
    assert captured["variables"]["companyId"] == "cid_999"


async def test_fetch_products_raises_clearly_on_a_plain_text_403(monkeypatch):
    """Regression test for a real response CJ actually returns: a plain
    HTTP 403 with a plain-text body (not a JSON GraphQL error envelope) —
    e.g. "User is not authorized to query on behalf of companyId ..." when
    the account isn't entitled to the Product Feed API yet. Must not crash
    trying to .json()-decode that body; must raise a clear error instead."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="User is not authorized to query on behalf of companyId 8069251.")

    _patch_transport(monkeypatch, handler)

    provider = CJProductProvider(api_token="test-token", company_id="8069251")
    with pytest.raises(RuntimeError, match="not authorized"):
        await provider.fetch_products(limit=5)


async def test_fetch_products_raises_on_graphql_errors(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "Invalid companyId"}]})

    _patch_transport(monkeypatch, handler)

    provider = CJProductProvider(api_token="test-token", company_id="bad_cid")
    with pytest.raises(RuntimeError, match="Invalid companyId"):
        await provider.fetch_products(limit=5)


def test_build_affiliate_url_is_a_passthrough():
    """CJ's linkCode.clickUrl is already tracked — nothing to append,
    unlike eBay's campid or Amazon's tag scheme."""
    provider = CJProductProvider(api_token="t", company_id="c")
    url = "https://www.dpbolvw.net/click-1234-5678?url=..."
    assert provider.build_affiliate_url(url, tracking_tag="tryonu-20") == url
