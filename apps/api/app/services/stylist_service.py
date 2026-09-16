"""AI fashion stylist: turns a free-text ask into a curated set of *real*
products, fetched live from retailer APIs at request time — never from a
pre-synced local catalog (see live_search_service.py). The LLM never sees
or invents products outside a pre-filtered candidate shortlist — see
app/ai/llm/base.py for how that's enforced. A candidate only ever becomes
a saved row in our own database at the very end, and only for the
specific items the LLM actually chose — see
product_ingestion_service.persist_single_product.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.base import StylistCandidate, StylistQuery
from app.ai.llm.registry import get_stylist_provider
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from app.models.stylist import StylistRequest
from app.models.wardrobe import WardrobeItem
from app.retailers.base import RawProduct
from app.schemas.stylist import StylistAskRequest
from app.services.live_search_service import LiveSearchResult, live_search
from app.services.outfit_compatibility import score_outfit
from app.services.personalization_service import TasteProfile, affinity_score, build_taste_profile
from app.services.product_ingestion_service import persist_single_product

_CANDIDATE_POOL_SIZE = 40
_LIVE_FETCH_POOL_SIZE = 60  # widened before personalized re-ranking trims to _CANDIDATE_POOL_SIZE
_RECENT_TURNS = 3

# Real, live-confirmed bug: eBay indexes individual product listings, not
# outfits — searching "jacket AND jeans AND sneakers" as one sentence
# essentially never matches a single real listing (a title would need all
# three words), so a multi-item outfit prompt returned zero candidates.
# These are the item-type words we recognize in a free-text prompt so each
# one becomes its own short search ("leather jacket", "sneakers", ...) —
# exactly the kind of query eBay's search reliably handles — merged into
# one candidate pool, same end result as the old fixed-category-list bulk
# ingestion, just derived from this prompt instead of a hardcoded list.
_ITEM_CATEGORY_WORDS = {
    "dress", "dresses", "jacket", "jackets", "jean", "jeans", "sneaker", "sneakers",
    "shoe", "shoes", "boot", "boots", "t-shirt", "tshirt", "shirt", "shirts", "sweater",
    "sweaters", "hoodie", "hoodies", "coat", "coats", "blazer", "blazers", "suit", "suits",
    "handbag", "handbags", "bag", "bags", "sunglasses", "watch", "watches", "hat", "hats",
    "cap", "caps", "skirt", "skirts", "shorts", "scarf", "scarves", "belt", "belts",
    "trouser", "trousers", "pant", "pants", "legging", "leggings", "cardigan", "vest",
    "gown", "romper", "jumpsuit", "sandals", "heels", "flats", "loafers", "trainers",
}
_TERM_STOPWORDS = {"a", "an", "the", "and", "with", "or", "for", "to", "of", "in", "on", "over", "under"}


def _extract_search_terms(prompt: str) -> list[str]:
    """Finds each recognized item-type word in the prompt and pairs it with
    an immediately preceding descriptive word when there is one ("leather
    jacket", not just "jacket") — one short query per distinct item
    mentioned, in the order they appear, deduplicated."""
    words = re.findall(r"[a-z']+", prompt.lower())
    terms: list[str] = []
    seen: set[str] = set()
    for i, word in enumerate(words):
        if word not in _ITEM_CATEGORY_WORDS:
            continue
        prev = words[i - 1] if i > 0 else ""
        term = f"{prev} {word}" if prev and prev not in _TERM_STOPWORDS and prev not in _ITEM_CATEGORY_WORDS else word
        if term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


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


@dataclass(frozen=True, slots=True)
class _Candidate:
    result: LiveSearchResult
    term: str  # the exact query that produced it — used to find alternatives sharing it


async def _fetch_candidates(req: StylistAskRequest, profile: TasteProfile | None) -> list[_Candidate]:
    """Every candidate is fetched fresh from retailer APIs for this exact
    prompt — nothing here is a pre-synced local row. Budget filtering and
    personalized re-ranking both happen over that live pool in Python
    rather than in SQL, since there's no local table to filter/sort with a
    WHERE/ORDER BY. Each candidate keeps the term that found it, so
    ask_stylist can offer real alternatives at other price points for
    whichever ones the LLM ends up choosing."""
    terms = _extract_search_terms(req.prompt)
    if terms:
        # One short search per distinct item mentioned (see
        # _extract_search_terms) — a multi-item outfit prompt otherwise
        # returns zero results, since no single real listing's title
        # contains every item type at once.
        per_term_limit = max(4, _LIVE_FETCH_POOL_SIZE // len(terms))
        term_results = await asyncio.gather(*(live_search(t, limit=per_term_limit) for t in terms))
        pool: list[_Candidate] = []
        seen_ids: set[tuple[str, str]] = set()
        for term, results in zip(terms, term_results):
            for r in results:
                key = (r.provider.slug, r.raw.retailer_product_id)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                pool.append(_Candidate(result=r, term=term))
    else:
        # No recognized item word (e.g. a bare brand/style ask) — fall
        # back to the prompt as a single query, same as before.
        pool = [_Candidate(result=r, term=req.prompt) for r in await live_search(req.prompt, limit=_LIVE_FETCH_POOL_SIZE)]

    if req.budget_min_cents is not None:
        pool = [c for c in pool if c.result.raw.price_cents >= req.budget_min_cents]
    if req.budget_max_cents is not None:
        pool = [c for c in pool if c.result.raw.price_cents <= req.budget_max_cents]

    if profile and profile.has_signal:
        # affinity_score only reads .color/.brand/.style_tags — present on
        # RawProduct with the same names, so this works unmodified even
        # though its signature says Product.
        pool.sort(key=lambda c: affinity_score(c.result.raw, profile), reverse=True)  # type: ignore[arg-type]

    return pool[:_CANDIDATE_POOL_SIZE]


_MAX_ALTERNATIVES = 8


def _alternatives_for(chosen: _Candidate, pool: list[_Candidate]) -> list[RawProduct]:
    """Other real, live-fetched results for the same item type — spanning
    low to high price so "show me other options, cheap and expensive" is
    real data, not invented. Never includes the chosen item itself."""
    same_term = [
        c.result.raw
        for c in pool
        if c.term == chosen.term and c.result.raw.retailer_product_id != chosen.result.raw.retailer_product_id
    ]
    if not same_term:
        return []
    by_price = sorted(same_term, key=lambda raw: raw.price_cents)
    if len(by_price) <= _MAX_ALTERNATIVES:
        return by_price
    # spread across the price range rather than just "the next 3 cheapest"
    step = (len(by_price) - 1) / (_MAX_ALTERNATIVES - 1)
    return [by_price[round(i * step)] for i in range(_MAX_ALTERNATIVES)]


def _slot_for(raw: RawProduct) -> OutfitSlot:
    cat = raw.category_slug or ""
    name = raw.name.lower()
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


async def ask_stylist(
    db: AsyncSession, *, user_id: str, req: StylistAskRequest
) -> tuple[StylistRequest, dict[str, tuple[str, list[RawProduct]]]]:
    wardrobe_item: WardrobeItem | None = None
    if req.wardrobe_item_id:
        wardrobe_item = await _load_owned_wardrobe_item(db, user_id, req.wardrobe_item_id)

    # An explicit "build around this" anchor takes priority over general
    # taste — the user asked for something specific, not just a good match.
    profile = _wardrobe_anchor_profile(wardrobe_item) if wardrobe_item else await build_taste_profile(db, user_id)
    candidates = await _fetch_candidates(req, profile)
    llm_candidates = [
        StylistCandidate(
            index=i,
            name=c.result.raw.name,
            brand=c.result.raw.brand,
            category=c.result.raw.category_slug,
            color=c.result.raw.color,
            price_cents=c.result.raw.price_cents,
            style_tags=c.result.raw.style_tags or [],
        )
        for i, c in enumerate(candidates)
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
        error_message = str(exc)[:512]  # AIUsage.error_message is VARCHAR(512)
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
        return stylist_request, {}

    chosen = [candidates[i] for i in recommendation.chosen_indexes if 0 <= i < len(candidates)]

    # The one point a live-searched candidate becomes a saved row — only
    # for what the LLM actually chose, never the rest of the pool it saw.
    chosen_products = [await persist_single_product(db, c.result.provider, c.result.raw) for c in chosen]

    # Real alternatives at other price points for each chosen item — from
    # results already fetched above, never an extra API call, never
    # invented. Keeps the search term alongside them so a client can
    # re-locate and persist one via POST /products/select-live if picked.
    alternatives_by_product_id = {
        product.id: (c.term, _alternatives_for(c, candidates)) for product, c in zip(chosen_products, chosen)
    }

    outfit: Outfit | None = None
    if len(chosen_products) > 1:
        slots = [_slot_for(c.result.raw) for c in chosen]
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
    return stylist_request, alternatives_by_product_id
