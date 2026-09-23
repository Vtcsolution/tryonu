"""A shopper's saved / favourited / purchased products.

The contract: only products someone actually interacted with are stored,
what's stored is a snapshot that outlives the retailer's listing, and the
affiliate link stays attached however long ago it was saved.
"""

from __future__ import annotations

from app.models.product import Product
from app.models.saved_product import SavedProduct
from app.retailers.base import ProductProvider, RawProduct
from app.services.live_search_service import LiveSearchResult
from tests.conftest import register_and_login, seed_product


class _FakeProvider(ProductProvider):
    slug = "fakeshop"
    display_name = "Fake Shop"

    def __init__(self, items: list[RawProduct]):
        self._items = items

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # pragma: no cover
        return self._items

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        return self._items[:limit]

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        return f"{product_url}?aff={tracking_tag}"


def _raw(pid: str = "sku-1", price: int = 4999) -> RawProduct:
    return RawProduct(
        retailer_product_id=pid,
        name="Embroidered Pink Bridal Lehenga",
        price_cents=price,
        product_url=f"https://fakeshop.example/{pid}",
        images=["https://fakeshop.example/img.jpg"],
    )


def _patch_live(monkeypatch, items: list[RawProduct]):
    provider = _FakeProvider(items)

    async def fake_find(query, *, retailer_slug, retailer_product_id):
        match = next((i for i in items if i.retailer_product_id == retailer_product_id), None)
        return LiveSearchResult(provider=provider, raw=match) if match else None

    monkeypatch.setattr("app.services.saved_product_service.find_live_result", fake_find)
    return provider


async def test_saving_a_live_result_records_the_retailers_own_price_and_link(client, monkeypatch):
    _patch_live(monkeypatch, [_raw(price=4999)])
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/saved-products",
        json={
            "status": "favorite",
            "retailer_slug": "fakeshop",
            "retailer_product_id": "sku-1",
            "query": "pink bridal lehenga",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "favorite"
    assert body["name"] == "Embroidered Pink Bridal Lehenga"
    assert body["price_cents"] == 4999  # the retailer's price at this moment
    assert body["retailer_name"] == "Fake Shop"
    assert "affiliate_url" not in body  # opened through /go, never rebuilt by a client


async def test_a_client_cannot_invent_a_price_or_a_product(client, monkeypatch):
    """Nothing is taken on the client's word — the item is re-fetched from
    the retailer, and one it no longer lists cannot be saved at all."""
    _patch_live(monkeypatch, [_raw(price=4999)])
    await register_and_login(client)

    gone = await client.post(
        "/api/v1/saved-products",
        json={"retailer_slug": "fakeshop", "retailer_product_id": "not-listed", "query": "anything"},
    )
    assert gone.status_code == 404
    assert "no longer listed" in gone.json()["detail"]


async def test_saving_the_same_product_twice_moves_it_rather_than_duplicating(client, monkeypatch):
    _patch_live(monkeypatch, [_raw()])
    await register_and_login(client)

    body = {"retailer_slug": "fakeshop", "retailer_product_id": "sku-1", "query": "lehenga"}
    first = await client.post("/api/v1/saved-products", json={**body, "status": "saved"})
    second = await client.post("/api/v1/saved-products", json={**body, "status": "purchased"})
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["status"] == "purchased"

    listed = (await client.get("/api/v1/saved-products")).json()
    assert listed["total"] == 1


async def test_only_what_the_shopper_touched_is_saved(client, db, monkeypatch):
    """Two products exist in the catalog; saving one must not drag the
    other into their account."""
    _patch_live(monkeypatch, [_raw("sku-1"), _raw("sku-2")])
    await register_and_login(client)
    await client.post(
        "/api/v1/saved-products",
        json={"retailer_slug": "fakeshop", "retailer_product_id": "sku-2", "query": "lehenga"},
    )
    listed = (await client.get("/api/v1/saved-products")).json()
    assert [i["retailer_product_id"] for i in listed["items"]] == ["sku-2"]


async def test_a_saved_product_survives_the_retailer_pulling_the_listing(client, db, monkeypatch):
    """The point of a snapshot: the shopper still sees what they saved,
    with a working affiliate link, after we lose the catalog row."""
    _patch_live(monkeypatch, [_raw()])
    await register_and_login(client)
    saved = (
        await client.post(
            "/api/v1/saved-products",
            json={"retailer_slug": "fakeshop", "retailer_product_id": "sku-1", "query": "lehenga"},
        )
    ).json()

    row = await db.get(SavedProduct, saved["id"])
    await db.refresh(row)
    product = await db.get(Product, row.product_id)
    await db.delete(product)
    await db.commit()

    listed = (await client.get("/api/v1/saved-products")).json()
    assert listed["total"] == 1
    still_there = listed["items"][0]
    assert still_there["name"] == "Embroidered Pink Bridal Lehenga"
    assert still_there["image_url"] == "https://fakeshop.example/img.jpg"
    assert still_there["price_cents"] == 4999

    opened = await client.get(f"/api/v1/saved-products/{saved['id']}/go", follow_redirects=False)
    assert opened.status_code == 302
    assert opened.headers["location"].startswith("https://fakeshop.example/sku-1?aff=")


async def test_opening_a_saved_product_keeps_the_affiliate_link_and_counts_the_click(client, db, monkeypatch):
    from sqlalchemy import func, select

    from app.models.affiliate import AffiliateClick

    _patch_live(monkeypatch, [_raw()])
    await register_and_login(client)
    saved = (
        await client.post(
            "/api/v1/saved-products",
            json={"retailer_slug": "fakeshop", "retailer_product_id": "sku-1", "query": "lehenga"},
        )
    ).json()

    before = await db.scalar(select(func.count(AffiliateClick.id)))
    resp = await client.get(f"/api/v1/saved-products/{saved['id']}/go", follow_redirects=False)
    assert resp.status_code == 302
    assert "?aff=" in resp.headers["location"]
    await db.commit()
    assert await db.scalar(select(func.count(AffiliateClick.id))) == (before or 0) + 1


async def test_a_product_we_already_hold_can_be_saved_by_id(client, db):
    product = await seed_product(db, name="Kundan Bridal Set", price_cents=7500)
    await register_and_login(client)
    resp = await client.post("/api/v1/saved-products", json={"product_id": product.id, "status": "favorite"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["price_cents"] == 7500
    assert resp.json()["product_id"] == product.id


async def test_saved_products_are_private_to_their_owner(client, db):
    product = await seed_product(db, name="Private Kurta")
    await register_and_login(client)
    saved = (await client.post("/api/v1/saved-products", json={"product_id": product.id})).json()

    await register_and_login(client)  # a different shopper on the same client
    assert (await client.get("/api/v1/saved-products")).json()["total"] == 0
    assert (await client.patch(f"/api/v1/saved-products/{saved['id']}", json={"status": "favorite"})).status_code == 404
    assert (await client.delete(f"/api/v1/saved-products/{saved['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/saved-products/{saved['id']}/go", follow_redirects=False)).status_code == 404


async def test_status_can_be_changed_and_filtered(client, db):
    kurta = await seed_product(db, name="Filter Kurta")
    khussa = await seed_product(db, name="Filter Khussa")
    await register_and_login(client)
    a = (await client.post("/api/v1/saved-products", json={"product_id": kurta.id})).json()
    await client.post("/api/v1/saved-products", json={"product_id": khussa.id, "status": "favorite"})

    assert (await client.patch(f"/api/v1/saved-products/{a['id']}", json={"status": "purchased"})).status_code == 200
    favourites = (await client.get("/api/v1/saved-products", params={"status": "favorite"})).json()
    assert [i["name"] for i in favourites["items"]] == ["Filter Khussa"]
    bought = (await client.get("/api/v1/saved-products", params={"status": "purchased"})).json()
    assert [i["name"] for i in bought["items"]] == ["Filter Kurta"]


async def test_saving_needs_an_account(client, db):
    product = await seed_product(db, name="Anon Kurta")
    assert (await client.post("/api/v1/saved-products", json={"product_id": product.id})).status_code == 401
    assert (await client.get("/api/v1/saved-products")).status_code == 401
