"""The AI stylist's core safety contract: it can only ever return product
ids that are real rows in our database — never an invented product, and
never an out-of-range index even if the LLM provider returns one."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.llm.base import StylistCandidate, StylistQuery, StylistRecommendation
from app.models.product import Product
from tests.conftest import register_and_login, seed_product


async def test_stylist_recommends_only_real_seeded_products(client, db):
    await seed_product(db, name="Black Blazer", price_cents=12000)
    await seed_product(db, name="Black Trousers", price_cents=8000)

    await register_and_login(client)
    resp = await client.post(
        "/api/v1/stylist/ask",
        json={"prompt": "black formal outfit for a wedding under $300", "max_items": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["products"]) > 0

    # The DB is shared across this whole test file (and others seed
    # products too), so we can't assert *which* products come back — only
    # that every single one genuinely exists in the DB under the name the
    # API claims for it. A fabricated/hallucinated product would fail this.
    returned = {p["id"]: p["name"] for p in body["products"]}
    result = await db.execute(select(Product).where(Product.id.in_(returned.keys())))
    real_rows = {row.id: row.name for row in result.scalars().all()}
    assert returned == real_rows


async def test_stylist_ignores_out_of_range_indexes_from_the_llm(client, db, monkeypatch):
    """Even if the LLM provider misbehaves and returns an index outside the
    candidate list, the backend must silently drop it — never fabricate a
    product for it."""

    class EvilProvider:
        name = "evil"
        model = "evil-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            # returns a mix of one valid and several impossible indexes
            return StylistRecommendation(summary="ignore me", chosen_indexes=[0, 9999, -5, 42])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: EvilProvider())

    await seed_product(db, name="A Real Product")
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "anything", "max_items": 5})
    assert resp.status_code == 200
    products = resp.json()["products"]

    # exactly one survives — the 3 out-of-range indexes (9999, -5, 42) were
    # dropped, not used to fabricate placeholder products
    assert len(products) == 1
    real_ids = (await db.execute(select(Product.id))).scalars().all()
    assert products[0]["id"] in real_ids


async def test_stylist_history_is_scoped_to_the_current_user(client, db):
    await seed_product(db, name="History Item")

    await register_and_login(client)
    await client.post("/api/v1/stylist/ask", json={"prompt": "casual weekend outfit", "max_items": 3})

    resp = await client.get("/api/v1/stylist/history")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # a second, different user has no history of their own
    await register_and_login(client)
    resp = await client.get("/api/v1/stylist/history")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_chat_recommend_outfit_routes_all_use_the_same_real_products_engine(client, db):
    """/chat, /recommend and /outfit are thin wrappers around the same
    ask_stylist() logic as /ask (see api/v1/endpoints/stylist.py) — confirm
    each route is wired up and honors the same real-products-only contract."""
    await seed_product(db, name="Chat Route Shirt")
    await register_and_login(client)

    real_ids = set((await db.execute(select(Product.id))).scalars().all())

    for route in ("chat", "recommend", "outfit"):
        resp = await client.post(
            f"/api/v1/stylist/{route}",
            json={"prompt": "something casual", "max_items": 3},
        )
        assert resp.status_code == 200, route
        body = resp.json()
        for p in body["products"]:
            assert p["id"] in real_ids
