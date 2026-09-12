"""Builds a lightweight "taste profile" from a user's explicit preferences
and implicit signals (saved looks, product views), and scores how well a
candidate product matches it.

Deliberately simple and explainable — weighted counters, not a model.
Explicit preferences count most; saving a look (a strong "I want this on
me" signal) counts more than just viewing a product page. A user with no
signal yet gets a neutral score everywhere, so personalization only ever
nudges ranking, never gates results.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.history import ProductView
from app.models.outfit import SavedLook
from app.models.preference import UserPreference
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult

_RECENT_VIEWS_LIMIT = 50
_WEIGHT_EXPLICIT = 3.0
_WEIGHT_SAVED_LOOK = 2.0
_WEIGHT_VIEW = 0.5

_NEUTRAL_SCORE = 0.5


@dataclass
class TasteProfile:
    colors: Counter[str] = field(default_factory=Counter)
    styles: Counter[str] = field(default_factory=Counter)
    brands: Counter[str] = field(default_factory=Counter)

    @property
    def has_signal(self) -> bool:
        return bool(self.colors or self.styles or self.brands)


def _add(counter: Counter[str], value: str | None, weight: float) -> None:
    if value:
        counter[value.strip().lower()] += weight


async def build_taste_profile(db: AsyncSession, user_id: str) -> TasteProfile:
    profile = TasteProfile()

    pref_result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    pref = pref_result.scalar_one_or_none()
    if pref:
        for c in pref.preferred_colors or []:
            _add(profile.colors, c, _WEIGHT_EXPLICIT)
        for s in pref.preferred_styles or []:
            _add(profile.styles, s, _WEIGHT_EXPLICIT)
        for b in pref.preferred_brands or []:
            _add(profile.brands, b, _WEIGHT_EXPLICIT)

    saved_result = await db.execute(
        select(SavedLook)
        .where(SavedLook.user_id == user_id)
        .options(
            selectinload(SavedLook.tryon_result).selectinload(TryOnResult.job).selectinload(TryOnJob.product)
        )
    )
    for look in saved_result.scalars().all():
        product = look.tryon_result.job.product if look.tryon_result and look.tryon_result.job else None
        if product is None:
            continue
        _add(profile.colors, product.color, _WEIGHT_SAVED_LOOK)
        _add(profile.brands, product.brand, _WEIGHT_SAVED_LOOK)
        for tag in product.style_tags or []:
            _add(profile.styles, tag, _WEIGHT_SAVED_LOOK)

    views_result = await db.execute(
        select(ProductView)
        .where(ProductView.user_id == user_id)
        .options(selectinload(ProductView.product))
        .order_by(ProductView.created_at.desc())
        .limit(_RECENT_VIEWS_LIMIT)
    )
    for view in views_result.scalars().all():
        if view.product is None:
            continue
        _add(profile.colors, view.product.color, _WEIGHT_VIEW)
        _add(profile.brands, view.product.brand, _WEIGHT_VIEW)
        for tag in view.product.style_tags or []:
            _add(profile.styles, tag, _WEIGHT_VIEW)

    return profile


def _counter_score(counter: Counter[str], key: str | None) -> float:
    if not key or not counter:
        return 0.0
    top = max(counter.values())
    return counter.get(key.strip().lower(), 0) / top


def affinity_score(product: Product, profile: TasteProfile) -> float:
    """0..1 — how well this product matches the profile. A brand-new user
    (no signal at all) scores exactly _NEUTRAL_SCORE for everything, so
    personalization never demotes results before there's any data."""
    if not profile.has_signal:
        return _NEUTRAL_SCORE

    color_score = _counter_score(profile.colors, product.color)
    brand_score = _counter_score(profile.brands, product.brand)
    tag_scores = [_counter_score(profile.styles, t) for t in (product.style_tags or [])]
    style_score = max(tag_scores) if tag_scores else 0.0

    return 0.35 * color_score + 0.4 * style_score + 0.25 * brand_score
