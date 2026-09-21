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


def test_a_man_is_never_suggested_womens_clothing():
    """Reported live: "Kurti for men with wallet and heels", "Mint lehenga
    choli for men". Saved categories can span the whole tree (onboarding
    lets anyone browse it), so the shopper's own audience decides."""
    womens = ["w.eastern.kurti", "w.eastern.pishwas", "w.eastern.bridal", "w.shoes.heels",
              "w.jewellery.earrings", "w.bags.clutch"]
    prompts = suggest_prompts(_pref(gender=Gender.MEN, preferred_categories=womens))

    assert prompts, "a man with only women's picks still gets suggestions"
    womens_only = ("kurti", "pishwas", "lehenga", "heels", "clutch", "saree", "anarkali", "gharara")
    for prompt in prompts:
        assert all(word not in prompt.lower() for word in womens_only), prompt
        assert "for men" in prompt

    # his own picks win when he has any
    mixed = womens + ["m.eastern.shalwar", "m.shoes.peshawari"]
    assert any("shalwar kameez" in p.lower() for p in suggest_prompts(_pref(gender=Gender.MEN, preferred_categories=mixed)))
    # and a woman still gets hers
    hers = suggest_prompts(_pref(gender=Gender.WOMEN, preferred_categories=womens))
    assert any("kurti" in p.lower() for p in hers) and all("for women" in p for p in hers)


def test_with_no_gender_saved_the_prompts_follow_the_picks_he_actually_made():
    """Reported live: "Kurti for men with wallet and heels". Onboarding
    doesn't force a gender, and the tree lets anyone tick anything, so one
    stray women's pick chose the clothes while a men's pick chose the
    words. Whichever audience he picked most of now decides both."""
    prompts = suggest_prompts(
        _pref(
            gender=None,
            preferred_categories=[
                "m.eastern.shalwar", "m.eastern.kurta", "m.shoes.formal", "m.accessories.rings",
                "m.accessories.wallets", "m.watches.analog",
                "w.eastern.kurti", "w.eastern.lehenga", "w.shoes.heels", "w.jewellery.earrings",
            ],
            preferred_colors=["mint"],
        )
    )
    assert prompts and all("for men" in p for p in prompts)
    womens = ("kurti", "lehenga", "heels", "earrings", "clutch", "necklace", "pishwas", "for women")
    assert not [p for p in prompts if any(w in p.lower() for w in womens)]


def test_mostly_womens_picks_with_no_gender_saved_read_as_womens_prompts():
    prompts = suggest_prompts(
        _pref(
            gender=None,
            preferred_categories=["w.eastern.kurti", "w.shoes.heels", "w.jewellery.earrings", "m.watches.analog"],
        )
    )
    assert prompts and all("for women" in p for p in prompts)
    assert not any("watch" in p for p in prompts)


def test_the_saved_gender_still_wins_over_the_picks():
    prompts = suggest_prompts(
        _pref(
            gender=Gender.WOMEN,
            preferred_categories=[
                "m.eastern.kurta", "m.shoes.formal", "m.watches.analog", "w.eastern.kurti", "w.shoes.heels",
            ],
        )
    )
    assert prompts and all("for women" in p for p in prompts)
    assert not any("kurta" in p or "watch" in p for p in prompts)


def test_kids_prompts_say_girls_or_boys_rather_than_for_men():
    prompts = suggest_prompts(_pref(gender=None, preferred_categories=["k.girls.frocks", "k.shoes.sandals"]))
    assert prompts and not any(" for men" in p or " for women" in p for p in prompts)
