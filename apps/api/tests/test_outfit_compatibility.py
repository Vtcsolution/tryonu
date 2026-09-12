"""The rule-based outfit compatibility scorer: real signal (neutrals pair
with anything, style-tag overlap matters, gender mismatches are penalized),
not a stub that always returns the same number."""

from __future__ import annotations

from app.models.enums import Gender, OutfitSlot
from app.services.outfit_compatibility import score_outfit


class _P:
    """A bare stand-in for Product — the scorer only reads color/style_tags/gender."""

    def __init__(self, color=None, style_tags=None, gender=Gender.UNISEX):
        self.color = color
        self.style_tags = style_tags
        self.gender = gender


def test_single_item_outfit_scores_perfectly():
    score = score_outfit([_P(color="red")])
    assert score.overall == 100


def test_neutral_colors_score_higher_than_clashing_ones():
    neutral_pair = score_outfit([_P(color="black"), _P(color="orange")])
    clashing_pair = score_outfit([_P(color="red"), _P(color="green")])
    assert neutral_pair.color > clashing_pair.color


def test_matching_style_tags_score_higher_than_disjoint_ones():
    matched = score_outfit(
        [_P(style_tags=["casual", "streetwear"]), _P(style_tags=["casual", "layering"])]
    )
    mismatched = score_outfit([_P(style_tags=["formal", "evening"]), _P(style_tags=["athleisure", "sporty"])])
    assert matched.style > mismatched.style
    assert any("style" in n.lower() for n in mismatched.notes)


def test_gender_mismatch_is_flagged_in_notes():
    score = score_outfit([_P(gender=Gender.MEN), _P(gender=Gender.WOMEN)])
    assert any("gender" in n.lower() for n in score.notes)


def test_unisex_alongside_a_gendered_item_is_not_penalized_as_heavily():
    mixed_with_unisex = score_outfit([_P(gender=Gender.WOMEN), _P(gender=Gender.UNISEX)])
    mixed_without_unisex = score_outfit([_P(gender=Gender.MEN), _P(gender=Gender.WOMEN)])
    assert mixed_with_unisex.overall > mixed_without_unisex.overall


def test_duplicate_slots_score_lower_than_distinct_slots():
    same_slot = score_outfit(
        [_P(color="black", style_tags=["casual"]), _P(color="black", style_tags=["casual"])],
        slots=[OutfitSlot.TOP, OutfitSlot.TOP],
    )
    distinct_slots = score_outfit(
        [_P(color="black", style_tags=["casual"]), _P(color="black", style_tags=["casual"])],
        slots=[OutfitSlot.TOP, OutfitSlot.BOTTOM],
    )
    assert distinct_slots.overall >= same_slot.overall


def test_score_is_bounded_0_to_100():
    score = score_outfit([_P(color="red"), _P(color="green"), _P(gender=Gender.MEN), _P(gender=Gender.WOMEN)])
    assert 0 <= score.overall <= 100
    assert 0 <= score.color <= 100
    assert 0 <= score.style <= 100
