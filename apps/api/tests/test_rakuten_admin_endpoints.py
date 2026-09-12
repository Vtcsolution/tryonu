"""Rakuten admin endpoints: role-gated like every other /admin/* route,
correct error-status mapping (not-configured vs upstream failure), and —
the important one — zero credential leakage in any response."""

from __future__ import annotations

import httpx
import pytest

from app.retailers.rakuten import RakutenProductProvider
from tests.conftest import make_admin, register_and_login


def _fake_provider(monkeypatch, handler, **overrides):
    async def _noop_sleep(*_a, **_kw):
        return None

    monkeypatch.setattr("app.retailers.rakuten.asyncio.sleep", _noop_sleep)

    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    defaults = dict(
        enabled=True,
        client_id="cid",
        client_secret="super-secret-value",
        access_token=None,
        refresh_token=None,
        publisher_id="pub123",
        account_id="acct123",
        base_url="https://api.rakutenmarketing.test",
    )
    defaults.update(overrides)
    provider = RakutenProductProvider(**defaults)
    monkeypatch.setattr("app.api.v1.endpoints.admin_rakuten.get_rakuten_provider", lambda: provider)
    return provider


async def _admin_client(client, db):
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    return data


async def test_status_endpoint_is_admin_only(client, db, monkeypatch):
    _fake_provider(monkeypatch, lambda r: httpx.Response(200, json={}))

    await register_and_login(client)
    resp = await client.get("/api/v1/admin/rakuten/status")
    assert resp.status_code == 403


async def test_status_endpoint_never_leaks_the_secret(client, db, monkeypatch):
    _fake_provider(monkeypatch, lambda r: httpx.Response(200, json={}))
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "super-secret-value" not in resp.text
    assert body["has_client_credentials"] is True
    assert body["configured"] is True


async def test_status_reports_not_configured_when_disabled(client, db, monkeypatch):
    _fake_provider(monkeypatch, lambda r: httpx.Response(200, json={}), enabled=False)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["configured"] is False


async def test_search_preview_returns_409_when_not_configured(client, db, monkeypatch):
    _fake_provider(monkeypatch, lambda r: httpx.Response(200, json={}), enabled=False)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/search", params={"keyword": "dress"})
    assert resp.status_code == 409


async def test_search_preview_returns_502_on_upstream_failure(client, db, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(503, text="down")

    _fake_provider(monkeypatch, handler)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/search", params={"keyword": "dress"})
    assert resp.status_code == 502
    assert "super-secret-value" not in resp.text


async def test_search_preview_returns_real_shaped_results(client, db, monkeypatch):
    item_xml = (
        "<item><sku>RKT-9</sku><productname>Denim Jacket</productname>"
        "<merchantname>Denim Co</merchantname><mid>42</mid>"
        '<price currency="USD">59.00</price>'
        "<linkurl>https://click.example/deeplink?mid=42</linkurl>"
        "<imageurl>https://img.example/jacket.jpg</imageurl></item>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=f"<result><TotalMatches>1</TotalMatches>{item_xml}</result>")

    _fake_provider(monkeypatch, handler)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/search", params={"keyword": "jacket"})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["retailer_product_id"] == "RKT-9"
    assert body[0]["merchant_name"] == "Denim Co"
    assert body[0]["price_cents"] == 5900


async def test_advertisers_endpoint_is_admin_only(client, db, monkeypatch):
    _fake_provider(monkeypatch, lambda r: httpx.Response(200, json={"advertisers": []}))
    await register_and_login(client)
    resp = await client.get("/api/v1/admin/rakuten/advertisers")
    assert resp.status_code == 403


async def test_advertisers_endpoint_returns_normalized_rows(client, db, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "_metadata": {"total": 1},
                "advertisers": [
                    {
                        "network": "rakuten",
                        "id": 7,
                        "name": "Fashion Co",
                        "url": "https://fashionco.example",
                        "status": "active",
                        "policies": {"international_capabilities": {"ships_to": ["US", "CA"]}},
                    }
                ],
            },
        )

    _fake_provider(monkeypatch, handler)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/advertisers")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["mid"] == "7"
    assert body[0]["name"] == "Fashion Co"
    assert body[0]["countries_shipped_to"] == ["US", "CA"]


async def test_partnerships_endpoint_requires_advertiser_ids(client, db, monkeypatch):
    _fake_provider(monkeypatch, lambda r: httpx.Response(200, json={}))
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/partnerships")
    assert resp.status_code == 422  # missing required query param


async def test_partnerships_endpoint(client, db, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.url.path == "/v2/advertisers/joined"
        assert request.url.params["advertiser-id"] == "7"
        return httpx.Response(
            200, json={"partnerships": [{"mid": 7, "advertisername": "Fashion Co", "status": "joined"}]}
        )

    _fake_provider(monkeypatch, handler)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/partnerships", params={"advertiser_ids": "7"})
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "joined"


async def test_offers_endpoint_omits_commission_when_rakuten_does(client, db, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json={"offers": [{"id": "o1", "mid": 7, "title": "Sale"}]})

    _fake_provider(monkeypatch, handler)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/offers")
    assert resp.status_code == 200
    assert resp.json()[0]["commission_rate"] is None


async def test_coupons_endpoint(client, db, monkeypatch):
    link_xml = (
        "<link><linkid>c1</linkid><mid>7</mid><advertisername>Fashion Co</advertisername>"
        "<offerdescription>10% off</offerdescription><couponcode>SAVE10</couponcode></link>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=f"<couponfeed><TotalMatches>1</TotalMatches>{link_xml}</couponfeed>")

    _fake_provider(monkeypatch, handler)
    await _admin_client(client, db)

    resp = await client.get("/api/v1/admin/rakuten/coupons")
    assert resp.status_code == 200
    assert resp.json()[0]["code"] == "SAVE10"
