"""Rule-based outfit coherence scoring — color harmony, style-tag overlap,
gender consistency, and slot diversity.

Deliberately rules-based, not ML: every score is explainable from the
product data we actually have (color/style_tags/gender), which matters
for a "real products only" platform — a score the product team can read
and adjust beats a black box. Used both when the stylist auto-assembles
an outfit and when a user manually builds one (see api/v1/endpoints/
outfits.py), so "does this look put together" means the same thing in
both places.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import OutfitSlot
from app.models.product import Product

# Neutrals pair with almost anything; named pairs cover common
# complementary/analogous combinations. An unlisted pair isn't wrong —
# fashion color "rules" are guidelines — so it gets a mild score, not zero.
_NEUTRALS = {"black", "white", "cream", "beige", "grey", "gray", "navy", "tan", "brown", "denim", "indigo", "ivory"}
_COMPATIBLE_COLOR_PAIRS = {
    frozenset({"red", "black"}),
    frozenset({"red", "white"}),
    frozenset({"red", "navy"}),
    frozenset({"blue", "white"}),
    frozenset({"blue", "cream"}),
    frozenset({"blue", "tan"}),
    frozenset({"pink", "grey"}),
    frozenset({"pink", "cream"}),
    frozenset({"green", "beige"}),
    frozenset({"green", "brown"}),
    frozenset({"yellow", "navy"}),
    frozenset({"yellow", "grey"}),
    frozenset({"orange", "navy"}),
    frozenset({"purple", "grey"}),
}


@dataclass(frozen=True, slots=True)
class OutfitScore:
    overall: int  # 0-100, weighted blend of the components below
    color: int
    style: int
    notes: list[str]


def score_outfit(products: list[Product], slots: list[OutfitSlot] | None = None) -> OutfitScore:
    if len(products) < 2:
        return OutfitScore(overall=100, color=100, style=100, notes=[])

    color = _color_score(products)
    style = _style_score(products)
    gender = _gender_score(products)
    diversity = _slot_diversity_score(slots) if slots else 1.0

    overall = 0.35 * color + 0.35 * style + 0.2 * gender + 0.1 * diversity

    notes: list[str] = []
    if color < 0.6:
        notes.append("A couple of these colors don't have an obvious pairing — worth a second look.")
    if style < 0.55:
        notes.append("These pieces lean toward different styles.")
    if gender < 0.7:
        notes.append("This mixes items from different gender categories.")

    return OutfitScore(overall=round(overall * 100), color=round(color * 100), style=round(style * 100), notes=notes)


def _norm_color(c: str | None) -> str | None:
    return c.strip().lower() if c else None


def _color_pair_score(a: str | None, b: str | None) -> float:
    a, b = _norm_color(a), _norm_color(b)
    if not a or not b:
        return 0.6  # missing color data — neither rewarded nor penalized
    if a == b:
        return 1.0
    if a in _NEUTRALS or b in _NEUTRALS:
        return 0.9
    if frozenset({a, b}) in _COMPATIBLE_COLOR_PAIRS:
        return 0.85
    return 0.45


def _color_score(products: list[Product]) -> float:
    colors = [p.color for p in products if p.color]
    if len(colors) < 2:
        return 0.75
    pairs = [(colors[i], colors[j]) for i in range(len(colors)) for j in range(i + 1, len(colors))]
    return sum(_color_pair_score(a, b) for a, b in pairs) / len(pairs)


def _style_score(products: list[Product]) -> float:
    tag_sets = [set(t.lower() for t in (p.style_tags or [])) for p in products]
    tag_sets = [s for s in tag_sets if s]
    if len(tag_sets) < 2:
        return 0.7
    pairs = [(tag_sets[i], tag_sets[j]) for i in range(len(tag_sets)) for j in range(i + 1, len(tag_sets))]
    overlaps = [len(a & b) / len(a | b) for a, b in pairs if (a | b)]
    if not overlaps:
        return 0.5
    # Jaccard overlap across a whole outfit is naturally strict (few
    # outfits share every tag) — rescale so partial overlap already reads
    # as "reasonably coherent" rather than mediocre.
    return min(1.0, 0.5 + sum(overlaps) / len(overlaps))


def _gender_score(products: list[Product]) -> float:
    genders = {str(p.gender) for p in products if p.gender}
    if len(genders) <= 1:
        return 1.0
    if "unisex" in genders and len(genders) == 2:
        return 0.9
    return 0.5


def _slot_diversity_score(slots: list[OutfitSlot]) -> float:
    return 1.0 if len(set(slots)) == len(slots) else 0.7
