"""The two live-search HTTP endpoints: GET /search/live (no DB reads/writes,
just proxies live_search_service) and POST /products/select-live (the one
place a live result becomes a real, saved Product with a real id)."""

from __future__ import annotations

from app.retailers.base import RawProduct
from app.services.live_search_service import LiveSearchResult
from tests.conftest import register_and_login


class _FakeEbayProvider:
    slug = "ebay"
    display_name = "eBay"

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        return f"{product_url}?campid={tracking_tag}"


def _raw(pid: str = "v1|123|0", name: str = "Denim Jacket") -> RawProduct:
    return RawProduct(
        retailer_product_id=pid,
        name=name,
        price_cents=3000,
        currency="usd",
        product_url="https://www.ebay.com/itm/123",
        images=["https://i.ebayimg.com/jacket.jpg"],
    )


async def test_search_live_rejects_empty_query(client):
    resp = await client.get("/api/v1/search/live", params={"q": " "})
    assert resp.status_code == 400


async def test_search_live_returns_real_shaped_results(client, monkeypatch):
    async def fake_live_search(query, *, limit=24):
        return [LiveSearchResult(provider=_FakeEbayProvider(), raw=_raw())]

    monkeypatch.setattr("app.api.v1.endpoints.search.live_search", fake_live_search)

    resp = await client.get("/api/v1/search/live", params={"q": "denim jacket"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["retailer_slug"] == "ebay"
    assert body[0]["retailer_product_id"] == "v1|123|0"
    assert body[0]["name"] == "Denim Jacket"
    assert "id" not in body[0]  # never has a DB id — it isn't saved


async def test_select_live_requires_auth(client, monkeypatch):
    resp = await client.post(
        "/api/v1/products/select-live",
        json={"query": "denim jacket", "retailer_slug": "ebay", "retailer_product_id": "v1|123|0"},
    )
    assert resp.status_code == 401


async def test_select_live_persists_a_real_product(client, db, monkeypatch):
    async def fake_find_live_result(query, *, retailer_slug, retailer_product_id):
        return LiveSearchResult(provider=_FakeEbayProvider(), raw=_raw(retailer_product_id, "Denim Jacket"))

    monkeypatch.setattr("app.api.v1.endpoints.products.find_live_result", fake_find_live_result)
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/products/select-live",
        json={"query": "denim jacket", "retailer_slug": "ebay", "retailer_product_id": "v1|123|0"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"]  # now has a real DB id
    assert body["name"] == "Denim Jacket"
    assert body["retailer"]["slug"] == "ebay"

    # it's now a normal product, reachable the normal way
    get_resp = await client.get(f"/api/v1/products/{body['id']}")
    assert get_resp.status_code == 200


async def test_select_live_returns_404_when_the_item_is_gone(client, monkeypatch):
    async def fake_find_live_result(query, *, retailer_slug, retailer_product_id):
        return None

    monkeypatch.setattr("app.api.v1.endpoints.products.find_live_result", fake_find_live_result)
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/products/select-live",
        json={"query": "denim jacket", "retailer_slug": "ebay", "retailer_product_id": "gone"},
    )
    assert resp.status_code == 404


async def test_a_shop_link_for_a_live_product_saves_it_counts_the_click_and_opens_the_shop(client, db, monkeypatch):
    """The home page's example look links to products that aren't saved yet."""
    from sqlalchemy import func, select

    from app.models.affiliate import AffiliateClick

    async def fake_find_live_result(query, *, retailer_slug, retailer_product_id):  # noqa: ANN001, ANN202, ARG001
        return LiveSearchResult(provider=_FakeEbayProvider(), raw=_raw(retailer_product_id)) if retailer_product_id == "v1|9|0" else None

    monkeypatch.setattr("app.services.live_search_service.find_live_result", fake_find_live_result)
    before = await db.scalar(select(func.count(AffiliateClick.id)))
    resp = await client.get("/api/v1/affiliate/live", params={"r": "ebay", "id": "v1|9|0", "q": "denim jacket"})
    assert resp.status_code == 302 and "ebay" in resp.headers["location"]
    assert await db.scalar(select(func.count(AffiliateClick.id))) == before + 1

    ended = await client.get("/api/v1/affiliate/live", params={"r": "ebay", "id": "gone", "q": "denim jacket"})
    assert ended.status_code == 302 and ended.headers["location"].endswith("/try")


async def test_the_home_example_look_lists_its_products_with_live_prices(client, monkeypatch):
    """The slider's products come from the shops; one that's gone is left out."""
    from app.api.v1.endpoints import showcase

    async def fake_find_live_result(query, *, retailer_slug, retailer_product_id):  # noqa: ANN001, ANN202, ARG001
        if retailer_product_id == showcase.LOOK[0]["id"]:
            return None  # the shop stopped selling it
        return LiveSearchResult(provider=_FakeEbayProvider(), raw=_raw(retailer_product_id))

    monkeypatch.setattr("app.services.live_search_service.find_live_result", fake_find_live_result)
    monkeypatch.setattr(showcase, "_cache", None)
    items = (await client.get("/api/v1/showcase/look")).json()
    assert [i["name"] for i in items] == [x["name"] for x in showcase.LOOK[1:]]
    assert items[0]["price_cents"] == 3000 and "/api/v1/affiliate/live?" in items[0]["buy_url"]
