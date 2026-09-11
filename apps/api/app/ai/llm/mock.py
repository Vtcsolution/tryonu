"""Mock stylist — deterministic heuristic (budget fit + style-tag overlap)
so the stylist endpoint is fully testable with zero LLM credentials."""

from __future__ import annotations

from app.ai.llm.base import StylistCandidate, StylistLLMProvider, StylistQuery, StylistRecommendation


class MockStylistProvider(StylistLLMProvider):
    name = "mock"
    model = "mock-stylist-v1"

    async def recommend(
        self, query: StylistQuery, candidates: list[StylistCandidate]
    ) -> StylistRecommendation:
        wanted_style = (query.style or query.occasion or "").lower()

        def score(c: StylistCandidate) -> tuple[int, int]:
            tag_hit = 1 if any(wanted_style and wanted_style in t.lower() for t in c.style_tags) else 0
            in_budget = 1
            if query.budget_min_cents and c.price_cents < query.budget_min_cents:
                in_budget = 0
            if query.budget_max_cents and c.price_cents > query.budget_max_cents:
                in_budget = 0
            return (tag_hit + in_budget, -c.price_cents)

        ranked = sorted(candidates, key=score, reverse=True)
        chosen = [c.index for c in ranked[: query.max_items]]

        names = ", ".join(c.name for c in ranked[: min(3, len(ranked))])
        occasion = f" for {query.occasion}" if query.occasion else ""
        summary = (
            f"Based on \"{query.prompt.strip()}\"{occasion}, I put together a set built around "
            f"{names or 'a few close matches'} — all within your stated budget and style."
        )

        return StylistRecommendation(summary=summary, chosen_indexes=chosen)
