"""AI fashion stylist: turns a free-text ask into a curated set of *real*
catalog products. The LLM never sees or invents products outside a
pre-filtered candidate shortlist — see app/ai/llm/base.py for how that's
enforced.
"""

from __future__ import annotations

import time

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
from app.schemas.stylist import StylistAskRequest

_CANDIDATE_POOL_SIZE = 40


async def _fetch_candidates(db: AsyncSession, req: StylistAskRequest) -> list[Product]:
    stmt = select(Product).where(Product.is_active.is_(True)).options(
        selectinload(Product.images), selectinload(Product.retailer), selectinload(Product.category)
    )
    if req.budget_min_cents is not None:
        stmt = stmt.where(Product.price_cents >= req.budget_min_cents)
    if req.budget_max_cents is not None:
        stmt = stmt.where(Product.price_cents <= req.budget_max_cents)
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
    candidates = await _fetch_candidates(db, req)
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
        outfit = Outfit(user_id=user_id, occasion=req.occasion, created_by_stylist=True)
        db.add(outfit)
        await db.flush()
        for pos, product in enumerate(chosen_products):
            db.add(
                OutfitItem(
                    outfit_id=outfit.id, product_id=product.id, slot=_slot_for(product), position=pos
                )
            )

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
