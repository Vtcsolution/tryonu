"""eBay Browse API adapter: OAuth token flow, item-summary mapping, and the
"not configured until credentials exist" contract — no real eBay calls, no
credentials needed to run this."""

from __future__ import annotations

import httpx
import pytest

from app.retailers.base import RawProduct
from app.retailers.ebay import EbayProductProvider
from app.retailers.errors import RetailerNotConfiguredError


async def test_fetch_products_without_credentials_raises_not_configured():
    provider = EbayProductProvider(client_id=None, client_secret=None, campaign_id=None)
    with pytest.raises(RetailerNotConfiguredError):
        await provider.fetch_products(limit=10)


async def test_search_live_without_credentials_raises_not_configured():
    provider = EbayProductProvider(client_id=None, client_secret=None, campaign_id=None)
    with pytest.raises(RetailerNotConfiguredError):
        await provider.search_live(query="denim jacket", limit=10)


def _fake_transport(*, items_by_query: dict[str, list[dict]]):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.ebay.com" and request.url.path == "/identity/v1/oauth2/token":
            assert request.headers["Authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 7200})
        if request.url.path == "/buy/browse/v1/item_summary/search":
            assert request.headers["Authorization"].startswith("Bearer ")
            assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
            query = request.url.params["q"]
            return httpx.Response(200, json={"itemSummaries": items_by_query.get(query, [])})
        raise AssertionError(f"unexpected request: {request.url}")

    return httpx.MockTransport(handler)


def _patch_transport(monkeypatch, transport):
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_fetch_products_maps_real_browse_api_shape(monkeypatch):
    dress_item = {
        "itemId": "v1|123456789|0",
        "title": "Red Evening Gown Size M",
        "price": {"value": "49.99", "currency": "USD"},
        "itemWebUrl": "https://www.ebay.com/itm/123456789",
        "image": {"imageUrl": "https://i.ebayimg.com/main.jpg"},
        "additionalImages": [{"imageUrl": "https://i.ebayimg.com/alt.jpg"}],
        "categories": [{"categoryName": "Women's Dresses"}],
        "condition": "NEW",
    }
    transport = _fake_transport(items_by_query={"dress": [dress_item]})
    _patch_transport(monkeypatch, transport)

    provider = EbayProductProvider(client_id="cid", client_secret="csecret", campaign_id=None)
    products = await provider.fetch_products(limit=5)

    assert len(products) == 1
    p = products[0]
    assert isinstance(p, RawProduct)
    assert p.retailer_product_id == "v1|123456789|0"
    assert p.name == "Red Evening Gown Size M"
    assert p.price_cents == 4999
    assert p.currency == "usd"
    assert p.product_url == "https://www.ebay.com/itm/123456789"
    assert p.images == ["https://i.ebayimg.com/main.jpg", "https://i.ebayimg.com/alt.jpg"]
    assert p.category_slug == "dresses"
    assert p.availability == "in_stock"


async def test_fetch_products_skips_unusable_items_and_dedupes(monkeypatch):
    good = {
        "itemId": "v1|good|0",
        "title": "Denim Jacket",
        "price": {"value": "20.00", "currency": "USD"},
        "itemWebUrl": "https://www.ebay.com/itm/good",
        "image": {"imageUrl": "https://i.ebayimg.com/good.jpg"},
    }
    missing_price = {
        "itemId": "v1|bad|0",
        "title": "No price item",
        "itemWebUrl": "https://www.ebay.com/itm/bad",
    }
    transport = _fake_transport(items_by_query={"jacket": [good, missing_price, good]})
    _patch_transport(monkeypatch, transport)

    provider = EbayProductProvider(client_id="cid", client_secret="csecret", campaign_id=None)
    products = await provider._search(
        httpx.AsyncClient(), {"Authorization": "Bearer x", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}, "jacket", "jackets", 10
    )
    assert [p.retailer_product_id for p in products] == ["v1|good|0", "v1|good|0"]


async def test_search_live_returns_real_matches_for_an_arbitrary_query(monkeypatch):
    jacket_item = {
        "itemId": "v1|999|0",
        "title": "Lee Riders Blue Denim Jacket",
        "price": {"value": "30.00", "currency": "USD"},
        "itemWebUrl": "https://www.ebay.com/itm/999",
        "image": {"imageUrl": "https://i.ebayimg.com/jacket.jpg"},
    }
    transport = _fake_transport(items_by_query={"denim jacket": [jacket_item]})
    _patch_transport(monkeypatch, transport)

    provider = EbayProductProvider(client_id="cid", client_secret="csecret", campaign_id=None)
    products = await provider.search_live(query="denim jacket", limit=10)

    assert len(products) == 1
    assert products[0].retailer_product_id == "v1|999|0"
    assert products[0].name == "Lee Riders Blue Denim Jacket"


def test_build_affiliate_url_uses_campaign_id_when_set():
    provider = EbayProductProvider(client_id="cid", client_secret="csecret", campaign_id="epn-123")
    url = provider.build_affiliate_url("https://www.ebay.com/itm/1", tracking_tag="tryonu-20")
    assert url == "https://www.ebay.com/itm/1?campid=epn-123"


def test_build_affiliate_url_falls_back_to_tracking_tag_without_campaign_id():
    provider = EbayProductProvider(client_id="cid", client_secret="csecret", campaign_id=None)
    url = provider.build_affiliate_url("https://www.ebay.com/itm/1", tracking_tag="tryonu-20")
    assert url == "https://www.ebay.com/itm/1?campid=tryonu-20"
