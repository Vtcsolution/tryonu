"""Drop the other gender's listings from live retailer results.

Searching "men leather ankle boots" on eBay still returns women's heels
(reported live: a man's boot alternatives were red pumps and "Reaction
Women's Boots"), because retailers match the words, not the shopper. The
listing title is the only reliable signal here — eBay's Browse API doesn't
return a gender field on search rows.

Deliberately permissive: only a title that clearly names the OTHER gender
is dropped. Unisex items, and the many listings that say nothing, are kept
— and if filtering would leave nothing at all, nothing is filtered, since
an empty result is worse than a mixed one.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import TypeVar

_WOMEN = re.compile(r"\b(women|women's|womens|woman|woman's|ladies|lady|girl|girls|girl's|female)\b", re.I)
_MEN = re.compile(r"\b(men|men's|mens|man|man's|gents|gent|boy|boys|boy's|male)\b", re.I)
_UNISEX = re.compile(r"\b(unisex|his and hers|couple)\b", re.I)

T = TypeVar("T")


def gender_of(title: str) -> str | None:
    """"men", "women", or None when the title says neither or both.

    Note "women" contains "men": the word boundaries matter, and a title
    naming both ("Men Women Unisex Bracelet") counts as neither."""
    women, men = bool(_WOMEN.search(title)), bool(_MEN.search(title))
    if _UNISEX.search(title) or (women and men):
        return None
    if women:
        return "women"
    return "men" if men else None


def is_other_gender(title: str, gender: str | None) -> bool:
    if gender not in ("men", "women"):
        return False
    other = gender_of(title)
    return other is not None and other != gender


def keep_for_gender(items: Iterable[T], gender: str | None, title: Callable[[T], str] = str) -> list[T]:
    items = list(items)
    if gender not in ("men", "women"):
        return items
    kept = [item for item in items if not is_other_gender(title(item), gender)]
    return kept or items  # never leave the shopper with nothing
