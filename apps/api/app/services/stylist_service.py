"""AI fashion stylist: turns a free-text ask into a curated set of *real*
catalog products. The LLM never sees or invents products outside a
pre-filtered candidate shortlist — see app/ai/llm/base.py for how that's
enforced.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm.base import StylistCandidate, StylistQuery
from app.ai.llm.registry import get_stylist_provider
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from app.models.product import Product
from app.models.stylist import StylistRequest
from app.models.wardrobe import WardrobeItem
from app.schemas.stylist import StylistAskRequest
from app.services.outfit_compatibility import score_outfit
from app.services.personalization_service import TasteProfile, affinity_score, build_taste_profile

_CANDIDATE_POOL_SIZE = 40
_CANDIDATE_FETCH_POOL_SIZE = 1000  # widened before personalized re-ranking trims to _CANDIDATE_POOL_SIZE
_RECENT_TURNS = 3


async def _recent_context(db: AsyncSession, user_id: str) -> str | None:
    """A short recap of the user's last few stylist turns, oldest first, so
    a follow-up ask ("what shoes go with that") has something to refer to.
    Does not widen which products the LLM may choose — the current
    candidate list + index validation is unchanged either way."""
    result = await db.execute(
        select(StylistRequest)
        .where(StylistRequest.user_id == user_id)
        .order_by(StylistRequest.created_at.desc())
        .limit(_RECENT_TURNS)
    )
    turns = list(reversed(result.scalars().all()))
    if not turns:
        return None
    lines = []
    for t in turns:
        summary = (t.response_summary or "").strip()
        lines.append(f'- User asked: "{t.prompt.strip()}" — You suggested: {summary or "no strong match"}')
    return "\n".join(lines)


async def _load_owned_wardrobe_item(db: AsyncSession, user_id: str, wardrobe_item_id: str) -> WardrobeItem:
    item = await db.get(WardrobeItem, wardrobe_item_id)
    if item is None or item.user_id != user_id or item.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found")
    return item


def _wardrobe_anchor_profile(item: WardrobeItem) -> TasteProfile:
    """A wardrobe item as an explicit "build around this" signal — takes
    priority over the general taste profile when present, since the user
    is asking for something specific, not just a good general match."""
    profile = TasteProfile()
    if item.color:
        profile.colors[item.color.strip().lower()] = 1.0
    if item.brand:
        profile.brands[item.brand.strip().lower()] = 1.0
    for tag in item.style_tags or []:
        profile.styles[tag.strip().lower()] = 1.0
    return profile


def _wardrobe_context_line(item: WardrobeItem) -> str:
    bits = [item.name]
    if item.color:
        bits.append(f"color: {item.color}")
    if item.category:
        bits.append(f"category: {item.category}")
    if item.style_tags:
        bits.append(f"style: {', '.join(item.style_tags)}")
    return (
        f"The shopper wants to build an outfit around an item they already own: {' — '.join(bits)}. "
        "Recommend real catalog products that complement it — do not recommend another item in the same "
        "category as what they already own."
    )


async def _fetch_candidates(db: AsyncSession, req: StylistAskRequest, profile: TasteProfile | None) -> list[Product]:
    stmt = select(Product).where(Product.is_active.is_(True)).options(
        selectinload(Product.images), selectinload(Product.retailer), selectinload(Product.category)
    )
    if req.budget_min_cents is not None:
        stmt = stmt.where(Product.price_cents >= req.budget_min_cents)
    if req.budget_max_cents is not None:
        stmt = stmt.where(Product.price_cents <= req.budget_max_cents)

    if profile and profile.has_signal:
        # Widen the pool, then trim to the LLM's shortlist size by taste —
        # the LLM only ever sees the final _CANDIDATE_POOL_SIZE, so
        # personalization decides which real products it gets to choose
        # from, never what it's allowed to invent.
        #
        # _CANDIDATE_FETCH_POOL_SIZE is generously large specifically so
        # an unordered LIMIT can't arbitrarily exclude relevant products
        # before affinity ranking (below) even gets to see them — an
        # ordered-but-still-capped fetch doesn't actually fix that (a
        # fresh UUID has no special position under any ordering); it just
        # needs to comfortably exceed real catalog size until Phase 1
        # brings enough inventory to warrant a real ANN/relevance query
        # here (same tradeoff search_service.py documents for its own
        # candidate cap).
        wide_stmt = stmt.limit(_CANDIDATE_FETCH_POOL_SIZE)
        pool = list((await db.execute(wide_stmt)).scalars().unique().all())
        pool.sort(key=lambda p: affinity_score(p, profile), reverse=True)
        return pool[:_CANDIDATE_POOL_SIZE]

    stmt = stmt.limit(_CANDIDATE_POOL_SIZE)
    return list((await db.execute(stmt)).scalars().unique().all())


def _slot_for(product: Product) -> OutfitSlot:
    cat = (product.category.slug if product.category else "") or ""
    name = product.name.lower()
    if "dress" in cat or "dress" in name:
        return OutfitSlot.DRESS
    if "coat" in cat or "jacket" in cat or "bomber" in name or "coat" in name:
        return OutfitSlot.OUTERWEAR
    if "shoe" in cat or "boot" in name:
        return OutfitSlot.SHOES
    if "denim" in cat or "pant" in cat or "jean" in name:
        return OutfitSlot.BOTTOM
    if "top" in cat or "shirt" in name or "sweater" in name or "poncho" in name:
        return OutfitSlot.TOP
    if "watch" in name:
        return OutfitSlot.WATCH
    if "bag" in name:
        return OutfitSlot.BAG
    return OutfitSlot.OTHER


async def ask_stylist(db: AsyncSession, *, user_id: str, req: StylistAskRequest) -> StylistRequest:
    wardrobe_item: WardrobeItem | None = None
    if req.wardrobe_item_id:
        wardrobe_item = await _load_owned_wardrobe_item(db, user_id, req.wardrobe_item_id)

    # An explicit "build around this" anchor takes priority over general
    # taste — the user asked for something specific, not just a good match.
    profile = _wardrobe_anchor_profile(wardrobe_item) if wardrobe_item else await build_taste_profile(db, user_id)
    candidates = await _fetch_candidates(db, req, profile)
    llm_candidates = [
        StylistCandidate(
            index=i,
            name=p.name,
            brand=p.brand,
            category=p.category.name if p.category else None,
            color=p.color,
            price_cents=p.price_cents,
            style_tags=p.style_tags or [],
        )
        for i, p in enumerate(candidates)
    ]

    provider = get_stylist_provider()
    query = StylistQuery(
        prompt=req.prompt,
        occasion=req.occasion,
        budget_min_cents=req.budget_min_cents,
        budget_max_cents=req.budget_max_cents,
        style=req.style,
        max_items=req.max_items,
        recent_context=await _recent_context(db, user_id),
        wardrobe_context=_wardrobe_context_line(wardrobe_item) if wardrobe_item else None,
    )

    start = time.perf_counter()
    success = True
    error_message: str | None = None
    try:
        recommendation = await provider.recommend(query, llm_candidates)
    except Exception as exc:  # noqa: BLE001
        success = False
        error_message = str(exc)
        recommendation = None
    latency_ms = int((time.perf_counter() - start) * 1000)

    db.add(
        AIUsage(
            user_id=user_id,
            kind=AIUsageKind.STYLIST_LLM,
            provider=provider.name,
            model=provider.model,
            tokens_input=getattr(recommendation, "tokens_input", None),
            tokens_output=getattr(recommendation, "tokens_output", None),
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
        )
    )

    if not success or recommendation is None:
        stylist_request = StylistRequest(
            user_id=user_id,
            prompt=req.prompt,
            occasion=req.occasion,
            budget_min_cents=req.budget_min_cents,
            budget_max_cents=req.budget_max_cents,
            style=req.style,
            response_summary="The stylist is temporarily unavailable — please try again.",
            recommended_product_ids=[],
        )
        db.add(stylist_request)
        await db.commit()
        await db.refresh(stylist_request)
        return stylist_request

    chosen_products = [candidates[i] for i in recommendation.chosen_indexes if 0 <= i < len(candidates)]

    outfit: Outfit | None = None
    if len(chosen_products) > 1:
        slots = [_slot_for(p) for p in chosen_products]
        coherence = score_outfit(chosen_products, slots)
        outfit = Outfit(
            user_id=user_id,
            occasion=req.occasion,
            created_by_stylist=True,
            compatibility_score=coherence.overall,
            compatibility_notes=coherence.notes or None,
        )
        db.add(outfit)
        await db.flush()
        for pos, (product, slot) in enumerate(zip(chosen_products, slots)):
            db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))

    stylist_request = StylistRequest(
        user_id=user_id,
        prompt=req.prompt,
        occasion=req.occasion,
        budget_min_cents=req.budget_min_cents,
        budget_max_cents=req.budget_max_cents,
        style=req.style,
        response_summary=recommendation.summary,
        recommended_product_ids=[p.id for p in chosen_products],
        recommended_outfit_id=outfit.id if outfit else None,
    )
    db.add(stylist_request)
    await db.commit()
    await db.refresh(stylist_request)
    return stylist_request
