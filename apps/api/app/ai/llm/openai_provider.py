"""OpenAI-compatible chat-completions stylist provider.

Uses plain httpx (not the openai SDK) against the standard
/chat/completions shape so any OpenAI-compatible endpoint (Azure OpenAI,
a self-hosted vLLM/Ollama gateway, etc.) works by changing only the base
URL — no code change, matching the "swap providers without rewriting the
app" architecture rule.
"""

from __future__ import annotations

import json

import httpx

from app.ai.llm.base import (
    LLMProviderError,
    StylistCandidate,
    StylistLLMProvider,
    StylistQuery,
    StylistRecommendation,
)

_SYSTEM_PROMPT = (
    "You are TryOnU's fashion stylist. You will be given a numbered list of "
    "REAL, purchasable candidate products and a shopper's request. Choose only "
    "from the numbered list — never invent a product, brand, or item that is "
    "not listed. If earlier conversation turns are provided, use them for "
    "continuity (e.g. a follow-up like \"what shoes go with that\") — but "
    "still choose only from THIS request's numbered candidate list; a "
    "product mentioned earlier may not be in it. Reply with strict JSON: "
    '{"summary": "<2-3 sentence styling rationale>", "chosen_indexes": [<int>, ...]}. '
    "chosen_indexes must reference the given index numbers only."
)


class OpenAIStylistProvider(StylistLLMProvider):
    name = "openai"

    def __init__(self, *, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def recommend(
        self, query: StylistQuery, candidates: list[StylistCandidate]
    ) -> StylistRecommendation:
        user_prompt = _build_user_prompt(query, candidates)

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        # No "temperature" override: newer OpenAI models (this
                        # one included) reject any value other than their
                        # default (1) and error with a 400 if one is sent.
                    },
                )
            except httpx.RequestError as exc:
                raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMProviderError(f"OpenAI error {resp.status_code}: {resp.text}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        try:
            parsed = json.loads(content)
            chosen = [int(i) for i in parsed.get("chosen_indexes", [])]
            summary = str(parsed.get("summary", "")).strip()
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LLMProviderError(f"Could not parse stylist response: {exc}") from exc

        valid_indexes = {c.index for c in candidates}
        chosen = [i for i in chosen if i in valid_indexes][: query.max_items]

        return StylistRecommendation(
            summary=summary or "Here's a selection that fits what you asked for.",
            chosen_indexes=chosen,
            tokens_input=usage.get("prompt_tokens"),
            tokens_output=usage.get("completion_tokens"),
        )


def _build_user_prompt(query: StylistQuery, candidates: list[StylistCandidate]) -> str:
    lines = []
    if query.wardrobe_context:
        lines.append(query.wardrobe_context)
        lines.append("")
    if query.recent_context:
        lines.append("Conversation so far:")
        lines.append(query.recent_context)
        lines.append("")
    lines.append(f"Shopper request: {query.prompt}")
    if query.occasion:
        lines.append(f"Occasion: {query.occasion}")
    if query.style:
        lines.append(f"Preferred style: {query.style}")
    if query.budget_min_cents or query.budget_max_cents:
        lo = (query.budget_min_cents or 0) / 100
        hi = (query.budget_max_cents or 0) / 100 or "no max"
        lines.append(f"Budget: ${lo:.0f} - {hi}")
    lines.append(f"Pick at most {query.max_items} items.")
    lines.append("\nCandidates:")
    for c in candidates:
        tags = ", ".join(c.style_tags) if c.style_tags else "—"
        lines.append(
            f"[{c.index}] {c.name} — {c.brand or 'Unbranded'} — {c.category or 'uncategorised'} "
            f"— {c.color or 'n/a'} — ${c.price_cents / 100:.2f} — tags: {tags}"
        )
    return "\n".join(lines)
