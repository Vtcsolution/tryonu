"""Personalization data capture: search/product-view events are logged
without changing the response shape or behavior of the endpoints that
trigger them — this is silent, best-effort instrumentation for Phase 4."""

from __future__ import annotations

from sqlalchemy import select

from app.models.history import ProductView, SearchHistory
from tests.conftest import register_and_login, seed_product


async def test_search_with_query_logs_search_history(client, db):
    await seed_product(db, name="Logged Search Item")
    await register_and_login(client)

    resp = await client.get("/api/v1/products", params={"q": "Logged Search Item"})
    assert resp.status_code == 200

    rows = (await db.execute(select(SearchHistory))).scalars().all()
    assert any(r.query == "Logged Search Item" for r in rows)


async def test_plain_browse_without_query_does_not_log_search_history(client, db):
    """The DB is shared across this whole test file (session-scoped), so
    other tests' searches are already in the table — assert the count
    doesn't change from a browse-only call, not that the table is empty."""
    await seed_product(db, name="Browse Only Item")
    await register_and_login(client)

    before = len((await db.execute(select(SearchHistory))).scalars().all())
    resp = await client.get("/api/v1/products", params={"limit": 5})
    assert resp.status_code == 200

    after = len((await db.execute(select(SearchHistory))).scalars().all())
    assert after == before


async def test_search_alias_route_also_logs_history(client, db):
    await seed_product(db, name="Alias Logged Item")
    await register_and_login(client)

    await client.get("/api/v1/search", params={"q": "Alias Logged Item"})

    rows = (await db.execute(select(SearchHistory))).scalars().all()
    assert any(r.query == "Alias Logged Item" for r in rows)


async def test_search_history_captures_anonymous_users_too(client, db):
    product = await seed_product(db, name="Anon Search Item")
    resp = await client.get("/api/v1/products", params={"q": "Anon Search Item"})
    assert resp.status_code == 200

    rows = (await db.execute(select(SearchHistory).where(SearchHistory.query == "Anon Search Item"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id is None
    assert product.id  # sanity: product exists and was matched (result_count > 0)
    assert rows[0].result_count >= 1


async def test_get_product_logs_a_product_view(client, db):
    product = await seed_product(db, name="Viewed Item")
    await register_and_login(client)

    resp = await client.get(f"/api/v1/products/{product.id}")
    assert resp.status_code == 200

    rows = (await db.execute(select(ProductView).where(ProductView.product_id == product.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "detail"
    assert rows[0].user_id is not None
