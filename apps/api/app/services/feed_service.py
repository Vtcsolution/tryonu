"""The personalised "For you" feed: live retailer results for exactly the
categories a user picked in onboarding (app/core/taxonomy.py), filtered by
their budget and ranked by their taste profile."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.core.taxonomy import NODES, PARENTS, Node, feed_nodes
from app.models.preference import UserPreference
from app.services.live_search_service import LiveSearchResult, apply_admin_filters, live_search
from app.services.personalization_service import TasteProfile, affinity_score

MAX_SECTIONS_IN_MIX = 8
_PER_SEARCH = 24
_CACHE_TTL_SECONDS = 600
_CACHE_MAX_ENTRIES = 500
_cache: dict[str, tuple[float, list[LiveSearchResult]]] = {}


@dataclass
class FeedEntry:
    node: Node
    result: LiveSearchResult


async def _search_cached(phrase: str) -> list[LiveSearchResult]:
    hit = _cache.get(phrase)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    results = await live_search(phrase, limit=_PER_SEARCH)
    if results:  # never cache an empty answer — it may be a transient retailer failure
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[phrase] = (time.monotonic(), results)
    return results


def sections_for(pref: UserPreference | None) -> list[Node]:
    gender = pref.gender.value if pref and pref.gender else None
    return feed_nodes((pref.preferred_categories or []) if pref else [], gender)


def parent_label(node: Node) -> str | None:
    parent = PARENTS.get(node.id)
    # audience level (Women/Men/Kids) adds nothing to "Kundan · Bangles"
    return NODES[parent].label if parent and PARENTS.get(parent) is not None else None


def _in_budget(result: LiveSearchResult, pref: UserPreference | None) -> bool:
    if pref is None:
        return True
    price = result.raw.price_cents
    if pref.budget_min_cents is not None and price < pref.budget_min_cents:
        return False
    if pref.budget_max_cents is not None and price > pref.budget_max_cents:
        return False
    return True


async def _entries_for(node: Node, pref: UserPreference | None, profile: TasteProfile | None) -> list[FeedEntry]:
    results = await apply_admin_filters(await _search_cached(node.search))
    results = [r for r in results if _in_budget(r, pref)]
    if profile is not None and profile.has_signal:
        # affinity_score only reads color/brand/style_tags, which RawProduct has too
        results.sort(key=lambda r: affinity_score(r.raw, profile), reverse=True)  # type: ignore[arg-type]
    return [FeedEntry(node=node, result=r) for r in results]


async def for_you(
    pref: UserPreference | None, profile: TasteProfile | None, *, node: Node | None, limit: int
) -> list[FeedEntry]:
    targets = [node] if node is not None else sections_for(pref)[:MAX_SECTIONS_IN_MIX]
    if not targets:
        return []
    per_node = await asyncio.gather(*(_entries_for(t, pref, profile) for t in targets))

    # round-robin across categories so "Top picks" isn't just the first one
    mixed: list[FeedEntry] = []
    seen: set[tuple[str, str]] = set()
    for rank in range(max(len(lst) for lst in per_node)):
        for lst in per_node:
            if rank >= len(lst):
                continue
            entry = lst[rank]
            key = (entry.result.provider.slug, entry.result.raw.retailer_product_id)
            if key in seen:
                continue
            seen.add(key)
            mixed.append(entry)
            if len(mixed) >= limit:
                return mixed
    return mixed
