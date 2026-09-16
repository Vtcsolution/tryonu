"""The AI stylist's core safety contract: it can only ever return product
ids that are real, saved rows in our database — never an invented
product, never an out-of-range index even if the LLM provider returns
one. Candidates are fetched live (mocked here, no real network) rather
than from a pre-synced local catalog — see live_search_service.py; a
candidate only becomes a saved row once the LLM actually chooses it."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.llm.base import StylistCandidate, StylistQuery, StylistRecommendation
from app.models.product import Product
from app.retailers.base import RawProduct
from app.services.live_search_service import LiveSearchResult
from tests.conftest import register_and_login


class _FakeLiveProvider:
    slug = "ebay"
    display_name = "eBay"

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        return f"{product_url}?campid={tracking_tag}"


def _raw(name: str, **overrides) -> RawProduct:
    defaults = dict(
        retailer_product_id=f"live-{name}",
        name=name,
        price_cents=5000,
        currency="usd",
        product_url=f"https://www.ebay.com/itm/{name}",
        images=["https://i.ebayimg.com/img.jpg"],
    )
    defaults.update(overrides)
    return RawProduct(**defaults)


def _live_results(*names_or_raws: str | RawProduct) -> list[LiveSearchResult]:
    provider = _FakeLiveProvider()
    return [
        LiveSearchResult(provider=provider, raw=r if isinstance(r, RawProduct) else _raw(r))
        for r in names_or_raws
    ]


def _patch_live_search(monkeypatch, results: list[LiveSearchResult]):
    async def fake_live_search(query: str, *, limit: int = 24):
        return results

    monkeypatch.setattr("app.services.stylist_service.live_search", fake_live_search)


async def test_stylist_recommends_only_real_persisted_products(client, db, monkeypatch):
    _patch_live_search(monkeypatch, _live_results("Black Blazer", "Black Trousers"))
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/stylist/ask",
        json={"prompt": "black formal outfit for a wedding under $300", "max_items": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["products"]) > 0

    # Every returned product must be a real row that now actually exists in
    # the DB — never an id the backend just made up. Since candidates come
    # from a live (mocked) search, not a pre-synced catalog, this also
    # proves the LLM's chosen items got persisted, not just echoed back.
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
    _patch_live_search(monkeypatch, _live_results("A Real Product"))
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "anything", "max_items": 5})
    assert resp.status_code == 200
    products = resp.json()["products"]

    # exactly one survives — the 3 out-of-range indexes (9999, -5, 42) were
    # dropped, not used to fabricate placeholder products
    assert len(products) == 1
    real_ids = (await db.execute(select(Product.id))).scalars().all()
    assert products[0]["id"] in real_ids


async def test_stylist_history_is_scoped_to_the_current_user(client, monkeypatch):
    _patch_live_search(monkeypatch, _live_results("History Item"))

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


async def test_stylist_passes_recent_turns_as_context_on_a_follow_up(client, monkeypatch):
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
    _patch_live_search(monkeypatch, _live_results("Memory Item"))
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


async def test_stylist_with_wardrobe_item_biases_candidates_toward_it(client, monkeypatch):
    """"Build an outfit around my black trousers" — the wardrobe item is
    never a candidate itself (it's not a catalog Product); it should just
    bias which real products the LLM even gets to see."""
    from app.schemas.stylist import StylistAskRequest
    from app.services.stylist_service import _fetch_candidates, _wardrobe_anchor_profile

    on_taste = _raw("Black Formal Shirt", color="black", style_tags=["formal"])
    off_taste = _raw("Neon Sports Tee", color="neon green", style_tags=["athleisure"])
    _patch_live_search(monkeypatch, _live_results(on_taste, off_taste))
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

    # Rebuild the same anchor profile ask_stylist derived from the wardrobe
    # item, and re-run the candidate fetch directly — the pool is fully
    # controlled by the mock (just these two items), so ranking is
    # deterministic, unlike the old DB-backed version which had to hedge
    # against a shared test-session table with other tests' unrelated rows.
    from app.models.wardrobe import WardrobeItem

    anchor_item = WardrobeItem(user_id="anchor", name="Black Trousers", color="black", style_tags=["formal"])
    anchor_profile = _wardrobe_anchor_profile(anchor_item)
    req = StylistAskRequest(prompt="what goes with this", max_items=3)
    candidates = await _fetch_candidates(req, anchor_profile)
    names = [c.raw.name for c in candidates]

    assert on_taste.name in names
    assert names.index(on_taste.name) < names.index(off_taste.name)


async def test_stylist_rejects_another_users_wardrobe_item(client):
    await register_and_login(client)
    item_resp = await client.post("/api/v1/wardrobe", json={"name": "Owner's Item"})
    wardrobe_item_id = item_resp.json()["id"]

    await register_and_login(client)  # a different user
    resp = await client.post(
        "/api/v1/stylist/ask", json={"prompt": "anything", "wardrobe_item_id": wardrobe_item_id}
    )
    assert resp.status_code == 404


async def test_chat_recommend_outfit_routes_all_use_the_same_real_products_engine(client, db, monkeypatch):
    """/chat, /recommend and /outfit are thin wrappers around the same
    ask_stylist() logic as /ask (see api/v1/endpoints/stylist.py) — confirm
    each route is wired up and honors the same real-products-only contract."""
    await register_and_login(client)

    for route in ("chat", "recommend", "outfit"):
        _patch_live_search(monkeypatch, _live_results(f"{route.title()} Route Shirt"))
        resp = await client.post(
            f"/api/v1/stylist/{route}",
            json={"prompt": "something casual", "max_items": 3},
        )
        assert resp.status_code == 200, route
        body = resp.json()
        assert body["products"]  # each route actually returned something to check

        returned_ids = {p["id"] for p in body["products"]}
        real_ids = set((await db.execute(select(Product.id).where(Product.id.in_(returned_ids)))).scalars().all())
        assert returned_ids == real_ids
