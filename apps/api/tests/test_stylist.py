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


async def test_stylist_passes_recent_turns_as_context_on_a_follow_up(client, db, monkeypatch):
    """Short-term memory: the second /ask call should see a recap of the
    first turn's prompt+summary, so a follow-up like "what shoes go with
    that" has something to refer to — without widening which products can
    be chosen (still index-validated against the current candidate list)."""
    captured_queries: list[StylistQuery] = []

    class SpyProvider:
        name = "spy"
        model = "spy-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            captured_queries.append(query)
            return StylistRecommendation(summary="a spy summary", chosen_indexes=[0] if candidates else [])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: SpyProvider())

    await seed_product(db, name="Memory Item")
    await register_and_login(client)

    resp1 = await client.post("/api/v1/stylist/ask", json={"prompt": "black casual outfit", "max_items": 3})
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/stylist/ask", json={"prompt": "what shoes go with that", "max_items": 3})
    assert resp2.status_code == 200

    assert len(captured_queries) == 2
    assert captured_queries[0].recent_context is None  # nothing before the first turn
    assert captured_queries[1].recent_context is not None
    assert "black casual outfit" in captured_queries[1].recent_context
    assert "a spy summary" in captured_queries[1].recent_context


async def test_stylist_with_wardrobe_item_biases_candidates_toward_it(client, db):
    """"Build an outfit around my black trousers" — the wardrobe item is
    never a candidate itself (it's not a catalog Product); it should just
    bias which real products the LLM even gets to see."""
    from app.services.stylist_service import _fetch_candidates
    from app.services.personalization_service import build_taste_profile

    on_taste = await seed_product(db, name="Black Formal Shirt", color="black", style_tags=["formal"])
    off_taste = await seed_product(db, name="Neon Sports Tee", color="neon green", style_tags=["athleisure"])
    await register_and_login(client)

    item_resp = await client.post(
        "/api/v1/wardrobe", json={"name": "Black Trousers", "color": "black", "style_tags": ["formal"]}
    )
    wardrobe_item_id = item_resp.json()["id"]

    resp = await client.post(
        "/api/v1/stylist/ask",
        json={"prompt": "what goes with this", "max_items": 3, "wardrobe_item_id": wardrobe_item_id},
    )
    assert resp.status_code == 200
    # the wardrobe item itself never appears as a "product" — it isn't one
    returned_ids = {p["id"] for p in resp.json()["products"]}
    assert wardrobe_item_id not in returned_ids

    from app.services.stylist_service import _wardrobe_anchor_profile
    from app.models.wardrobe import WardrobeItem

    item = await db.get(WardrobeItem, wardrobe_item_id)
    profile = _wardrobe_anchor_profile(item)
    from app.schemas.stylist import StylistAskRequest

    req = StylistAskRequest(prompt="what goes with this", max_items=3)
    candidates = await _fetch_candidates(db, req, profile)
    ids = [c.id for c in candidates]

    # on_taste (black/formal, matches the anchor) should survive the
    # affinity-ranked cut and rank near the top. off_taste isn't asserted
    # to survive at all — with many other zero-affinity products tied in
    # this shared test-session DB, being crowded out of the top N by
    # genuinely-irrelevant ties is the *correct* behavior, not a bug.
    assert on_taste.id in ids
    assert ids.index(on_taste.id) < 5
    if off_taste.id in ids:  # not guaranteed to survive the cut at all — see above
        assert ids.index(on_taste.id) < ids.index(off_taste.id)


async def test_stylist_rejects_another_users_wardrobe_item(client, db):
    await seed_product(db, name="Any Product")
    await register_and_login(client)
    item_resp = await client.post("/api/v1/wardrobe", json={"name": "Owner's Item"})
    wardrobe_item_id = item_resp.json()["id"]

    await register_and_login(client)  # a different user
    resp = await client.post(
        "/api/v1/stylist/ask", json={"prompt": "anything", "wardrobe_item_id": wardrobe_item_id}
    )
    assert resp.status_code == 404


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
