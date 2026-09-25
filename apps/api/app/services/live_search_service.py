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
from app.services.relevance import keep_relevant
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
_SHORT_QUERY_WORDS = 5  # enough to name a thing, short enough for a retailer to match
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

    Listings from the *same* retailer at the same price whose titles
    agree up to their last few words are variants — the red one and the
    blue one — and that's a choice, not a duplicate, so the first two are
    kept. Not all of them: live, "New 2 Pc Pakistani Print Lawn Kurti
    Trousers Suit Scalloped Trim" at $29.99 in Magenta, Sage, Black,
    Navy and Black XL took five of the twelve places on the shelf. The
    comparison ignores the tail of the title because that is where a
    colour and a size sit. A shopper who wants the other colours can open
    the listing.

    Titles shorter than three words are too generic to judge by, so they
    are left alone."""
    _VARIANTS_SHOWN = 2
    _NAME_WORDS = 8  # colour and size live at the end of a listing title
    seen_ids: set[tuple[str, str]] = set()
    elsewhere: dict[tuple[str, int], str] = {}
    variants: dict[tuple[str, str, int], int] = {}
    kept: list[LiveSearchResult] = []
    for result in results:
        key = (result.provider.slug, result.raw.retailer_product_id)
        if key in seen_ids:
            continue
        title = _normalised_title(result.raw.name)
        same_product = (title, result.raw.price_cents)
        if len(title.split()) >= 3:
            if elsewhere.get(same_product, result.provider.slug) != result.provider.slug:
                continue
            here = (result.provider.slug, " ".join(title.split()[:_NAME_WORDS]), result.raw.price_cents)
            if variants.get(here, 0) >= _VARIANTS_SHOWN:
                continue
            variants[here] = variants.get(here, 0) + 1
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

    # Relevance is judged inside each retailer's own answer, before they
    # are mixed. Retailers match loosely — "khussa shoes" came back from
    # one of them as men's sneakers — but they also use different words
    # for the same thing, and judging the merged list let one retailer's
    # vocabulary wipe another off the page: a "pakistani lawn suit"
    # search fetched 48 listings from each of eBay and AliExpress and put
    # twelve eBay ones on the shelf, because AliExpress sellers write
    # "Punjabi 3-piece" and never "lawn". Each retailer now keeps its own
    # best matches and they are mixed afterwards, so the shelf is a mix.
    # keep_at_least=0: a retailer with nothing relevant contributes
    # nothing, rather than padding its own noise back in. The promise that
    # a shopper never gets an empty page belongs to the shelf, and is kept
    # below.
    relevant = [
        keep_relevant(batch, query, title=lambda r: r.raw.name, keep_at_least=0)
        for batch in per_provider
    ]
    results = _deduplicate(_interleave(relevant))
    if not results:
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
    if provider is None:
        return None
    if provider.slug in await _disabled_retailer_slugs():
        return None  # an admin turned this retailer off

    raw = await _by_id(provider, retailer_product_id) or await _by_search(
        provider, query, retailer_product_id
    )
    if raw is None:
        return None
    result = LiveSearchResult(provider=provider, raw=raw)
    hidden = await _hidden_product_keys([result])
    return None if (provider.slug, raw.retailer_product_id) in hidden else result


async def _by_id(provider: ProductProvider, retailer_product_id: str) -> RawProduct | None:
    """The listing itself, from the retailers that can look one up."""
    try:
        raw = await provider.fetch_by_id(retailer_product_id)
    except (NotImplementedError, RetailerNotConfiguredError):
        return None
    except Exception as exc:  # noqa: BLE001 — fall back to the search
        logger.warning("find_live_by_id_failed", retailer=provider.slug, error=str(exc)[:200])
        return None
    if raw is None:
        # a definite "gone" from the retailer still deserves the search
        # fallback: some ids only resolve through search
        logger.info("find_live_by_id_empty", retailer=provider.slug, product=retailer_product_id[:60])
    return raw


async def _by_search(provider: ProductProvider, query: str, retailer_product_id: str) -> RawProduct | None:
    """Ask that one retailer for the same words and look for the id.

    Deliberately not live_search(): that builds the shopper-facing shelf,
    and everything it does to make a shelf readable — dropping listings
    that don't match the query's distinctive words, dropping a duplicate
    of something another retailer also sells, cutting to one page — can
    drop the very item being looked up. Here we already know exactly
    which listing is wanted, so none of it applies.

    The words are tried shortest-last. A stylist alternative is clicked
    with its own full title as the query, and AliExpress answers a long
    brand-heavy title with nothing at all (verified live: 0 results for
    "Fabulicious Women's Black Patent Platform Heels", 3 for "black
    patent platform heels") — so a first-page miss gets one more try with
    the query cut down."""
    for words in _narrowing(query):
        try:
            found = await provider.search_live(query=words, limit=_MAX_PER_RETAILER)
        except (NotImplementedError, RetailerNotConfiguredError):
            return None
        except Exception as exc:  # noqa: BLE001 — a broken retailer reads as "gone"
            logger.warning("find_live_search_failed", retailer=provider.slug, error=str(exc)[:200])
            return None
        for raw in found:
            if raw.retailer_product_id == retailer_product_id:
                return raw
    logger.info(
        "find_live_not_found", retailer=provider.slug, product=retailer_product_id[:60], query=query[:80]
    )
    return None


def _narrowing(query: str) -> list[str]:
    """The query, then a shorter version of it if there is one worth
    trying — the first few words that actually pin it down."""
    words = query.split()
    if len(words) <= _SHORT_QUERY_WORDS:
        return [query]
    return [query, " ".join(words[:_SHORT_QUERY_WORDS])]
