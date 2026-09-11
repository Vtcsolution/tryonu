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
