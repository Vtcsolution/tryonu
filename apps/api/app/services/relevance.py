"""Drop results that aren't what the shopper asked for.

Retailers match loosely. Live: "khussa shoes" came back from AliExpress
as men's sneakers and gladiator sandals, and "maang tikka" as bracelets
— every one a real listing, none of them the thing asked for. Shown
alongside eBay's actual khussa, half the shelf was noise.

The rule is deliberately narrow: a query's *distinctive* words are the
ones that aren't category filler, and a listing has to contain at least
one of them. "khussa shoes" keeps khussa and drops sneakers; "maang
tikka" keeps tikka sets and drops bracelets; "women analog watch" keeps
analog watches. Nothing is scored on how pretty it looks — only on
whether the words the shopper typed are in the title.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")

# Words that describe a category or a shopper rather than a product: on
# their own they match nearly anything, so they can't carry a query.
_FILLER = {
    "a", "an", "and", "for", "from", "in", "of", "or", "the", "to", "with",
    "boy", "boys", "female", "gent", "gents", "girl", "girls", "kid", "kids",
    "ladies", "lady", "male", "man", "mans", "men", "mens", "woman", "womans",
    "women", "womens", "unisex",
    "bag", "bags", "belt", "belts", "boot", "boots", "clothes", "clothing",
    "dress", "dresses", "earring", "earrings", "flats", "footwear", "jewellery",
    "jewelry", "necklace", "necklaces", "outfit", "outfits", "pant", "pants",
    "ring", "rings", "sandal", "sandals", "shirt", "shirts", "shoe", "shoes",
    "slippers", "sneaker", "sneakers", "suit", "suits", "top", "tops",
    "trouser", "trousers", "watch", "watches",
    "beautiful", "best", "casual", "designer", "elegant", "fashion", "latest",
    "luxury", "new", "party", "quality", "set", "sets", "size", "style",
    "stylish", "wear",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def distinctive(query: str) -> set[str]:
    """The words that actually pin down what was asked for."""
    words = {w for w in _words(query) if len(w) > 2}
    return words - _FILLER


def matches(title: str, wanted: set[str]) -> bool:
    if not wanted:
        return True  # nothing distinctive to check against
    title_words = set(_words(title))
    return any(word in title_words for word in wanted)


def keep_relevant(
    items: Iterable[T], query: str, *, title: Callable[[T], str] = str, keep_at_least: int = 3
) -> list[T]:
    """`items` filtered to those that actually answer `query`.

    Never empties a shelf: if too few survive, the rest follow behind the
    ones that matched, because an empty page is worse than a loose one
    and the shopper can judge for themselves."""
    items = list(items)
    wanted = distinctive(query)
    if not wanted:
        return items

    kept = [item for item in items if matches(title(item), wanted)]
    if len(kept) >= keep_at_least:
        return kept
    rest = [item for item in items if item not in kept]
    return kept + rest[: max(0, keep_at_least - len(kept))] if kept else items
