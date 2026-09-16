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

from app.core.logging import logger
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError
from app.retailers.registry import get_all_providers


@dataclass(frozen=True, slots=True)
class LiveSearchResult:
    provider: ProductProvider
    raw: RawProduct


async def live_search(query: str, *, limit: int = 24) -> list[LiveSearchResult]:
    """Fan out one query to every retailer that supports live search,
    skipping (not failing on) an unconfigured or currently-broken one —
    same resilience guarantee the bulk sync path gives per retailer."""
    results: list[LiveSearchResult] = []

    for provider in get_all_providers():
        if len(results) >= limit:
            break
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
