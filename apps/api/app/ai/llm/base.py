"""Fashion-stylist LLM provider abstraction.

The model is only ever shown a shortlist of *real* candidate products
(already filtered from the DB by budget/category/keyword — see
services/stylist_service.py) and must choose by index into that list. It
physically cannot return a product that doesn't exist in our catalog: the
service layer maps the returned indices back to real Product rows and
drops anything out of range.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StylistCandidate:
    index: int
    name: str
    brand: str | None
    category: str | None
    color: str | None
    price_cents: int
    style_tags: list[str]


@dataclass(frozen=True, slots=True)
class StylistQuery:
    prompt: str
    occasion: str | None
    budget_min_cents: int | None
    budget_max_cents: int | None
    style: str | None
    max_items: int
    # Short recap of the user's last few turns (see
    # services/stylist_service.py._recent_context), so a follow-up like
    # "what shoes go with that" has something to refer to. Never expands
    # which products can be chosen — index validation against the current
    # candidate list still applies regardless of this context.
    recent_context: str | None = None
    # Set when the ask is anchored to a wardrobe item ("build around my
    # black trousers") — see stylist_service._wardrobe_context_line. The
    # anchor item itself is never a candidate (it's not a catalog Product),
    # so this only ever shapes which real products get chosen, never adds
    # a fabricated one.
    wardrobe_context: str | None = None


@dataclass(frozen=True, slots=True)
class StylistRecommendation:
    summary: str
    chosen_indexes: list[int]
    tokens_input: int | None = None
    tokens_output: int | None = None


class LLMProviderError(Exception):
    pass


class StylistLLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def recommend(
        self, query: StylistQuery, candidates: list[StylistCandidate]
    ) -> StylistRecommendation: ...
