"""Personalization: a new user gets neutral scores everywhere (never
demoted before there's data), explicit preferences and saved looks shift
search ranking and the stylist's candidate shortlist toward a user's
taste, and none of it ever changes *which* products can appear — only the
order."""

from __future__ import annotations

from app.services.personalization_service import affinity_score, build_taste_profile
from tests.conftest import register_and_login, seed_product


async def _user_id(client) -> str:
    return (await client.get("/api/v1/auth/me")).json()["id"]


async def test_new_user_has_no_signal_and_gets_neutral_affinity(client, db):
    product = await seed_product(db, name="Neutral Target", color="red", style_tags=["formal"])
    await register_and_login(client)
    user_id = await _user_id(client)

    profile = await build_taste_profile(db, user_id)
    assert profile.has_signal is False
    assert affinity_score(product, profile) == 0.5


async def test_explicit_preferences_shift_affinity_toward_matching_products(client, db):
    matching = await seed_product(db, name="Cream Match", color="cream", style_tags=["cozy"])
    non_matching = await seed_product(db, name="Neon Mismatch", color="neon green", style_tags=["clubwear"])
    await register_and_login(client)
    user_id = await _user_id(client)

    resp = await client.put(
        "/api/v1/users/me/preferences",
        json={"preferred_colors": ["cream"], "preferred_styles": ["cozy"]},
    )
    assert resp.status_code == 200

    profile = await build_taste_profile(db, user_id)
    assert profile.has_signal is True
    assert affinity_score(matching, profile) > affinity_score(non_matching, profile)


async def test_search_relevance_with_no_query_ranks_by_affinity_when_signal_exists(client, db):
    matching = await seed_product(db, name="Personalized Pick", color="teal", style_tags=["boho"], price_cents=9999)
    non_matching = await seed_product(db, name="Unrelated Pick", color="grey", style_tags=["formal"], price_cents=100)
    await register_and_login(client)

    await client.put("/api/v1/users/me/preferences", json={"preferred_colors": ["teal"], "preferred_styles": ["boho"]})

    resp = await client.get("/api/v1/products", params={"limit": 50})
    assert resp.status_code == 200
    ids_in_order = [item["id"] for item in resp.json()["items"]]
    assert ids_in_order.index(matching.id) < ids_in_order.index(non_matching.id)


async def test_stylist_candidate_shortlist_is_biased_toward_saved_look_taste(client, db, monkeypatch):
    """A saved look is a stronger signal than a view — after saving a
    cream/cozy item, a fresh cream/cozy candidate should outrank an
    unrelated one in what the LLM even gets to see."""
    from app.ai.providers.base import TryOnOutput
    from app.ai.providers.mock import MockTryOnProvider
    from tests.test_tryon import _poll_until_terminal, _upload_front_photo

    async def fake_generate(self, payload):  # noqa: ARG001
        return TryOnOutput(image_bytes=b"\xff\xd8\xff", provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    saved_taste_product = await seed_product(db, name="Cream Cozy Sweater", color="cream", style_tags=["cozy"])
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    job_resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": saved_taste_product.id}
    )
    job = await _poll_until_terminal(client, job_resp.json()["id"])
    await client.post(f"/api/v1/users/me/saved-looks/{job['result']['id']}")

    # a fresh product matching that taste, and one that doesn't
    on_taste = await seed_product(db, name="Cream Cozy Cardigan", color="cream", style_tags=["cozy"])
    off_taste = await seed_product(db, name="Neon Clubwear Top", color="neon green", style_tags=["clubwear"])

    from app.services.stylist_service import _fetch_candidates
    from app.schemas.stylist import StylistAskRequest
    from app.services.personalization_service import build_taste_profile

    user_id = await _user_id(client)
    profile = await build_taste_profile(db, user_id)
    assert profile.has_signal is True

    req = StylistAskRequest(prompt="something to wear", max_items=5)
    candidates = await _fetch_candidates(db, req, profile)
    ids = [c.id for c in candidates]
    assert ids.index(on_taste.id) < ids.index(off_taste.id)
