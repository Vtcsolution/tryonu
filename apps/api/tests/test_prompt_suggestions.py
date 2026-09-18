"""Stylist prompts built from saved preferences — and every one of them
must turn into searches for each item it names."""

from __future__ import annotations

from app.models.enums import Gender
from app.models.preference import UserPreference
from app.services.prompt_suggestions import suggest_prompts
from app.services.stylist_service import _extract_search_terms
from tests.conftest import register_and_login


def _pref(**kw) -> UserPreference:
    return UserPreference(user_id="u", **kw)


def test_no_categories_means_no_suggestions():
    assert suggest_prompts(None) == []
    assert suggest_prompts(_pref(gender=Gender.WOMEN, preferred_categories=[])) == []


def test_builds_outfit_prompts_from_picked_categories_and_colours():
    prompts = suggest_prompts(
        _pref(
            gender=Gender.WOMEN,
            preferred_categories=[
                "w.eastern.shalwar", "w.eastern.shalwar.lawn",
                "w.jewellery.bangles", "w.jewellery.earrings.jhumka", "w.shoes.khussa",
            ],
            preferred_colors=["white", "maroon"],
            preferred_styles=["party wear"],
        )
    )
    assert 1 < len(prompts) <= 6
    assert prompts[0] == "White lawn shalwar kameez for women with khussa and bangles"
    assert all("for women" in p for p in prompts)
    assert any("jhumka earrings" in p for p in prompts)
    assert len(set(prompts)) == len(prompts)


def test_jewellery_only_picks_still_get_prompts():
    prompts = suggest_prompts(
        _pref(gender=Gender.WOMEN, preferred_categories=["w.jewellery.bangles.glass", "w.jewellery.tikka"])
    )
    assert prompts and all("for women" in p for p in prompts)


def test_every_category_phrase_is_something_the_stylist_searches_for():
    """Suggestions are built from these phrases — each must be recognised
    as an item, or tapping the suggestion would silently skip it."""
    from app.core.taxonomy import NODES
    from app.services.prompt_suggestions import _phrase

    for node_id, node in NODES.items():
        if node_id.count(".") < 2:
            continue  # audiences and broad categories are expanded to their items, never suggested as-is
        assert _extract_search_terms(_phrase(node)), (node_id, _phrase(node))


def test_a_broad_category_pick_suggests_its_concrete_items():
    prompts = suggest_prompts(_pref(gender=Gender.WOMEN, preferred_categories=["w.western", "w.shoes"]))
    assert prompts[0] == "Blouse top for women with khussa and heels"
    assert not any("clothing" in p for p in prompts)


async def test_suggestions_endpoint_uses_saved_preferences(client):
    await register_and_login(client)
    assert (await client.get("/api/v1/stylist/suggestions")).json() == {"prompts": []}

    resp = await client.put(
        "/api/v1/users/me/preferences",
        json={"gender": "men", "preferred_categories": ["m.eastern.shalwar", "m.shoes.peshawari"]},
    )
    assert resp.status_code == 200, resp.text
    prompts = (await client.get("/api/v1/stylist/suggestions")).json()["prompts"]
    assert prompts and prompts[0].startswith("Shalwar kameez for men with peshawari chappal")
