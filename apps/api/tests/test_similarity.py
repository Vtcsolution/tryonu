"""Find similar / find cheaper: plain deterministic catalog queries, no
LLM involved — same category, real products only by construction."""

from __future__ import annotations

from tests.conftest import register_and_login, seed_product


async def test_similar_excludes_the_product_itself(client, db):
    target = await seed_product(db, name="Similar Target", price_cents=5000)
    other = await seed_product(db, name="Similar Other", price_cents=5500)
    await register_and_login(client)

    # A high limit here isn't about testing "top N" — it's so this
    # assertion about *filtering* (self-excluded, real peer included)
    # doesn't depend on where hash-fallback embeddings (no real OpenAI key
    # in tests) happen to rank `other` among however many other products
    # this shared test-session DB has accumulated by now.
    resp = await client.get(f"/api/v1/stylist/similar/{target.id}", params={"limit": 500})
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert target.id not in ids
    assert other.id in ids


async def test_similar_missing_product_is_404(client):
    await register_and_login(client)
    resp = await client.get("/api/v1/stylist/similar/does-not-exist")
    assert resp.status_code == 404


async def test_cheaper_only_returns_lower_priced_items(client, db):
    target = await seed_product(db, name="Cheaper Target", price_cents=5000)
    cheap = await seed_product(db, name="Actually Cheaper", price_cents=2000)
    pricey = await seed_product(db, name="Still Pricier", price_cents=9000)
    await register_and_login(client)

    resp = await client.get(f"/api/v1/stylist/cheaper/{target.id}", params={"limit": 500})
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert cheap.id in ids
    assert pricey.id not in ids
    assert target.id not in ids


async def test_cheaper_respects_limit(client, db):
    target = await seed_product(db, name="Limit Target", price_cents=10000)
    for i in range(10):
        await seed_product(db, name=f"Cheap Option {i}", price_cents=100 + i)
    await register_and_login(client)

    resp = await client.get(f"/api/v1/stylist/cheaper/{target.id}", params={"limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) <= 3
