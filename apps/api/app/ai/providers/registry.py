"""Provider factory — the one place that knows how many/which try-on
providers exist. Everything else asks for `get_tryon_provider()`.

Adding a provider later (a different vendor, or a self-hosted model) means
adding one class + one branch here — never touching the job worker,
endpoints, or credit logic.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.providers.base import VirtualTryOnProvider
from app.ai.providers.fashn import FASHNTryOnProvider
from app.ai.providers.mock import MockTryOnProvider
from app.core.config import get_settings


@lru_cache
def get_tryon_provider() -> VirtualTryOnProvider:
    settings = get_settings()

    if settings.VIRTUAL_TRYON_PROVIDER == "fashn":
        return FASHNTryOnProvider(
            api_key=settings.FASHN_API_KEY,  # type: ignore[arg-type]
            base_url=settings.FASHN_API_BASE_URL,
            model=settings.FASHN_MODEL,
        )

    return MockTryOnProvider()
