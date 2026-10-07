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


class _FakeAliExpressProvider:
    slug = "aliexpress"
    display_name = "AliExpress"

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        return f"{product_url}?aff_short_key={tracking_tag}"


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


def _live_results(*names_or_raws: str | RawProduct, provider=None) -> list[LiveSearchResult]:
    provider = provider or _FakeLiveProvider()
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
    names = [c.result.raw.name for c in candidates]

    assert on_taste.name in names
    assert names.index(on_taste.name) < names.index(off_taste.name)


async def test_stylist_returns_real_alternatives_at_different_prices(client, monkeypatch):
    """The actual feature: alongside the chosen product, real alternatives
    from the same search — at different price points — come back too, not
    just the one winner."""
    options = [
        _raw("Budget Jacket", price_cents=3000),
        _raw("Mid Jacket", price_cents=6000),
        _raw("Premium Jacket", price_cents=12000),
        _raw("Luxury Jacket", price_cents=20000),
    ]
    _patch_live_search(monkeypatch, _live_results(*options))

    class PicksFirstProvider:
        name = "picks-first"
        model = "picks-first-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            return StylistRecommendation(summary="the budget one", chosen_indexes=[0])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksFirstProvider())
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "a leather jacket", "max_items": 1})
    assert resp.status_code == 200
    body = resp.json()
    chosen = body["products"][0]
    assert chosen["name"] == "Budget Jacket"

    alts = body["alternatives"][chosen["id"]]
    alt_names = {a["name"] for a in alts}
    assert "Budget Jacket" not in alt_names  # never includes the chosen item itself
    assert alt_names == {"Mid Jacket", "Premium Jacket", "Luxury Jacket"}
    prices = [a["price_cents"] for a in alts]
    assert prices == sorted(prices)  # low to high
    # carries the search term back, so a client can persist one via
    # POST /products/select-live without needing to know what was searched
    assert all(a["search_term"] == "leather jacket" for a in alts)


async def test_an_alternative_from_a_non_ebay_retailer_is_labelled_correctly(client, monkeypatch):
    """Real bug: alternatives used to hardcode retailer_slug="ebay" for
    every one, from back when eBay really was the only retailer with a
    live search. An AliExpress alternative came back labelled eBay —
    wrong retailer_name shown, and POST /products/select-live for it
    would have asked eBay for an id AliExpress actually owns."""
    options = [
        _raw("Budget Jacket", price_cents=3000),
        _raw("AliExpress Jacket", price_cents=6000, retailer_product_id="ali-1"),
    ]
    results = _live_results(options[0]) + _live_results(options[1], provider=_FakeAliExpressProvider())
    _patch_live_search(monkeypatch, results)

    class PicksFirstProvider:
        name = "picks-first"
        model = "picks-first-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            return StylistRecommendation(summary="the budget one", chosen_indexes=[0])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksFirstProvider())
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "a leather jacket", "max_items": 1})
    assert resp.status_code == 200
    body = resp.json()
    chosen = body["products"][0]

    alts = body["alternatives"][chosen["id"]]
    ali_alt = next(a for a in alts if a["name"] == "AliExpress Jacket")
    assert ali_alt["retailer_slug"] == "aliexpress"
    assert ali_alt["retailer_name"] == "AliExpress"


async def test_stylist_alternatives_span_the_price_range_not_just_cheapest(client, monkeypatch):
    """With more real options than the alternatives cap, pick low/mid/high
    across the range — not just the N cheapest — so "top, low etc" prices
    are genuinely represented."""
    options = [_raw(f"Jacket {i}", price_cents=(i + 1) * 1000) for i in range(30)]  # 1000..30000
    _patch_live_search(monkeypatch, _live_results(*options))

    class PicksLastProvider:
        name = "picks-last"
        model = "picks-last-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            return StylistRecommendation(summary="picked", chosen_indexes=[29])  # the priciest, 30000

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksLastProvider())
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "a denim jacket", "max_items": 1})
    body = resp.json()
    chosen = body["products"][0]
    alts = body["alternatives"][chosen["id"]]
    assert len(alts) == 24
    prices = sorted(a["price_cents"] for a in alts)
    # from the 29 remaining options (1000..29000), spans low and high — not
    # just the 24 cheapest (which would top out at 24000)
    assert prices[0] == 1000
    assert prices[-1] == 29000


def test_extract_search_terms_splits_a_multi_item_outfit_prompt():
    """Real bug, found live: eBay indexes individual listings, not
    outfits — searching "jacket AND jeans AND sneakers" as one sentence
    returned zero results, because no real listing's title contains every
    item word at once. Each item mentioned must become its own query."""
    from app.services.stylist_service import _extract_search_terms

    terms = _extract_search_terms(
        "A stylish men's leather jacket paired with denim jeans and sneakers, casual streetwear outfit"
    )
    assert "men leather jacket" in terms
    assert "men denim jeans" in terms
    assert "men sneakers" in terms
    # only the item words, not filler like "stylish"/"casual"/"streetwear"/"outfit"
    assert not any("stylish" in t or "outfit" in t for t in terms)


def test_extract_search_terms_returns_empty_for_a_prompt_with_no_recognized_item():
    from app.services.stylist_service import _extract_search_terms

    assert _extract_search_terms("something for a black-tie gala") == []


def test_extract_search_terms_understands_desi_wear_and_jewellery():
    from app.services.stylist_service import _extract_search_terms

    terms = _extract_search_terms(
        "Red embroidered shalwar kameez for women with gold bangles, jhumka earrings and khussa shoes"
    )
    assert terms == [
        "women red embroidered shalwar kameez",
        "women gold bangles",
        "women jhumka earrings",
        "women khussa shoes",
    ]


def test_extract_search_terms_keeps_comma_separated_items_apart():
    from app.services.stylist_service import _extract_search_terms

    assert _extract_search_terms("jacket, jeans, sneakers") == ["jacket", "jeans", "sneakers"]


def test_extract_search_terms_drops_matching_as_a_fake_descriptor():
    """Real bug, found live: "a kurti, matching trousers" built the term
    "women matching trousers" — its top live result was a Western
    blazer-and-trousers SET literally titled "...BLAZER JACKET AND
    MATCHING TROUSERS...", picked for the trousers slot, which rendered
    as a second incompatible top-layer garment over the kurti."""
    from app.services.stylist_service import _extract_search_terms

    terms = _extract_search_terms("a kurti, matching trousers and shoes", gender="women")
    assert terms == ["women kurti", "women trousers", "women shoes"]


def test_extract_search_terms_drops_a_generic_jewelry_lead_in():
    """Real bug, found live: "two jewelry pieces (earrings and bangles)"
    produced three searches instead of two — "jewelry" is itself a
    recognized item word, not just a lead-in to the specific ones named
    right after it — and the outfit came back with an extra, unwanted
    second pair of earrings from the generic term's own top result."""
    from app.services.stylist_service import _extract_search_terms

    terms = _extract_search_terms(
        "a kurti and two jewelry pieces (earrings and bangles)", gender="women"
    )
    assert terms == ["women kurti", "women earrings", "women bangles"]


def test_extract_search_terms_keeps_a_bare_jewelry_ask():
    """The umbrella word is only dropped when a more specific item from
    the same prompt already covers it — a prompt that names nothing more
    specific must still search for it."""
    from app.services.stylist_service import _extract_search_terms

    assert _extract_search_terms("a dress and some jewelry", gender="women") == [
        "women dress",
        "women jewelry",
    ]


def test_extract_search_terms_drops_conversational_filler_before_an_item():
    """Real bug, found live: "apply ear rings , ... and also watch" built
    the search terms "apply ear rings" and "also watch" — neither
    "apply" nor "also" is a stopword, a category word or a gender word,
    so the "up to two describing words before it" rule swept them in as
    if they were real descriptors like "white" or "leather". Live:
    "apply ear rings" found 2 listings; "ear rings" alone found 10 — the
    extra word wasn't neutral, it actively hurt the search."""
    from app.services.stylist_service import _extract_search_terms

    terms = _extract_search_terms(
        "apply ear rings, white color ring, white shalwar kameez with karahi heels shoes and also watch"
    )
    assert terms == ["ear rings", "white color ring", "white shalwar kameez", "karahi heels shoes", "watch"]


def test_narrow_term_drops_the_leading_descriptor_keeping_gender_and_category():
    from app.services.stylist_service import _narrow_term

    assert _narrow_term("karahi heels shoes") == "heels shoes"
    assert _narrow_term("women karahi heels shoes") == "women heels shoes"
    assert _narrow_term("white color ring") == "ring"
    assert _narrow_term("watch") is None  # nothing left to drop
    assert _narrow_term("women watch") is None


async def test_a_term_that_finds_nothing_is_retried_narrowed_rather_than_dropped(monkeypatch):
    """Real bug, found live: "karahi heels shoes" (karahi is a specific
    embroidery technique) returned zero results from live_search, so the
    shopper's outfit came back missing shoes entirely with no
    explanation — four items shown for a five-item ask. "heels shoes"
    alone found real ones live. The item must not just vanish because
    the shopper's own word for it isn't a retailer's."""
    from app.schemas.stylist import StylistAskRequest
    from app.services.stylist_service import _fetch_candidates

    calls: list[str] = []

    async def fake_live_search(query: str, *, limit: int = 24):
        calls.append(query)
        if query == "women karahi heels shoes":
            return []  # the shopper's exact phrasing: nothing
        if query == "women heels shoes":
            return _live_results("Nude Ankle Strap Heels")
        return _live_results(f"generic result for {query}")

    monkeypatch.setattr("app.services.stylist_service.live_search", fake_live_search)

    req = StylistAskRequest(prompt="white shalwar kameez with karahi heels shoes", max_items=2)
    candidates = await _fetch_candidates(req, None, "women")

    assert "women karahi heels shoes" in calls  # tried the shopper's own words first
    assert "women heels shoes" in calls  # then retried, narrowed
    assert any(c.result.raw.name == "Nude Ankle Strap Heels" for c in candidates)


async def test_stylist_searches_each_outfit_item_separately_not_as_one_sentence(client, monkeypatch):
    """The actual end-to-end fix: a multi-item prompt must trigger one
    live_search call per item type, not a single call with the whole
    sentence (which is exactly what returned zero candidates in
    production)."""
    calls: list[str] = []

    async def fake_live_search(query: str, *, limit: int = 24):
        calls.append(query)
        if "jacket" in query:
            return _live_results(_raw("Leather Jacket"))
        if "jeans" in query:
            return _live_results(_raw("Denim Jeans"))
        if "sneakers" in query:
            return _live_results(_raw("Running Sneakers"))
        return []

    class PicksEverythingProvider:
        name = "picks-everything"
        model = "picks-everything-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            return StylistRecommendation(summary="all of it", chosen_indexes=list(range(len(candidates))))

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksEverythingProvider())
    monkeypatch.setattr("app.services.stylist_service.live_search", fake_live_search)
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/stylist/ask",
        json={
            "prompt": "A stylish leather jacket paired with denim jeans and sneakers, streetwear outfit",
            "max_items": 6,
        },
    )
    assert resp.status_code == 200
    # every item type actually got its own search — never the raw sentence
    assert not any("paired with" in c or "streetwear" in c for c in calls)
    assert any("jacket" in c for c in calls)
    assert any("jeans" in c for c in calls)
    assert any("sneakers" in c for c in calls)

    names = {p["name"] for p in resp.json()["products"]}
    assert names & {"Leather Jacket", "Denim Jeans", "Running Sneakers"}


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


async def test_stylist_alternatives_never_offer_another_item_already_in_the_outfit(client, monkeypatch):
    """Two picks from the same search must not list each other as
    alternatives — swapping one in would put the same product in the outfit
    twice."""
    options = [
        _raw("Budget Jacket", price_cents=3000),
        _raw("Mid Jacket", price_cents=6000),
        _raw("Premium Jacket", price_cents=12000),
    ]
    _patch_live_search(monkeypatch, _live_results(*options))

    class PicksTwoProvider:
        name = "picks-two"
        model = "picks-two-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            return StylistRecommendation(summary="two jackets", chosen_indexes=[0, 1])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksTwoProvider())
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "a leather jacket", "max_items": 2})
    assert resp.status_code == 200
    body = resp.json()
    chosen_names = {p["name"] for p in body["products"]}
    assert chosen_names == {"Budget Jacket", "Mid Jacket"}
    for p in body["products"]:
        alt_names = {a["name"] for a in body["alternatives"].get(p["id"], [])}
        assert alt_names.isdisjoint(chosen_names)
        assert alt_names == {"Premium Jacket"}


async def test_multi_item_ask_gets_one_of_each_item_even_if_the_model_overpicks_one(client, monkeypatch):
    """Real bug, seen in a smoke run: "shalwar kameez with bangles and
    khussa" came back as six pairs of khussa. Each item named gets one
    pick; the rest stay available as alternatives."""

    async def fake_live_search(query: str, *, limit: int = 24):
        if "shalwar kameez" in query:
            return _live_results(_raw("Embroidered Shalwar Kameez", price_cents=9000))
        if "bangles" in query:
            return _live_results(_raw("Glass Bangles Set", price_cents=4000))
        return _live_results(*(_raw(f"Khussa {i}", price_cents=1000 + i) for i in range(6)))

    monkeypatch.setattr("app.services.stylist_service.live_search", fake_live_search)

    class OverpicksShoesProvider:
        name = "overpicks"
        model = "overpicks-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            return StylistRecommendation(
                summary="shoes", chosen_indexes=[c.index for c in candidates if c.name.startswith("Khussa")]
            )

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: OverpicksShoesProvider())
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/stylist/ask",
        json={"prompt": "Embroidered shalwar kameez for women with bangles and khussa", "max_items": 6},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    names = [p["name"] for p in body["products"]]
    assert names == ["Embroidered Shalwar Kameez", "Glass Bangles Set", "Khussa 0"]
    khussa_id = body["products"][2]["id"]
    assert len(body["alternatives"][khussa_id]) == 5


async def test_a_mans_alternatives_are_never_womens_products(client, monkeypatch):
    """Reported live: under "Men's Leather Ankle Boots", the other options
    were red pumps and "Reaction Women's Boots". eBay matches the words,
    not the shopper, so the live pool is filtered before the LLM ever
    sees it — which covers the chosen items and their alternatives."""
    options = [
        _raw("Men's Leather Ankle Boots", price_cents=9000),
        _raw("Reaction Women's Brown Leather Boots", price_cents=7000),
        _raw("Pleaser Ladies Platform Boots", price_cents=5000),
        _raw("Leather Chelsea Boots UK 9", price_cents=11000),
    ]
    _patch_live_search(monkeypatch, _live_results(*options))

    class PicksFirstProvider:
        name = "picks-first"
        model = "picks-first-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            # the pool is already filtered — the model can't pick what it can't see
            assert not any("Women" in c.name or "Ladies" in c.name for c in candidates)
            return StylistRecommendation(summary="these", chosen_indexes=[0])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksFirstProvider())
    await register_and_login(client)
    await client.put("/api/v1/users/me/preferences", json={"gender": "men"})

    body = (await client.post("/api/v1/stylist/ask", json={"prompt": "boots", "max_items": 1})).json()
    chosen = body["products"][0]
    assert chosen["name"] == "Men's Leather Ankle Boots"
    assert [a["name"] for a in body["alternatives"][chosen["id"]]] == ["Leather Chelsea Boots UK 9"]


async def test_a_woman_is_shown_the_womens_listings(client, monkeypatch):
    options = [
        _raw("Men's Leather Ankle Boots", price_cents=9000),
        _raw("Reaction Women's Brown Leather Boots", price_cents=7000),
        _raw("Leather Chelsea Boots UK 9", price_cents=11000),
    ]
    _patch_live_search(monkeypatch, _live_results(*options))

    class PicksFirstProvider:
        name = "picks-first"
        model = "picks-first-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            assert not any("Men's" in c.name for c in candidates)
            return StylistRecommendation(summary="these", chosen_indexes=[0])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksFirstProvider())
    await register_and_login(client)
    await client.put("/api/v1/users/me/preferences", json={"gender": "women"})

    body = (await client.post("/api/v1/stylist/ask", json={"prompt": "boots", "max_items": 1})).json()
    names = {p["name"] for p in body["products"]} | {
        a["name"] for alts in body["alternatives"].values() for a in alts
    }
    assert names == {"Reaction Women's Brown Leather Boots", "Leather Chelsea Boots UK 9"}


async def test_the_prompt_overrules_the_saved_gender(client, monkeypatch):
    """A man buying a gift says so in words; that wins over his profile."""
    options = [_raw("Men's Kurta"), _raw("Women's Kurti")]
    _patch_live_search(monkeypatch, _live_results(*options))

    seen: list[str] = []

    class PicksFirstProvider:
        name = "picks-first"
        model = "picks-first-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            seen.extend(c.name for c in candidates)
            return StylistRecommendation(summary="these", chosen_indexes=[0])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksFirstProvider())
    await register_and_login(client)
    await client.put("/api/v1/users/me/preferences", json={"gender": "men"})

    await client.post("/api/v1/stylist/ask", json={"prompt": "a kurti for my wife", "max_items": 1})
    assert seen == ["Women's Kurti"]


async def test_a_bare_ask_follows_the_categories_he_picked_when_no_gender_is_saved(client, monkeypatch):
    """Nothing forces a gender in onboarding, so his picks have to speak
    for him — otherwise "boots" comes back with women's boots again."""
    options = [_raw("Men's Chelsea Boots"), _raw("Women's Ankle Boots")]
    _patch_live_search(monkeypatch, _live_results(*options))

    seen: list[str] = []

    class PicksFirstProvider:
        name = "picks-first"
        model = "picks-first-1"

        async def recommend(self, query: StylistQuery, candidates: list[StylistCandidate]) -> StylistRecommendation:
            seen.extend(c.name for c in candidates)
            return StylistRecommendation(summary="these", chosen_indexes=[0])

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: PicksFirstProvider())
    await register_and_login(client)
    await client.put(
        "/api/v1/users/me/preferences",
        json={"preferred_categories": ["m.eastern.kurta", "m.shoes.boots", "w.shoes.heels"]},
    )

    await client.post("/api/v1/stylist/ask", json={"prompt": "boots", "max_items": 1})
    assert seen == ["Men's Chelsea Boots"]


async def test_a_failing_stylist_model_is_logged_not_just_swallowed(client, monkeypatch, capsys):
    """Live: the OpenAI account ran out of credit, shoppers saw "the
    stylist is temporarily unavailable", and the logs said nothing —
    the error went only into the ai_usage row."""
    _patch_live_search(monkeypatch, _live_results("Navy Dress"))

    class BrokeProvider:
        name = "openai"
        model = "gpt-5.6-sol"

        async def recommend(self, query, candidates):
            raise RuntimeError("OpenAI error 429: insufficient_quota / credit_balance_exhausted")

    monkeypatch.setattr("app.services.stylist_service.get_stylist_provider", lambda: BrokeProvider())
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "a navy dress", "max_items": 1})
    assert resp.status_code == 200  # the shopper gets a polite answer, not a crash
    assert "temporarily unavailable" in resp.json()["summary"]

    logged = capsys.readouterr()
    everything = logged.out + logged.err
    assert "stylist_llm_failed" in everything
    assert "insufficient_quota" in everything  # the actual reason is findable


def _pick(name: str, image: str, product_id: str = ""):
    from types import SimpleNamespace

    from app.services.stylist_service import _Candidate

    raw = SimpleNamespace(name=name, images=[image], retailer_product_id=product_id or name)
    return _Candidate(result=SimpleNamespace(raw=raw), term="t")


def test_a_set_and_its_own_dupatta_are_not_both_picked():
    """Live: a 3 piece suit and its dupatta were picked as two separate items."""
    from app.services.stylist_service import _drop_redundant_candidates

    suit = _pick("Pakistani Women 3 Piece Suit Blue White Floral Kameez Shalwar with Dupatta", "https://img/a.jpg")
    dupatta = _pick("Women Chiffon Dupatta Blue Floral Embroidered", "https://img/b.jpg")
    kept = _drop_redundant_candidates([suit, dupatta])
    assert [c.result.raw.name for c in kept] == [suit.result.raw.name]


def test_a_standalone_dupatta_is_kept_when_no_set_is_picked():
    from app.services.stylist_service import _drop_redundant_candidates

    kurti = _pick("White Chikankari Kurti", "https://img/c.jpg")
    dupatta = _pick("Women Chiffon Dupatta White", "https://img/d.jpg")
    assert len(_drop_redundant_candidates([kurti, dupatta])) == 2


def test_a_colour_the_shopper_did_not_ask_for_is_a_conflict():
    from app.services.stylist_service import _colour_conflicts

    assert _colour_conflicts("a white shalwar kameez", "Blue Floral Suit")
    assert not _colour_conflicts("a white shalwar kameez", "White Chikankari Kurti")
    assert not _colour_conflicts("a white shalwar kameez", "Chikankari Kurti")  # names no colour: kept
    assert not _colour_conflicts("a shalwar kameez", "Blue Floral Suit")  # no colour asked: nothing to conflict


def test_a_jewellery_set_overlapping_a_separate_piece_is_dropped():
    """Live: a necklace+earrings+tikka set was picked with separate earrings, and
    the two earring designs were blended in the image."""
    from app.services.stylist_service import _drop_redundant_candidates

    earrings = _pick("Bollywood South India Gold Plated Jhumka Earrings", "https://img/e.jpg")
    the_set = _pick("Choker Gold Plated Bridal Necklace Set Earrings Maang Tikka", "https://img/s.jpg")
    ring = _pick("Natural Emerald Ring 18K Gold Plated", "https://img/r.jpg")
    kept = [c.result.raw.name for c in _drop_redundant_candidates([earrings, the_set, ring])]
    assert kept == [earrings.result.raw.name, ring.result.raw.name]


def test_a_jewellery_set_that_overlaps_nothing_is_kept():
    from app.services.stylist_service import _drop_redundant_candidates

    the_set = _pick("Gold Necklace Set with Earrings", "https://img/s.jpg")
    ring = _pick("Emerald Ring", "https://img/r.jpg")
    assert len(_drop_redundant_candidates([the_set, ring])) == 2


def test_extract_search_terms_leaves_out_items_the_shopper_says_no_to():
    # Live: "No second dress and no separate dupatta" fetched a bandhani dupatta.
    from app.services.stylist_service import _extract_search_terms

    terms = _extract_search_terms(
        "ONE pink bridal lehenga dress only, gold nose ring, elegant gold wristwatch, pink khussa. "
        "No second dress and no separate dupatta."
    )
    assert terms == ["pink bridal lehenga dress", "gold nose ring", "elegant gold wristwatch", "pink khussa"]
    assert _extract_search_terms("red dress without a dupatta, black heels") == ["red dress", "black heels"]
    assert _extract_search_terms("red dress with matching dupatta") == ["red dress", "dupatta"]


def test_a_dupatta_search_never_brings_back_a_whole_outfit():
    # Live: "with matching dupatta" picked a lehenga set, and the look had two dresses.
    from app.services.stylist_service import _whole_outfit_for_a_piece

    assert _whole_outfit_for_a_piece("women dupatta", "DESIGNER NET LEHENGA CHOLI WITH DUPATTA FOR INDIAN")
    assert not _whole_outfit_for_a_piece("women dupatta", "Pink Net Embroidered Dupatta With Gold Border")
    assert not _whole_outfit_for_a_piece("pink bridal lehenga dress", "Pink Lehenga Choli With Dupatta")


def test_each_listing_must_be_the_item_asked_for_and_one_real_product():
    # Live: a bridal look came back like a costume. "maang tikka" found a
    # belly-dance head chain, "nose ring" an 8-pack, "nose ring" a finger ring.
    from app.services.stylist_service import _is_the_item, _unsuitable

    assert not _is_the_item("women gold maang tikka", "Silver Gold Coin Tassel Belly Dance Head Chain")
    assert _is_the_item("women gold maang tikka", "Kundan Gold Maang Tikka With Pearls")
    assert not _is_the_item("women small gold nose ring", "2Ct Round Diamond Bridal Engagement Ring")
    assert _is_the_item("women small gold nose ring", "Small Thin Gold Nose Ring Hoop")
    assert _is_the_item("women elegant gold wristwatch", "Vintage Gold Bracelet Watch Women")
    assert _is_the_item("women embellished pink khussa", "Handmade Jutti Flats Women Pink")

    assert _unsuitable("women small gold nose ring", "Tucnoeu 8 Pcs Dangle Nose Rings Hoop", "a nose ring")
    assert _unsuitable("women gold maang tikka", "Belly Dance Coin Head Chain", "bridal look")
    assert not _unsuitable("women belly dance head chain", "Belly Dance Coin Head Chain", "a belly dance costume")
    assert not _unsuitable("women pink lehenga", "3 Piece Lehenga Suit", "pink lehenga")  # a set is one outfit
    assert not _unsuitable("women pink lehenga", "Customized Baby Pink Lehenga Choli", "pink lehenga")


def test_items_beyond_the_look_limit_are_named_not_dropped_silently():
    from app.services.stylist_service import _extract_search_terms, _left_out_note

    prompt = "pink lehenga, gold maang tikka, jhumka earrings, gold necklace, nose ring, gold ring, gold watch"
    terms = _extract_search_terms(prompt, "women")
    note = _left_out_note(terms[5:], 5, "women")
    assert "up to 5 products" in note and "gold ring, gold watch" in note and "women" not in note
    assert _left_out_note([], 5, "women") == ""


def test_the_colour_asked_for_ranks_first_and_a_lookalike_piece_last():
    # Live: "gold maang tikka" picked a silver "Hairband Maang Tikka Headband"; it came out as a crown.
    from app.services.stylist_service import _fit

    term = "women gold maang tikka"
    names = [
        "Assyrian Style Flag Leaves Tassel Hairband Maang Tikka Headband",
        "Kundan Pearl Maang Tikka",
        "Maang Tikka Indian Gold Plated Red Kundan",
    ]
    ranked = sorted(names, key=lambda n: -_fit(term, n))
    assert ranked == ["Maang Tikka Indian Gold Plated Red Kundan", "Kundan Pearl Maang Tikka", ranked[-1]]
    assert "Headband" in ranked[-1]
    assert _fit("women gold tikka headband", names[0]) == 0  # asked for a headband: no penalty


def test_a_bottom_on_its_own_never_brings_back_a_whole_suit():
    # Live: "cream shalwar" under a sherwani picked a whole black "Shalwar Kameez" suit.
    from app.services.stylist_service import _whole_outfit_for_a_piece

    assert _whole_outfit_for_a_piece("men cream shalwar", "PAKISTANI MEN SHALWAR KAMEEZ SUIT")
    assert not _whole_outfit_for_a_piece("men cream shalwar", "Men Cream Cotton Shalwar Trouser")
    assert not _whole_outfit_for_a_piece("men black trousers", "Men's Slim Fit Suit Trousers")
    assert not _whole_outfit_for_a_piece("men cream shalwar kameez", "Shalwar Kameez Suit")  # asked for the suit


def test_a_single_aliexpress_item_titled_1pc_is_not_a_multipack():
    # AliExpress titles single items "1PC ..." / "1 Pair ..."; they were being dropped as packs.
    from app.services.stylist_service import _unsuitable

    assert not _unsuitable("women small gold nose ring", "1PC Gold Color Nose Ring Hoop For Women", "nose ring")
    assert not _unsuitable("women gold jhumka earrings", "1 Pair Indian Gold Jhumka Earrings", "jhumka")
    assert _unsuitable("women gold maang tikka", "2Pcs Indian Maang Tikka Gold Color", "tikka")
    assert _unsuitable("women small gold nose ring", "Tucnoeu 8 Pcs Dangle Nose Rings Hoop", "nose ring")
    assert _unsuitable("women gold ring", "Set of 6 Gold Stacking Rings", "ring")


def test_one_piece_asked_for_ranks_single_pieces_above_sets():
    # Live: "gold maang tikka" picked a choker + earrings + tikka bridal set.
    from app.services.stylist_service import _fit

    term = "women gold maang tikka"
    one_set = "Indian Bollywood Kundan Choker Necklace Earrings Maang Tikka Bridal Jewelry Set"
    single = "Kundan Pearl Maang Tikka"
    assert _fit(term, single) > _fit(term, one_set)
    assert _fit("women gold jewellery set", one_set) >= 0  # asked for a set: no penalty
