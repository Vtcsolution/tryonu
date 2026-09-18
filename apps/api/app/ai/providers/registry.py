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
from app.ai.providers.openai_image import OpenAIImageTryOnProvider
from app.core.config import get_settings
from app.models.enums import OutfitSlot
from app.services.outfit_slots import render_plan


@lru_cache
def get_tryon_provider() -> VirtualTryOnProvider:
    settings = get_settings()

    if settings.VIRTUAL_TRYON_PROVIDER == "fashn":
        return FASHNTryOnProvider(
            api_key=settings.FASHN_API_KEY,  # type: ignore[arg-type]
            base_url=settings.FASHN_API_BASE_URL,
            model=settings.FASHN_MODEL,
        )

    if settings.VIRTUAL_TRYON_PROVIDER == "openai":
        return OpenAIImageTryOnProvider(
            api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
            model=settings.OPENAI_IMAGE_MODEL,
        )

    return MockTryOnProvider()


@lru_cache
def get_full_look_provider() -> VirtualTryOnProvider | None:
    """The whole-outfit provider used for looks the main provider can't fully
    draw (shoes, bags, jewellery with FASHN) — or None to always use the main
    one. The main provider itself when it already draws whole outfits."""
    settings = get_settings()
    main = get_tryon_provider()
    if main.whole_outfit:
        return main
    if main.name == "mock" or not settings.TRYON_OPENAI_FOR_FULL_LOOKS or not settings.OPENAI_API_KEY:
        return None
    return OpenAIImageTryOnProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_IMAGE_MODEL)


def plan_outfit_render(
    items: list[tuple[OutfitSlot, str]],
) -> tuple[VirtualTryOnProvider, list[tuple[int, OutfitSlot]]]:
    """Which provider draws this outfit, and which items it draws: the
    whole-outfit provider when it would draw more of the look, otherwise the
    main provider. The worker and the "on photo" labels both use this."""
    main = get_tryon_provider()
    plan = render_plan(items, main.model, main.whole_outfit)
    full = get_full_look_provider()
    if full is not None and full is not main:
        full_plan = render_plan(items, full.model, True)
        if len(full_plan) > len(plan):
            return full, full_plan
    return main, plan
