"""AliExpress affiliate provider: signing and response mapping.

No real AliExpress call is made here — the response shape asserted against
is the Open Platform's documented one
(aliexpress_affiliate_product_query_response -> resp_result -> result ->
products -> product[]). The signature is checked by recomputing it the way
the gateway does, so a change to the signing code can't pass silently.
"""

from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest

from app.retailers.aliexpress import AliExpressProductProvider
from app.retailers.errors import RetailerNotConfiguredError

APP_KEY, APP_SECRET, TRACKING = "12345", "sekret", "tryonu"


def _provider(**kw) -> AliExpressProductProvider:
    return AliExpressProductProvider(
        app_key=kw.pop("app_key", APP_KEY),
        app_secret=kw.pop("app_secret", APP_SECRET),
        tracking_id=kw.pop("tracking_id", TRACKING),
        **kw,
    )


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _row(**over) -> dict:
    row = {
        "product_id": "3256807",
        "product_title": "Pakistani Embroidered Khussa Shoes Women Handmade",
        "product_main_image_url": "https://ae01.alicdn.com/kf/main.jpg",
        "product_small_image_urls": {"string": ["https://ae01.alicdn.com/kf/a.jpg", "not-a-url"]},
        "target_sale_price": "23.45",
        "target_sale_price_currency": "USD",
        "promotion_link": "https://s.click.aliexpress.com/e/_abc123",
        "product_detail_url": "https://www.aliexpress.com/item/3256807.html",
        "evaluate_rate": "94.2%",
        "lastest_volume": 318,
        "shop_name": "Desi Craft Store",
        "shop_id": 4409,
        "first_level_category_name": "Shoes",
        "second_level_category_name": "Women Flats",
    }
    row.update(over)
    return row


def _body(*rows: dict) -> dict:
    return {
        "aliexpress_affiliate_product_query_response": {
            "resp_result": {"resp_code": 200, "result": {"products": {"product": list(rows)}}}
        }
    }


async def test_without_credentials_it_says_so_instead_of_calling(monkeypatch):
    def handler(request):  # pragma: no cover — must never be reached
        raise AssertionError("no request should be made without credentials")

    _patch_transport(monkeypatch, handler)
    for missing in ({"app_key": None}, {"app_secret": None}, {"tracking_id": None}):
        with pytest.raises(RetailerNotConfiguredError):
            await _provider(**missing).search_live(query="khussa", limit=5)


async def test_a_search_is_signed_the_way_the_gateway_verifies_it(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["form"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(200, json=_body(_row()))

    _patch_transport(monkeypatch, handler)
    await _provider().search_live(query="khussa shoes", limit=5)

    form = seen["form"]
    assert form["method"] == "aliexpress.affiliate.product.query"
    assert form["keywords"] == "khussa shoes"
    assert form["tracking_id"] == TRACKING  # no tracking id, no commission
    assert form["ship_to_country"] == "PK"

    sign = form.pop("sign")
    payload = "".join(f"{k}{form[k]}" for k in sorted(form))
    assert sign == hmac.new(APP_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest().upper()


async def test_a_product_maps_onto_our_shape(monkeypatch):
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=_body(_row())))
    [product] = await _provider().search_live(query="khussa", limit=5)

    assert product.retailer_product_id == "3256807"
    assert product.name.startswith("Pakistani Embroidered Khussa")
    assert product.price_cents == 2345  # the sale price, which is what the shopper pays
    assert product.currency == "usd"
    # the tracked link, not the plain one — that's what earns the commission
    assert product.product_url == "https://s.click.aliexpress.com/e/_abc123"
    assert product.images == ["https://ae01.alicdn.com/kf/main.jpg", "https://ae01.alicdn.com/kf/a.jpg"]
    assert product.rating == 4.71  # 94.2% of five stars
    assert product.rating_count == 318
    assert product.merchant_name == "Desi Craft Store"
    assert product.subcategory == "Women Flats"


async def test_a_tracked_link_is_never_rewritten(monkeypatch):
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=_body(_row())))
    provider = _provider()
    [product] = await provider.search_live(query="khussa", limit=5)
    assert provider.build_affiliate_url(product.product_url, tracking_tag="tryonu") == product.product_url
    plain = "https://www.aliexpress.com/item/1.html"
    assert provider.build_affiliate_url(plain, tracking_tag="tryonu") == f"{plain}?aff_short_key=tryonu"


async def test_rows_that_would_be_useless_are_dropped(monkeypatch):
    rows = [
        _row(product_id="ok"),
        _row(product_id="no-image", product_main_image_url=None, product_small_image_urls=None),
        _row(product_id="no-price", target_sale_price=None, target_original_price=None),
        _row(product_id="no-title", product_title=""),
    ]
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=_body(*rows)))
    found = await _provider().search_live(query="khussa", limit=10)
    assert [p.retailer_product_id for p in found] == ["ok"]


async def test_the_gateways_own_error_is_raised_not_returned_as_no_results(monkeypatch):
    """It answers 200 with an error_response body — treating that as "no
    results" would hide a bad key behind an empty shelf."""
    error = {"error_response": {"code": 15, "msg": "Remote service error", "sub_msg": "Invalid signature"}}
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=error))
    with pytest.raises(RuntimeError, match="Invalid signature"):
        await _provider().search_live(query="khussa", limit=5)


async def test_the_bulk_sync_keeps_going_when_one_term_fails(monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        form = dict(httpx.QueryParams(request.content.decode()))
        calls.append(form["keywords"])
        if len(calls) == 1:
            return httpx.Response(500, text="upstream hiccup")
        return httpx.Response(200, json=_body(_row(product_id=f"p{len(calls)}")))

    _patch_transport(monkeypatch, handler)
    products = await _provider().fetch_products(limit=12)
    assert len(calls) > 1  # it didn't stop at the failure
    assert products and len({p.retailer_product_id for p in products}) == len(products)


def test_the_deployments_own_variable_names_are_accepted(monkeypatch):
    """The server's .env spells these ALI_EXPRESS_*; both spellings load,
    so the names there never have to change."""
    from app.core.config import Settings

    for name in ("ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_TRACKING_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALI_EXPRESS_APP_KEY", "key-123")
    monkeypatch.setenv("ALI_EXPRESS_SECRET_API", "secret-456")
    monkeypatch.setenv("ALI_EXPRESS_TRACKING_ID", "tryonu")

    settings = Settings(_env_file=None)
    assert settings.ALIEXPRESS_APP_KEY == "key-123"
    assert settings.ALIEXPRESS_APP_SECRET == "secret-456"
    assert settings.ALIEXPRESS_TRACKING_ID == "tryonu"


async def test_what_is_missing_is_named_in_both_spellings():
    provider = AliExpressProductProvider(app_key=None, app_secret="s", tracking_id=None)
    with pytest.raises(RetailerNotConfiguredError) as exc:
        await provider.search_live(query="kurti", limit=3)
    message = str(exc.value)
    assert "ALIEXPRESS_APP_KEY" in message and "ALI_EXPRESS_APP_KEY" in message
    assert "TRACKING_ID" in message
    assert "APP_SECRET" not in message  # that one is already set


async def test_no_sort_parameter_is_sent(monkeypatch):
    """Verified against the live API: sort=SALE_PRICE_ASC comes back as
    resp_code 405 "The result is empty" for a query that returns products
    without it. Their own relevance order is what we want anyway."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["form"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(200, json=_body(_row()))

    _patch_transport(monkeypatch, handler)
    await _provider().search_live(query="khussa shoes", limit=5)
    assert "sort" not in seen["form"]


async def test_an_empty_result_is_no_products_not_an_error(monkeypatch):
    """The live shape for "nothing matched": resp_code 405, no result
    block at all. Raising on that would turn a thin search into an
    outage."""
    empty = {
        "aliexpress_affiliate_product_query_response": {
            "resp_result": {"resp_code": 405, "resp_msg": "The result is empty"},
            "request_id": "212a6b7f17902659669484789",
        }
    }
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=empty))
    assert await _provider().search_live(query="nothing at all", limit=5) == []
