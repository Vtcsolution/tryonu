"""Live, on-demand product search — the browse/search UI and the AI
stylist call this directly against real retailer APIs instead of reading
from a pre-synced local catalog. Nothing here writes to the database;
see product_ingestion_service.persist_single_product for the one place a
live result becomes a real, saved Product — only once a user actually
selects it (for a try-on, or the AI stylist choosing it for an outfit),
never speculatively for a whole page of search results.

Only eBay implements ProductProvider.search_live right now (the only
retailer with a real, working account — CJ is blocked on their side,
Rakuten has zero approved advertiser partnerships; see those providers'
own docstrings). This loops every registered provider generically so CJ
and Rakuten join automatically once their account-side blockers clear —
no code change needed here when that happens.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from sqlalchemy import select

from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.product import Product
from app.models.retailer import Retailer
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError
from app.retailers.registry import get_all_providers
from app.schemas.product import LiveProductOut


@dataclass(frozen=True, slots=True)
class LiveSearchResult:
    provider: ProductProvider
    raw: RawProduct


# A short memory of what each query returned. The AI stylist fires one
# search per item in a prompt — a ten-item bridal look is ten searches,
# several of which repeat across shoppers within minutes. Kept brief
# because prices and availability are the point of searching live, and
# admin hides/disables are re-applied on every read regardless.
_MAX_PER_RETAILER = 48
_CACHE_TTL_SECONDS = 180
_CACHE_MAX_ENTRIES = 400
_cache: dict[tuple[str, int], tuple[float, list[LiveSearchResult]]] = {}


def _cached(query: str, limit: int) -> list[LiveSearchResult] | None:
    hit = _cache.get((query, limit))
    if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _remember(query: str, limit: int, results: list[LiveSearchResult]) -> None:
    if not results:  # never cache an empty answer — it may be a transient outage
        return
    if len(_cache) >= _CACHE_MAX_ENTRIES:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
    _cache[(query, limit)] = (time.monotonic(), results)


def to_live_product_out(result: LiveSearchResult) -> LiveProductOut:
    r = result.raw
    return LiveProductOut(
        retailer_slug=result.provider.slug,
        retailer_product_id=r.retailer_product_id,
        name=r.name,
        brand=r.brand,
        merchant_name=r.merchant_name,
        description=r.description,
        subcategory=r.subcategory,
        gender=r.gender,
        color=r.color,
        sizes=r.sizes,
        style_tags=r.style_tags,
        price_cents=r.price_cents,
        currency=r.currency,
        rating=r.rating,
        rating_count=r.rating_count,
        availability=r.availability,
        product_url=r.product_url,
        images=r.images,
        retailer_name=result.provider.display_name,
    )


async def _disabled_retailer_slugs() -> set[str]:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(select(Retailer.slug).where(Retailer.is_active.is_(False)))
        return set(rows.scalars().all())


async def _hidden_product_keys(results: list[LiveSearchResult]) -> set[tuple[str, str]]:
    ids = {r.raw.retailer_product_id for r in results}
    if not ids:
        return set()
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Retailer.slug, Product.retailer_product_id)
            .join(Retailer, Product.retailer_id == Retailer.id)
            .where(Product.is_active.is_(False), Product.retailer_product_id.in_(ids))
        )
        return {(slug, pid) for slug, pid in rows.all()}


async def apply_admin_filters(results: list[LiveSearchResult]) -> list[LiveSearchResult]:
    """Re-applies retailer disables and product hides to results fetched
    earlier (e.g. cached), so those admin controls stay immediate."""
    disabled = await _disabled_retailer_slugs()
    results = [r for r in results if r.provider.slug not in disabled]
    hidden = await _hidden_product_keys(results)
    return [r for r in results if (r.provider.slug, r.raw.retailer_product_id) not in hidden]


def _normalised_title(name: str) -> str:
    """A title stripped down to what two listings of the same thing share:
    lowercase words only, so "Casio LQ-142E-1ADF (NEW!)" and
    "Casio LQ 142E 1ADF new" collapse together."""
    return " ".join(re.findall(r"[a-z0-9]+", name.lower()))


def _deduplicate(results: list[LiveSearchResult]) -> list[LiveSearchResult]:
    """One product, once — without hiding things a shopper wants to see.

    Two cases are dropped. The same id from the same retailer is the same
    listing arriving twice. The same title at the same price from a
    *different* retailer is one product reached through two networks we
    are both connected to (a merchant's own feed and CJ, AliExpress and
    Daraz) — the shopper gains nothing from seeing it twice.

    Deliberately NOT dropped: two listings with the same title and price
    from the same retailer. Those are usually variants — the red one and
    the blue one — and that's a choice, not a duplicate. Titles shorter
    than three words are too generic to judge by, so they are left alone
    as well."""
    seen_ids: set[tuple[str, str]] = set()
    elsewhere: dict[tuple[str, int], str] = {}
    kept: list[LiveSearchResult] = []
    for result in results:
        key = (result.provider.slug, result.raw.retailer_product_id)
        if key in seen_ids:
            continue
        title = _normalised_title(result.raw.name)
        same_product = (title, result.raw.price_cents)
        if len(title.split()) >= 3 and elsewhere.get(same_product, result.provider.slug) != result.provider.slug:
            continue
        seen_ids.add(key)
        elsewhere.setdefault(same_product, result.provider.slug)
        kept.append(result)
    return kept


def _interleave(per_provider: list[list[LiveSearchResult]]) -> list[LiveSearchResult]:
    """Round-robin, so the answer is a mix of the retailers rather than
    whichever one happens to be asked first."""
    mixed: list[LiveSearchResult] = []
    for rank in range(max((len(batch) for batch in per_provider), default=0)):
        for batch in per_provider:
            if rank < len(batch):
                mixed.append(batch[rank])
    return mixed


async def _ask(provider: ProductProvider, query: str, limit: int) -> list[LiveSearchResult]:
    """One retailer's answer, or none — an unconfigured, unsupported or
    briefly broken retailer must never take the others down with it."""
    try:
        found = await provider.search_live(query=query, limit=limit)
    except (NotImplementedError, RetailerNotConfiguredError):
        return []
    except Exception as exc:  # noqa: BLE001 — one bad retailer must not break the whole search
        logger.warning("live_search_provider_failed", retailer=provider.slug, error=str(exc))
        return []
    return [LiveSearchResult(provider=provider, raw=raw) for raw in found]


async def live_search(query: str, *, limit: int = 24) -> list[LiveSearchResult]:
    """Fan out one query to every retailer that supports live search, all
    at once, and return a deduplicated mix of what they say.

    Every retailer is asked for a full share of the results and they are
    then interleaved: asking them in turn and stopping at `limit` meant
    whichever provider came first in the registry filled the page and the
    rest were never reached at all — connecting a new retailer changed
    nothing visible.

    Results never come from our own database, so admin controls are
    applied here: a retailer an admin disabled isn't queried at all, and a
    product an admin hid is dropped even though the retailer still lists it."""
    cached = _cached(query, limit)
    if cached is not None:
        return await apply_admin_filters(cached)

    disabled = await _disabled_retailer_slugs()
    providers = [p for p in get_all_providers() if p.slug not in disabled]
    if not providers:
        return []

    # each retailer is asked for enough to fill the page on its own: they
    # answer different amounts, and a thin answer from one shouldn't leave
    # the page short
    share = max(8, min(limit, _MAX_PER_RETAILER))
    per_provider = await asyncio.gather(*(_ask(provider, query, share) for provider in providers))

    results = _deduplicate(_interleave(list(per_provider)))
    hidden = await _hidden_product_keys(results)
    if hidden:
        results = [r for r in results if (r.provider.slug, r.raw.retailer_product_id) not in hidden]
    results = results[:limit]
    _remember(query, limit, results)
    return results


async def find_live_result(query: str, *, retailer_slug: str, retailer_product_id: str) -> LiveSearchResult | None:
    """Re-locates one specific item a user picked from an earlier live
    search — used to re-verify a selection server-side (real current
    price/availability/url) right before persisting it, rather than
    trusting whatever the client last had cached.

    Asks the retailer for that exact listing first. Searching for it
    again means asking the retailer to rank it back into the first page
    of results for the same words, which it does not reliably do — a
    shopper was told "that item is no longer available" about a product
    sitting on screen in front of them. Only a retailer that can't look
    items up by id falls back to the search scan."""
    provider = next((p for p in get_all_providers() if p.slug == retailer_slug), None)
    if provider is not None:
        try:
            raw = await provider.fetch_by_id(retailer_product_id)
        except (NotImplementedError, RetailerNotConfiguredError):
            raw = None
        except Exception as exc:  # noqa: BLE001 — fall back to the search
            logger.warning("find_live_by_id_failed", retailer=retailer_slug, error=str(exc)[:200])
            raw = None
        else:
            if raw is not None:
                return LiveSearchResult(provider=provider, raw=raw)
            # a definite "gone" from the retailer still deserves the
            # search fallback: some ids only resolve through search
            logger.info("find_live_by_id_empty", retailer=retailer_slug, product=retailer_product_id[:60])

    for result in await live_search(query, limit=48):
        if result.provider.slug == retailer_slug and result.raw.retailer_product_id == retailer_product_id:
            return result
    return None
