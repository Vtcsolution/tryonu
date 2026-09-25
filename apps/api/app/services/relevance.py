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


# Words for the same thing. Shoppers and sellers in this market use them
# interchangeably — eBay's own listings say "Pakistani Indian 3 Piece
# Embroidered Lawn Suit" — and AliExpress sellers reach for "Punjabi"
# where a Karachi shopper types "Pakistani". Without this, a search
# fetched 48 real listings from AliExpress and put one on the shelf.
#
# Kept deliberately small, and only for words that name the same object.
# "lawn" and "cotton" were in here briefly: lawn is a cotton cloth, so it
# reads as harmless, but it let a printed cotton sari answer "pakistani
# lawn suit" as completely as a lawn suit does, and the sari came second
# on the shelf. A fabric a thing is made of is not the thing.
_SAME_THING = (
    {"pakistani", "pakistan", "indian", "india", "punjabi", "desi"},
    {"khussa", "jutti", "juttis", "mojari"},
    {"kameez", "kurta", "kurti", "kurtis"},
    {"dupatta", "chunni", "odhni"},
    {"lehenga", "ghagra", "gharara"},
    {"tikka", "teeka", "matha", "patti"},
)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def distinctive(query: str) -> set[str]:
    """The words that actually pin down what was asked for."""
    words = {w for w in _words(query) if len(w) > 2}
    return words - _FILLER


def _group(word: str) -> frozenset[str]:
    for group in _SAME_THING:
        if word in group:
            return frozenset(group)
    return frozenset({word})


def _same_word(a: str, b: str) -> bool:
    """One word or an obvious form of it.

    Retailers and shoppers inflect differently: a shopper types
    "pakistani" and the listing says "Pakistan", "embroidered" against
    "embroidery", "kurti" against "kurtis". Demanding the identical
    string threw away real matches — live, an AliExpress shelf of
    Punjabi 3-piece suits was dropped from a "pakistani lawn suit"
    search. Four letters of shared stem is enough to be the same word
    and short enough to stay cheap."""
    if a == b or b in _group(a):
        return True
    shared = min(len(a), len(b))
    return shared >= 4 and (a.startswith(b[:shared]) or b.startswith(a[:shared]))


def score(title: str, wanted: set[str]) -> int:
    """How many of the words that pin down the query this listing answers.

    Counting rather than answering yes/no is what makes a mixed shelf
    work. Live, on "pakistani lawn suit": every AliExpress title begins
    "Indian", so once "indian" counted as "pakistani" a sari and a
    dance costume passed on that one word alone and filled the shelf.
    A 3-piece cotton kurta set answers both words and a sari answers
    one, so the set goes first and the sari falls off the end."""
    title_words = set(_words(title))
    return sum(1 for word in wanted if any(_same_word(word, seen) for seen in title_words))


def matches(title: str, wanted: set[str]) -> bool:
    if not wanted:
        return True  # nothing distinctive to check against
    return score(title, wanted) > 0


def keep_relevant(
    items: Iterable[T], query: str, *, title: Callable[[T], str] = str, keep_at_least: int = 3
) -> list[T]:
    """`items` that answer `query`, best answers first.

    Never empties a shelf: if too few survive, the rest follow behind the
    ones that matched, because an empty page is worse than a loose one
    and the shopper can judge for themselves."""
    items = list(items)
    wanted = distinctive(query)
    if not wanted:
        return items

    # The filler words break ties. "pakistani lawn suit" pins down
    # "pakistani" and "lawn"; no AliExpress listing says "lawn", so every
    # one of them scored 1 and the order fell back to theirs, which put a
    # dance costume above a 3-piece kurta set. The kurta set says "suit"
    # and the costume doesn't — too weak to select on, strong enough to
    # order by.
    also = set(_words(query)) - distinctive(query)
    scored = [
        (score(title(item), wanted), score(title(item), also), item) for item in items
    ]
    # best answers first, and a retailer's own order held within a tie —
    # it knows more about its catalogue than we do
    ranked = sorted(scored, key=lambda s: (-s[0], -s[1]))
    kept = [item for points, _, item in ranked if points > 0]
    if len(kept) >= keep_at_least:
        return kept
    rest = [item for points, _, item in scored if points == 0]
    return kept + rest[: max(0, keep_at_least - len(kept))] if kept else items
