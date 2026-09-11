from __future__ import annotations

from functools import lru_cache

from app.ai.llm.base import StylistLLMProvider
from app.ai.llm.mock import MockStylistProvider
from app.ai.llm.openai_provider import OpenAIStylistProvider
from app.core.config import get_settings


@lru_cache
def get_stylist_provider() -> StylistLLMProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER == "openai":
        return OpenAIStylistProvider(
            api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
            model=settings.OPENAI_MODEL,
        )
    return MockStylistProvider()
