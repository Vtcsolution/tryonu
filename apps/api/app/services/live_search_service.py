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


async def live_search(query: str, *, limit: int = 24) -> list[LiveSearchResult]:
    """Fan out one query to every retailer that supports live search,
    skipping (not failing on) an unconfigured or currently-broken one —
    same resilience guarantee the bulk sync path gives per retailer.

    Results never come from our own database, so admin controls are
    applied here: a retailer an admin disabled isn't queried at all, and a
    product an admin hid is dropped even though the retailer still lists it."""
    results: list[LiveSearchResult] = []
    disabled = await _disabled_retailer_slugs()

    for provider in get_all_providers():
        if len(results) >= limit:
            break
        if provider.slug in disabled:
            continue
        try:
            provider_results = await provider.search_live(query=query, limit=limit - len(results))
        except NotImplementedError:
            continue
        except RetailerNotConfiguredError:
            continue
        except Exception as exc:  # noqa: BLE001 — one bad retailer must not break the whole search
            logger.warning("live_search_provider_failed", retailer=provider.slug, error=str(exc))
            continue

        results.extend(LiveSearchResult(provider=provider, raw=raw) for raw in provider_results)

    hidden = await _hidden_product_keys(results)
    if hidden:
        results = [r for r in results if (r.provider.slug, r.raw.retailer_product_id) not in hidden]
    return results[:limit]


async def find_live_result(query: str, *, retailer_slug: str, retailer_product_id: str) -> LiveSearchResult | None:
    """Re-locates one specific item a user picked from an earlier live
    search — used to re-verify a selection server-side (real current
    price/availability/url) right before persisting it, rather than
    trusting whatever the client last had cached."""
    for result in await live_search(query, limit=48):
        if result.provider.slug == retailer_slug and result.raw.retailer_product_id == retailer_product_id:
            return result
    return None
