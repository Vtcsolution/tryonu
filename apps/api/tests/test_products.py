"""Product listing/search never returns anything that wasn't actually
seeded into the DB — the core "no invented products" guarantee, tested at
the catalog layer."""

from __future__ import annotations

from tests.conftest import seed_product


async def test_list_products_returns_only_real_seeded_products(client, db):
    p1 = await seed_product(db, name="Cream Poncho", price_cents=3200)
    p2 = await seed_product(db, name="Rust Bomber Jacket", price_cents=9900)

    # High limit — the DB is shared across the whole test session, so by
    # the time this runs there may be more than the default page size (24)
    # of other tests' products already in it.
    resp = await client.get("/api/v1/products", params={"limit": 100})
    assert resp.status_code == 200
    body = resp.json()
    names = {item["name"] for item in body["items"]}
    assert {"Cream Poncho", "Rust Bomber Jacket"} <= names
    ids = {item["id"] for item in body["items"]}
    assert p1.id in ids and p2.id in ids


async def test_price_filter_excludes_out_of_range_products(client, db):
    cheap = await seed_product(db, name="Cheap Tee", price_cents=1000)
    pricey = await seed_product(db, name="Pricey Coat", price_cents=50000)

    resp = await client.get("/api/v1/products", params={"max_price_cents": 5000})
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert cheap.id in ids
    assert pricey.id not in ids


async def test_get_single_product(client, db):
    p = await seed_product(db, name="Solo Item")
    resp = await client.get(f"/api/v1/products/{p.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Solo Item"


async def test_get_missing_product_is_404(client):
    resp = await client.get("/api/v1/products/does-not-exist")
    assert resp.status_code == 404


async def test_search_alias_route_matches_products_route(client, db):
    """/api/v1/search is a spec-mandated alias over the same catalog engine
    as /api/v1/products (see api/v1/endpoints/search.py) — not a second,
    divergent implementation."""
    p = await seed_product(db, name="Alias Route Hoodie", price_cents=6000)

    resp = await client.get("/api/v1/search", params={"q": "Alias Route Hoodie"})
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert p.id in ids
