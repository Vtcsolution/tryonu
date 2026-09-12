"""Rakuten Advertising provider — tested against the REAL, live-verified
contract (see app/retailers/rakuten.py's module docstring for exactly
what was confirmed against a real account: base URL, token flow, Product
Search's XML response shape, the real /v2/advertisers JSON schema, and
the confirmed-but-unconfirmed-shape partnerships endpoint).

Item-level product/coupon fields remain unconfirmed (this account has
zero approved advertiser partnerships, so no populated response has ever
been seen) — those tests validate our own best-effort XML parsing logic
against the contract this file defines, not a Rakuten-verified shape."""

from __future__ import annotations

import httpx
import pytest

from app.retailers.base import RawProduct
from app.retailers.errors import RetailerNotConfiguredError
from app.retailers.rakuten import RakutenAPIError, RakutenProductProvider


@pytest.fixture(autouse=True)
def _skip_real_throttle_sleep(monkeypatch):
    """The provider's outbound throttle (real, 0.5s between Rakuten calls
    in production) has no place adding real wall-clock time to tests."""

    async def _noop_sleep(*_a, **_kw):
        return None

    monkeypatch.setattr("app.retailers.rakuten.asyncio.sleep", _noop_sleep)


def _provider(**overrides) -> RakutenProductProvider:
    defaults = dict(
        enabled=True,
        client_id="cid",
        client_secret="csecret",
        access_token=None,
        refresh_token=None,
        publisher_id="pub123",
        account_id="acct123",
        base_url="https://api.linksynergy.test",
    )
    defaults.update(overrides)
    return RakutenProductProvider(**defaults)


def _patch_transport(monkeypatch, transport):
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


_DRESS_ITEM_XML = """
<item>
  <sku>RKT-1001</sku>
  <productname>Red Cocktail Dress</productname>
  <description>A knee-length red cocktail dress.</description>
  <brandname>Rakuten Fashion Co</brandname>
  <merchantname>Chic Boutique</merchantname>
  <mid>555</mid>
  <price currency="USD">39.99</price>
  <linkurl>https://click.linksynergy.com/deeplink?id=abc&amp;mid=555</linkurl>
  <imageurl>https://img.rakuten.example/dress.jpg</imageurl>
</item>
"""


def _search_xml(items: str = "", *, total: int | None = None) -> str:
    if total is not None:
        return f"<result><TotalMatches>{total}</TotalMatches><TotalPages>0</TotalPages><PageNumber>1</PageNumber></result>"
    return f"<result><TotalMatches>1</TotalMatches>{items}</result>"


# ---------------------------------------------------------------- config ---


async def test_disabled_raises_not_configured_with_zero_network_calls(monkeypatch):
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("must not make any network call while disabled")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider(enabled=False)
    with pytest.raises(RetailerNotConfiguredError, match="disabled"):
        await provider.fetch_products(limit=10)
    assert calls == []


async def test_missing_publisher_id_raises_not_configured():
    provider = _provider(publisher_id=None)
    with pytest.raises(RetailerNotConfiguredError, match="PUBLISHER_ID"):
        await provider.fetch_products(limit=10)


async def test_missing_all_credentials_raises_not_configured():
    provider = _provider(client_id=None, client_secret=None, access_token=None)
    with pytest.raises(RetailerNotConfiguredError):
        await provider.fetch_products(limit=10)


def test_describe_configuration_never_includes_secret_values():
    provider = _provider()
    info = provider.describe_configuration()
    assert info["has_client_credentials"] is True
    assert "cid" not in str(info.values())
    assert "csecret" not in str(info.values())


# ---------------------------------------------------------------- token ----


async def test_client_credentials_token_flow_and_search(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            assert request.headers["Authorization"].startswith("Basic ")
            body = request.content.decode()
            assert "grant_type=client_credentials" in body
            return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
        if request.url.path == "/productsearch/1.0":
            assert request.headers["Authorization"] == "Bearer tok-1"
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, text=_search_xml(_DRESS_ITEM_XML))
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=5)

    assert len(products) == 1
    p = products[0]
    assert isinstance(p, RawProduct)
    assert p.retailer_product_id == "RKT-1001"
    assert p.name == "Red Cocktail Dress"
    assert p.brand == "Rakuten Fashion Co"
    assert p.merchant_name == "Chic Boutique"
    assert p.merchant_id == "555"
    assert p.price_cents == 3999
    assert p.currency == "usd"
    assert p.product_url.startswith("https://click.linksynergy.com")
    assert p.images == ["https://img.rakuten.example/dress.jpg"]


async def test_direct_token_is_used_without_minting(monkeypatch):
    token_calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            token_calls.append(request)
            return httpx.Response(200, json={"access_token": "should-not-be-used"})
        if request.url.path == "/productsearch/1.0":
            assert request.headers["Authorization"] == "Bearer direct-token-abc"
            return httpx.Response(200, text=_search_xml(total=0))
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider(client_id=None, client_secret=None, access_token="direct-token-abc")
    await provider.fetch_products(limit=5)
    assert token_calls == []


async def test_401_triggers_a_real_refresh_via_client_credentials(monkeypatch):
    call_count = {"token": 0, "search": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            call_count["token"] += 1
            return httpx.Response(200, json={"access_token": f"tok-{call_count['token']}", "expires_in": 3600})
        if request.url.path == "/productsearch/1.0":
            call_count["search"] += 1
            if call_count["search"] == 1:
                return httpx.Response(401, text="expired")
            assert request.headers["Authorization"] == "Bearer tok-2"
            return httpx.Response(200, text=_search_xml(_DRESS_ITEM_XML))
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=5)
    assert call_count["token"] == 2  # initial mint + forced re-mint after the 401
    assert len(products) >= 1


async def test_401_with_refresh_token_path_uses_refresh_grant(monkeypatch):
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            body = request.content.decode()
            calls.append(body)
            if "grant_type=refresh_token" in body:
                assert "refresh_token=refresh-abc" in body
                return httpx.Response(200, json={"access_token": "tok-refreshed", "expires_in": 3600})
            raise AssertionError("should not mint via client_credentials when using a direct token")
        if request.url.path == "/productsearch/1.0":
            if request.headers["Authorization"] == "Bearer direct-token":
                return httpx.Response(401, text="expired")
            assert request.headers["Authorization"] == "Bearer tok-refreshed"
            return httpx.Response(200, text=_search_xml(total=0))
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider(
        client_id=None, client_secret=None, access_token="direct-token", refresh_token="refresh-abc"
    )
    await provider.fetch_products(limit=5)
    assert any("refresh_token" in c for c in calls)


# --------------------------------------------------------------- errors ----


async def test_rate_limit_response_raises_rakuten_api_error(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(429, text="Too Many Requests")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    with pytest.raises(RakutenAPIError, match="rate limit"):
        await provider.fetch_products(limit=5)


async def test_malformed_xml_response_raises_a_clear_error(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text="<result><unclosed>")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    with pytest.raises(RakutenAPIError, match="malformed"):
        await provider.fetch_products(limit=5)


async def test_server_error_raises_rakuten_api_error(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(503, text="Service Unavailable")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    with pytest.raises(RakutenAPIError):
        await provider.fetch_products(limit=5)


async def test_no_products_returns_empty_list_not_an_error(monkeypatch):
    """Confirmed live: TotalMatches=0 is a normal HTTP 200 outcome."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=_search_xml(total=0))

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=5)
    assert products == []


async def test_no_approval_error_returns_empty_list_not_an_error(monkeypatch):
    """Confirmed live, verbatim: a 200 response with this exact <Errors>
    body when the account has no relationship with the queried
    advertiser. Must be treated as zero results, not a crash."""

    real_confirmed_error_xml = (
        "<result><Errors><ErrorID>7186919</ErrorID>"
        "<ErrorText>No matching products found. Possible reasons include lack of approval "
        "from the specified Advertiser or no active relationships with any Advertiser.</ErrorText>"
        "</Errors></result>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=real_confirmed_error_xml)

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=5)
    assert products == []


async def test_items_missing_required_fields_are_skipped_not_fabricated(monkeypatch):
    incomplete_item = "<item><sku>RKT-2</sku><productname>No price item</productname></item>"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=_search_xml(incomplete_item + _DRESS_ITEM_XML))

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=5)
    assert len(products) == 1
    assert products[0].retailer_product_id == "RKT-1001"


# ------------------------------------------------------------ dedup/pool ---


async def test_fetch_products_dedupes_across_search_terms(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=_search_xml(_DRESS_ITEM_XML))  # every keyword "finds" the same SKU

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=100)
    ids = [p.retailer_product_id for p in products]
    assert len(ids) == len(set(ids))  # no duplicates despite 12 search terms all matching


async def test_fetch_products_respects_limit(monkeypatch):
    items_xml = "".join(
        f'<item><sku>RKT-{i}</sku><productname>Item {i}</productname>'
        f'<price currency="USD">10.00</price><linkurl>https://x.example/{i}</linkurl></item>'
        for i in range(20)
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=f"<result><TotalMatches>20</TotalMatches>{items_xml}</result>")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    products = await provider.fetch_products(limit=7)
    assert len(products) == 7


# --------------------------------------------------------- affiliate url ---


def test_build_affiliate_url_is_a_passthrough():
    provider = _provider()
    url = "https://click.linksynergy.com/deeplink?id=abc&mid=555"
    assert provider.build_affiliate_url(url, tracking_tag="tryonu-20") == url


# ------------------------------------------- advertisers/partnerships/etc --


async def test_list_advertisers_normalizes_the_real_v2_json_shape(monkeypatch):
    """Shape confirmed live against /v2/advertisers with a real account."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if request.url.path == "/v2/advertisers":
            return httpx.Response(
                200,
                json={
                    "_metadata": {"page": 1, "limit": 1, "total": 1},
                    "advertisers": [
                        {
                            "network": 3,
                            "id": 50524,
                            "name": "VIEVE",
                            "url": "https://www.vievebeauty.com",
                            "logo_url": "https://merchant.linksynergy.com/fs/logo/lg_50524",
                            "policies": {"international_capabilities": {"ships_to": ["US", "CA", "GB"]}},
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    advertisers = await provider.list_advertisers(keyword="beauty")
    assert len(advertisers) == 1
    a = advertisers[0]
    assert a.mid == "50524"
    assert a.name == "VIEVE"
    assert a.countries_shipped_to == ["US", "CA", "GB"]


async def test_list_partnerships_requires_advertiser_ids():
    provider = _provider()
    with pytest.raises(ValueError, match="advertiser id"):
        await provider.list_partnerships(advertiser_ids=[])


async def test_list_partnerships_sends_advertiser_id_param(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if request.url.path == "/v2/advertisers/joined":
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"advertisers": [{"id": 50524, "name": "VIEVE", "status": "joined"}]})
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    partnerships = await provider.list_partnerships(advertiser_ids=["50524", "775"])
    assert captured["params"]["advertiser-id"] == "50524,775"
    assert partnerships[0].status == "joined"


async def test_list_offers_surfaces_a_clear_error_for_the_unconfirmed_endpoint(monkeypatch):
    """Confirmed live: no working Offers endpoint has been found — this
    must raise clearly, never silently return an empty/fabricated list."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(404, json={"message": "no Route matched with those values"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    with pytest.raises(RakutenAPIError):
        await provider.list_offers()


async def test_list_coupons_parses_the_confirmed_xml_wrapper(monkeypatch):
    coupon_xml = (
        "<couponfeed><TotalMatches>1</TotalMatches>"
        "<link><linkid>cpn-1</linkid><mid>555</mid><advertisername>Chic Boutique</advertisername>"
        "<offerdescription>10% off</offerdescription><couponcode>TRYONU10</couponcode></link>"
        "</couponfeed>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if request.url.path == "/coupon/1.0":
            return httpx.Response(200, text=coupon_xml)
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    coupons = await provider.list_coupons()
    assert coupons[0].code == "TRYONU10"
    assert coupons[0].advertiser_name == "Chic Boutique"


async def test_list_coupons_no_matches_returns_empty_list(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text="<couponfeed><TotalMatches>0</TotalMatches></couponfeed>")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    provider = _provider()
    assert await provider.list_coupons() == []


async def test_advertisers_coupons_require_configuration():
    provider = _provider(enabled=False)
    with pytest.raises(RetailerNotConfiguredError):
        await provider.list_advertisers()
    with pytest.raises(RetailerNotConfiguredError):
        await provider.list_coupons()
    with pytest.raises(RetailerNotConfiguredError):
        await provider.list_partnerships(advertiser_ids=["1"])
