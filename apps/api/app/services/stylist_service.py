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
from app.core.taxonomy import audience_of
from app.ai.llm.registry import get_stylist_provider
from app.core.config import get_settings
from app.core.logging import logger
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from app.models.preference import UserPreference
from app.models.stylist import StylistRequest
from app.models.wardrobe import WardrobeItem
from app.retailers.base import RawProduct
from app.schemas.stylist import StylistAskRequest
from app.services.gender_filter import fits_audience
from app.services.live_search_service import LiveSearchResult, live_search, match_score, store_rank
from app.services.outfit_compatibility import score_outfit
from app.services.outfit_slots import slot_for
from app.services.personalization_service import TasteProfile, affinity_score, build_taste_profile
from app.services.prompt_reader import read_prompt
from app.services.product_ingestion_service import persist_single_product
from app.services.shopper_context import current_country

_CANDIDATE_POOL_SIZE = 40
_LIVE_FETCH_POOL_SIZE = 60  # widened before personalized re-ranking trims to _CANDIDATE_POOL_SIZE
# results fetched for EACH item of a multi-item ask, so its "other options"
# row offers a real choice. Live: 9 items shared 60 results, then a 40-result
# trim, and each item showed only 3 options.
_PER_ITEM_RESULTS = 24
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
    # South Asian wear — "shalwar kameez" is two item words in a row, kept
    # together as one search (see _extract_search_terms)
    "shalwar", "salwar", "kameez", "kurta", "kurtas", "kurti", "kurtis", "lehenga", "lehengas",
    "saree", "sarees", "sari", "anarkali", "pishwas", "dupatta", "dupattas", "sherwani", "waistcoat",
    "abaya", "abayas", "hijab", "frock", "frocks", "palazzo", "palazzos", "khussa", "khussas", "kolhapuri", "chappal", "chappals", "mojari",
    # jewellery & accessories
    "jewellery", "jewelry", "bangle", "bangles", "bracelet", "bracelets", "ring", "rings",
    "earring", "earrings", "jhumka", "jhumkas", "necklace", "necklaces", "choker", "pendant",
    "anklet", "anklets", "tikka", "clutch", "clutches",
    # the rest of the onboarding taxonomy's items (app/core/taxonomy.py), so
    # a preference-built suggestion searches for every item it names
    "jilbab", "shawl", "shawls", "blouse", "blouses", "top", "tops", "activewear", "pin",
    "smartwatch", "wristwatch", "wristwatches", "chinos", "tuxedo", "wallet", "wallets", "cufflinks", "accessories",
    "backpack", "backpacks", "payal", "chappal", "purse", "tote", "romper", "rompers", "set", "sets",
    # winter wear — live: "black wool overcoat" was not searched at all
    "overcoat", "overcoats", "peacoat", "peacoats", "parka", "parkas", "puffer", "puffers", "trench",
    "turtleneck", "turtlenecks", "pullover", "pullovers", "jumper", "jumpers", "beanie", "beanies",
    "muffler", "mufflers", "gloves", "mittens",
}
# a third describing word is kept when it's a colour: live, "brown leather
# Chelsea boots" was searched as "leather chelsea boots", any colour
_LEAD_COLOURS = {
    "white", "black", "red", "blue", "green", "pink", "yellow", "maroon", "grey", "gray", "gold", "silver",
    "brown", "navy", "purple", "orange", "beige", "cream", "ivory", "teal", "charcoal", "camel", "tan",
    "khaki", "olive", "burgundy", "mustard", "rust",
}
# one garment worn on its own: a listing selling it as a set (sweater and
# trousers together) is not it. Live: "cream cable-knit sweater" picked a
# "knitted sweater set" with matching trousers, the shopper's own trousers
# already chosen.
_SEPARATES = {
    "sweater", "sweaters", "shirt", "shirts", "t-shirt", "tshirt", "hoodie", "hoodies", "cardigan", "blouse",
    "jacket", "jackets", "coat", "coats", "overcoat", "overcoats", "peacoat", "parka", "puffer", "blazer",
    "blazers", "trouser", "trousers", "pant", "pants", "jean", "jeans", "chinos", "turtleneck", "pullover",
    "jumper", "top", "tops",
}
_SET_OFFER = re.compile(r"\b(sets?|tracksuits?|co-?ords?|two[- ]piece|2[- ]?(piece|pc|pcs))\b")
# Generic umbrella words, each mapped to the specific items it's a mere
# lead-in for — real bug, found live: "two jewelry pieces (earrings and
# bangles)" produced three separate searches ("jewelry", "earrings",
# "bangles") instead of two, because "jewelry" is itself a recognized item
# word, not just a lead-in to the specific ones named right after it. The
# outfit came back with 6 items instead of 5: an extra, unwanted second
# pair of earrings from the generic term's own top result. Dropped only
# when the prompt also names a specific item from WITHIN that umbrella —
# "a dress and some jewelry" (nothing more specific) must still search
# for it; "dress" being present elsewhere is not grounds to drop it.
_JEWELRY_WORDS = {
    "bangle", "bangles", "bracelet", "bracelets", "ring", "rings", "earring", "earrings",
    "jhumka", "jhumkas", "necklace", "necklaces", "choker", "pendant", "anklet", "anklets",
    "tikka", "payal",
}
_GENERIC_UMBRELLA_WORDS: dict[str, set[str]] = {
    "jewelry": _JEWELRY_WORDS,
    "jewellery": _JEWELRY_WORDS,
}
_TERM_STOPWORDS = {
    "a", "an", "the", "and", "with", "or", "for", "to", "of", "in", "on", "over", "under",
    # conversational filler a shopper types around the actual ask — real
    # bug, live: "apply ear rings, ... and also watch" built the search
    # terms "apply ear rings" and "also watch", because neither word is a
    # stopword, a category word or a gender word, so the "describing
    # words right before it" rule swept them in as if they were "white"
    # or "leather". "apply ear rings" found 2 real listings; "ear rings"
    # alone found 10 — the extra word wasn't neutral, it actively hurt.
    "apply", "add", "also", "please", "want", "wants", "wanted", "need", "needs", "needed",
    "show", "get", "give", "looking", "like", "would", "some", "any", "just", "can", "could",
    "i", "me", "my", "you", "your", "its", "it's",
    # Real bug, found live: "a kurti, matching trousers" built the search
    # term "women matching trousers" — "matching" isn't a stopword, a
    # category word or a gender word, so it was swept in as if it were a
    # real descriptor like "white" or "leather". That term's top live
    # result was a Western blazer-and-trousers SET literally titled
    # "...BLAZER JACKET AND MATCHING TROUSERS...", chosen for the
    # trousers slot, which rendered as a second, incompatible top-layer
    # garment over the kurti. Same bug class as "apply"/"also" above:
    # "matching"/"coordinating" describe a relationship to another item,
    # not the item itself, and have no business being an eBay search word.
    "matching", "coordinating",
}
# words that turn the item after them into something NOT wanted
_NEGATIONS = {"no", "not", "without", "except", "excluding", "skip", "avoid", "don't", "dont", "never"}
# who the ask is for — said outright, or through who it's being bought for
_WOMEN_WORDS = {
    "women", "women's", "womens", "woman", "woman's", "ladies", "lady", "girl", "girls", "girl's", "female",
    "wife", "wife's", "girlfriend", "mum", "mom", "mother", "sister", "daughter", "bride",
}
_MEN_WORDS = {
    "men", "men's", "mens", "man", "man's", "gents", "boy", "boys", "boy's", "guy", "guys", "male",
    "husband", "husband's", "boyfriend", "dad", "father", "brother", "son", "groom",
}


_COLOUR_WORDS = {
    "white", "black", "red", "blue", "green", "pink", "yellow", "maroon", "grey", "gray", "gold",
    "silver", "brown", "navy", "purple", "orange", "beige", "cream", "ivory", "teal", "mint",
    "multicolor", "multicolour", "multicolored", "multicoloured", "rainbow", "aurora",
    "charcoal", "camel", "tan", "khaki", "olive", "burgundy", "mustard", "rust",
}
# a material asked for must be what the listing is made of, and these words
# mean it isn't. Live: "black leather jacket" came back with a parachute jacket.
_MATERIALS: dict[str, tuple[set[str], set[str]]] = {
    "leather": ({"leather", "pu", "faux", "vegan", "nappa", "lambskin", "sheepskin", "cowhide"}, {"parachute", "nylon", "puffer", "windbreaker", "fleece", "denim", "wool"}),
    "suede": ({"suede"}, {"parachute", "nylon", "puffer", "denim"}),
    "denim": ({"denim", "jean", "jeans"}, {"leather", "parachute"}),
    "wool": ({"wool", "woolen", "woollen", "cashmere", "merino", "tweed"}, {"parachute", "nylon", "leather", "puffer"}),
    "woolen": ({"wool", "woolen", "woollen", "cashmere", "merino", "tweed"}, {"parachute", "nylon", "leather", "puffer"}),
    "cashmere": ({"cashmere"}, {"parachute", "nylon"}),
    "silk": ({"silk", "silky"}, set()),
    "satin": ({"satin"}, set()),
    "velvet": ({"velvet"}, set()),
    "linen": ({"linen"}, set()),
    "cotton": ({"cotton"}, set()),
    "chiffon": ({"chiffon"}, set()),
    "corduroy": ({"corduroy"}, set()),
    "tweed": ({"tweed"}, set()),
    "fleece": ({"fleece"}, set()),
    "parachute": ({"parachute"}, {"leather"}),
    "puffer": ({"puffer", "padded", "quilted", "down"}, {"leather"}),
}
_HIGH_NECK = {"turtleneck", "turtlenecks", "rollneck", "polo", "highneck"}
_NO_ACCESSORIES = re.compile(r"\b(no|without|skip)\s+(any\s+)?(accessor\w*|jewell?ery|extras?)\b", re.I)
# words that mean one listing is a whole set, and the pieces such a set includes
_SET_LISTING = re.compile(r"(\d+\s*(piece|pc|pcs)\b|\bsuit\b|\bco-?ord\b|\boutfit\b)")
_SET_COMPONENTS = {
    "dupatta", "dupattas", "stole", "shawl", "trouser", "trousers", "pant", "pants", "palazzo",
    "palazzos", "shalwar", "salwar", "kameez", "kurta", "kurti", "top", "bottom",
}


# A search for just a dupatta must not bring back a whole outfit. Live:
# "with matching dupatta" picked a "Lehenga Choli with Dupatta" set, and the
# look had two dresses.
_PIECE_ONLY = {
    "dupatta", "dupattas", "stole", "stoles", "shawl", "shawls",
    # a bottom on its own: live, "cream shalwar" under a sherwani picked a
    # whole black "Shalwar Kameez" suit, kurta and all
    "shalwar", "salwar", "trouser", "trousers", "pant", "pants", "palazzo", "palazzos", "churidar", "pajama", "pyjama",
}
_WHOLE_OUTFIT = {
    "lehenga", "lehnga", "choli", "suit", "kameez", "saree", "sari", "gown", "dress", "anarkali",
    "sharara", "gharara", "frock", "maxi", "kurta", "kurtas", "kurti", "kurtis", "tunic", "sherwani",
}


_BOTTOMS = {"shalwar", "salwar", "trouser", "trousers", "pant", "pants", "palazzo", "palazzos", "churidar", "pajama", "pyjama"}
# what makes a bottom's listing a whole set: it names a top too ("Men's Suit
# Trousers" are still just trousers)
_TOPS = {"kameez", "kurta", "kurtas", "kurti", "kurtis", "tunic", "sherwani", "choli", "shirt", "shirts", "top", "tops"}


def _whole_outfit_for_a_piece(term: str, name: str) -> bool:
    asked = _words(term) & _ITEM_CATEGORY_WORDS
    if not asked or not asked <= _PIECE_ONLY:
        return False
    named = _words(name)
    if asked <= _BOTTOMS:
        return bool(named & _TOPS)
    return bool(named & _WHOLE_OUTFIT)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


# Live, a bridal look came back looking like a costume: "gold maang tikka"
# found a belly-dance coin head chain, "nose ring" an 8-pack of different
# nose rings, "gold bridal necklace" a rainbow crystal set. Each listing must
# now actually be the item asked for, and be one product, not a costume.
_ITEM_FOLD = {
    "wristwatch": "watch", "wristwatches": "watch", "smartwatch": "watch", "watches": "watch",
    "jutti": "khussa", "juttis": "khussa", "mojari": "khussa", "mojaris": "khussa", "khussas": "khussa",
    "jhumka": "earring", "jhumkas": "earring", "jhumki": "earring", "earrings": "earring",
    "lehnga": "lehenga", "lehengas": "lehenga", "sari": "saree", "sarees": "saree",
    "clutch": "bag", "clutches": "bag", "purse": "bag", "handbag": "bag", "handbags": "bag", "bags": "bag",
    "choker": "necklace", "necklaces": "necklace", "haar": "necklace",
    "bracelet": "bangle", "bracelets": "bangle", "bangles": "bangle", "kada": "bangle",
    # what shops also call the same garment
    "trousers": "trouser", "pant": "trouser", "pants": "trouser", "slacks": "trouser", "chinos": "trouser",
    "jumper": "sweater", "jumpers": "sweater", "pullover": "sweater", "pullovers": "sweater",
    "overcoat": "coat", "overcoats": "coat", "peacoat": "coat", "peacoats": "coat", "trench": "coat",
    "trainers": "sneaker", "trainer": "sneaker", "dresses": "dress", "scarves": "scarf",
}
# a word in the request that narrows the item: a "nose ring" is not any ring
_QUALIFIERS = {"nose": {"nose", "nath", "nathni", "septum"}}
# listings that carry the item's name but are a different piece. Live:
# "gold maang tikka" picked a silver "Hairband Maang Tikka Headband", and it
# came out as a crown.
_LOOKALIKES = {
    "tikka": re.compile(r"\b(head ?bands?|hair ?bands?|tiaras?|crowns?|head ?chains?|headpieces?|matha ?patti|sheeshpatti)\b"),
}


def _fit(term: str, name: str) -> int:
    """How well a listing fits the ask, for ordering only: the colour asked
    for named in the title first, a look-alike piece last. Nothing is dropped,
    so an item never disappears for want of a perfect listing."""
    words = _words(name)
    asked_colours = _words(term) & _COLOUR_WORDS
    score = 2 if asked_colours & words else 0
    for item, lookalike in _LOOKALIKES.items():
        if item in _words(term) and lookalike.search(name.lower()) and not lookalike.search(term.lower()):
            score -= 3
    # one piece asked for, a set of several offered: live, "gold maang tikka"
    # picked a "Choker Necklace Earrings Maang Tikka Bridal Jewelry Set"
    asked_pieces, named_pieces = _jewel_pieces(term), _jewel_pieces(name)
    if len(asked_pieces) == 1 and len(named_pieces) >= 2 and "set" not in _words(term):
        score -= 2
    return score
_COSTUME = re.compile(
    r"\b(costume|cosplay|halloween|belly ?danc\w*|fancy dress|toys?|dolls?|kids?|children|child|toddlers?|infants?)\b"
)
# two or more of something; "1PC" / "1 Pair" is how AliExpress titles a single
# item, and counting it as a pack dropped their single nose rings and tikkas
_MULTI_PACK = re.compile(
    r"\b([2-9]|\d{2,})\s*-?\s*(pcs|pc|pieces|pairs|pack)\b|\b(set|pack|lot) of ([2-9]|\d{2,})\b"
)
_ONE_PIECE_ITEMS = {
    "watch", "bag", "khussa", "earring", "necklace", "bangle", "ring", "rings", "tikka", "pendant", "anklet",
    "anklets", "payal", "shoe", "shoes", "heels", "heel", "sandals", "sandal", "flats", "flat", "chappal", "chappals",
    "sunglasses", "anklet",
}


def _fold(word: str) -> str:
    word = _ITEM_FOLD.get(word, word)
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]  # jackets, boots, jeans: one word for one and many
    return _ITEM_FOLD.get(word, word)


def _is_the_item(term: str, name: str) -> bool:
    """The listing names the item the shopper asked for (any of its item
    words, folded so a "jutti" counts as a "khussa"), and any qualifier."""
    term_words, name_words = _words(term), _words(name)
    asked = {_fold(w) for w in term_words & _ITEM_CATEGORY_WORDS}
    have = {_fold(w) for w in name_words}
    # "high-neck shirt": shops sell these as turtlenecks, of any upper garment
    if {"high", "neck"} <= term_words:
        if not (name_words & _HIGH_NECK or {"high", "neck"} <= name_words or {"mock", "neck"} <= name_words or {"roll", "neck"} <= name_words):
            return False
    elif asked and not asked & have:
        return False
    elif not asked:
        # a product type we have no word for ("shacket"): the listing must name
        # something of what was asked, beyond who it's for and its colour
        wanted = {_fold(w) for w in term_words - _COLOUR_WORDS - _WOMEN_WORDS - _MEN_WORDS - _TERM_STOPWORDS}
        if wanted and not wanted & have:
            return False
    if not _right_material(term_words, name_words):
        return False
    return all(name_words & alts for q, alts in _QUALIFIERS.items() if q in term_words)


def _right_material(term_words: set[str], name_words: set[str]) -> bool:
    for material, (accepted, wrong) in _MATERIALS.items():
        if material in term_words and (not name_words & accepted or name_words & wrong - term_words):
            return False
    return True


def _unsuitable(term: str, name: str, prompt: str) -> bool:
    """A costume the shopper didn't ask for, or a multi-pack offered for an
    item worn singly: its photo shows many different designs, so the try-on
    can only guess which one was meant."""
    lowered = name.lower()
    if _COSTUME.search(lowered) and not _COSTUME.search(prompt.lower()):
        return True
    asked = _words(term) & _ITEM_CATEGORY_WORDS
    if asked & _SEPARATES and _SET_OFFER.search(lowered) and not _SET_OFFER.search(prompt.lower()):
        return True
    one_piece = {_fold(w) for w in asked} & _ONE_PIECE_ITEMS
    return bool(one_piece) and bool(_MULTI_PACK.search(lowered))


def _colour_conflicts(prompt: str, name: str) -> bool:
    """True when the listing names a colour the shopper didn't ask for and
    names none they did. A listing that names no colour at all is kept."""
    wanted = _words(prompt) & _COLOUR_WORDS
    named = _words(name) & _COLOUR_WORDS
    return bool(wanted) and bool(named) and not (named & wanted)


def _drop_redundant_candidates(cands: list["_Candidate"]) -> list["_Candidate"]:
    """A whole set and its own included piece are never both picked as
    separate items: a "3 piece suit" plus its "dupatta" is the same product
    twice. Nothing else is dropped, so no real product is skipped silently."""
    kept = list(cands)
    set_words = [_words(c.result.raw.name) for c in kept if _SET_LISTING.search(c.result.raw.name.lower())]
    result: list[_Candidate] = []
    for c in kept:
        words = _words(c.result.raw.name)
        is_component = bool(words & _SET_COMPONENTS)
        if is_component and any(
            (words & _SET_COMPONENTS) <= parent and words != parent for parent in set_words
        ):
            continue
        result.append(c)
    return _drop_overlapping_jewellery_sets(result)


# jewellery pieces as they appear in listing titles, folded to one name each
_JEWEL_PIECES = {
    "earring": "earring", "earrings": "earring", "jhumka": "earring", "jhumkas": "earring", "jhumki": "earring",
    "tikka": "tikka", "maang": "tikka", "necklace": "necklace", "choker": "necklace", "haar": "necklace",
    "bangle": "bangle", "bangles": "bangle", "bracelet": "bangle", "kada": "bangle",
    "ring": "ring", "rings": "ring", "nath": "nose", "nose": "nose",
}


def _jewel_pieces(name: str) -> set[str]:
    return {_JEWEL_PIECES[w] for w in _words(name) if w in _JEWEL_PIECES}


def _drop_overlapping_jewellery_sets(cands: list["_Candidate"]) -> list["_Candidate"]:
    """A jewellery SET that contains a piece also picked on its own is dropped,
    keeping the separately chosen piece. Live: a "choker necklace set earrings
    maang tikka" listing was picked alongside separate jhumka earrings and a
    separate choker, and the image came back with the two earring designs
    blended and an extra necklace. A set that overlaps nothing is kept."""
    singles = [_jewel_pieces(c.result.raw.name) for c in cands]
    is_set = [("set" in _words(c.result.raw.name) and len(p) >= 2) for c, p in zip(cands, singles)]
    kept = []
    for i, c in enumerate(cands):
        if is_set[i]:
            others = set().union(*(p for j, p in enumerate(singles) if j != i and not is_set[j]))
            if singles[i] & others:
                continue
        kept.append(c)
    return kept


def _gender_in_prompt(prompt: str) -> str | None:
    words = re.findall(r"[a-z']+", prompt.lower())
    if any(w in _WOMEN_WORDS for w in words):
        return "women"
    return "men" if any(w in _MEN_WORDS for w in words) else None


# "Pink bridal look", "Eid outfit": a shopper can name the occasion instead of
# every item, and gets the whole look. {c} is the colour they asked for (or
# nothing), {m} the metal (gold unless they said silver). Most important
# first: when Admin allows fewer items per look, the first ones are kept.
_READY_LOOKS: dict[str, dict[str, list[str]]] = {
    "bridal": {
        "women": ["{c} bridal lehenga", "{c} dupatta", "{m} maang tikka", "{m} jhumka earrings", "{m} bridal necklace set",
                  "{m} bangles", "{m} rings", "{m} wristwatch", "{c} khussa", "{m} clutch bag"],
        "men": ["{c} sherwani", "khussa", "{m} wristwatch", "shawl"],
    },
    "mehndi": {
        "women": ["{c} lehenga", "{c} dupatta", "{m} jhumka earrings", "{m} bangles", "{m} maang tikka", "{c} khussa",
                  "{m} clutch bag"],
        "men": ["{c} kurta shalwar", "waistcoat", "khussa", "{m} wristwatch"],
    },
    "eid": {
        "women": ["{c} shalwar kameez", "{c} dupatta", "{m} jhumka earrings", "{m} bangles", "khussa", "clutch bag"],
        "men": ["{c} shalwar kameez", "waistcoat", "peshawari chappal", "{m} wristwatch"],
    },
    "party": {
        "women": ["{c} dress", "heels", "clutch bag", "{m} earrings", "{m} necklace", "{m} bracelet"],
        "men": ["{c} blazer", "shirt", "trousers", "loafers", "{m} wristwatch"],
    },
    "office": {
        "women": ["{c} blouse", "trousers", "heels", "handbag", "{m} wristwatch"],
        "men": ["{c} shirt", "trousers", "blazer", "loafers", "{m} wristwatch"],
    },
    "casual": {
        "women": ["{c} top", "jeans", "sneakers", "handbag", "sunglasses"],
        "men": ["{c} t-shirt", "jeans", "sneakers", "{m} wristwatch", "sunglasses"],
    },
}
# the words shoppers use for each occasion
_OCCASION_WORDS = {
    "bridal": "bridal", "bride": "bridal", "wedding": "bridal", "barat": "bridal", "baraat": "bridal",
    "dulhan": "bridal", "shaadi": "bridal", "shadi": "bridal", "nikah": "bridal", "walima": "bridal",
    "groom": "bridal", "dulha": "bridal",
    "mehndi": "mehndi", "mehendi": "mehndi", "mayun": "mehndi", "haldi": "mehndi",
    "eid": "eid", "festive": "eid",
    "party": "party", "dinner": "party",
    "office": "office", "interview": "office",
    "casual": "casual", "everyday": "casual", "weekend": "casual", "college": "casual", "university": "casual",
}
_METALS = {"gold", "golden", "silver"}
_LOOK_WORDS = {"look", "looks", "outfit", "outfits", "complete", "full", "everything"}


def _ready_look(prompt: str, gender: str | None) -> str | None:
    """The item list behind a short ask like "pink bridal look", or None.
    Only when no item is named, or one item plus "look"/"outfit" ("red bridal
    lehenga look"): "party dress" still means just a dress."""
    words = re.findall(r"[a-z']+", prompt.lower())
    occasion = next((_OCCASION_WORDS[w] for w in words if w in _OCCASION_WORDS), None)
    if occasion is None:
        return None
    named = len(_extract_search_terms(prompt, gender, ready=False))
    if named >= 2 or (named == 1 and not _LOOK_WORDS & set(words)):
        return None
    who = _gender_in_prompt(prompt) or (gender if gender in ("men", "women") else None)
    if who is None:
        who = "men" if any(w in ("groom", "dulha") for w in words) else "women"
    colour = next((w for w in words if w in _COLOUR_WORDS and w not in _METALS), "")
    metal = "silver" if "silver" in words else "gold"
    items = [i.format(c=colour, m=metal).strip() for i in _READY_LOOKS[occasion][who]]
    return ", ".join(" ".join(i.split()) for i in items) + f" for {who}"


def _extract_search_terms(prompt: str, gender: str | None = None, *, ready: bool = True) -> list[str]:
    """Finds each recognized item in the prompt, one short query per item,
    in the order they appear, deduplicated:
    - item words written back to back ("shalwar kameez", "khussa shoes")
      stay one item, but a comma splits them ("jacket, jeans")
    - up to two describing words right before it are kept ("leather
      jacket", "white lawn shalwar kameez")
    - "for women" / "men's" anywhere in the prompt — or, failing that, the
      shopper's own saved gender — is added to every query, since eBay
      otherwise mixes in the other gender's listings.
    - a short ask naming an occasion ("pink bridal look") becomes that
      occasion's whole look (_ready_look)"""
    asked_prompt = prompt
    expanded = False
    if ready and (whole_look := _ready_look(prompt, gender)):
        prompt = whole_look
        expanded = True
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[a-z']+(?:-[a-z']+)*", prompt.lower())]
    words = [t[0] for t in tokens]
    gender = _gender_in_prompt(prompt) or (gender if gender in ("men", "women") else "")

    def joined(a: int, b: int) -> bool:
        # the two tokens are separated by plain spaces only — no comma etc.
        return prompt[tokens[a][2] : tokens[b][1]].strip() == ""

    def _negated(i: int) -> bool:
        # "no separate dupatta", "without a dupatta": a "no"/"not"/"without"
        # up to three words before the item, with no comma between, means
        # the shopper does NOT want it. Live: "No second dress and no
        # separate dupatta" fetched a bandhani dupatta and put it on her.
        k = i
        while k > 0 and i - k < 3 and joined(k - 1, k):
            k -= 1
            if words[k] in _NEGATIONS:
                return True
        return False

    terms: list[str] = []
    seen: set[str] = set()
    i = 0
    while i < len(words):
        if words[i] not in _ITEM_CATEGORY_WORDS:
            i += 1
            continue
        j = i
        while j + 1 < len(words) and words[j + 1] in _ITEM_CATEGORY_WORDS and joined(j, j + 1):
            j += 1
        if _negated(i):
            i = j + 1
            continue
        parts = words[i : j + 1]
        specific = _GENERIC_UMBRELLA_WORDS.get(parts[0]) if len(parts) == 1 else None
        if specific is not None and any(w in specific for w in words):
            # a bare "jewelry" lead-in to specific items named elsewhere in
            # the same prompt — not a request in its own right
            i = j + 1
            continue
        # up to two describing words right before it ("white lawn")
        k = i
        while (
            k > 0
            and i - k < 2
            and joined(k - 1, k)
            and words[k - 1] not in _TERM_STOPWORDS
            and words[k - 1] not in _ITEM_CATEGORY_WORDS
            and words[k - 1] not in _WOMEN_WORDS
            and words[k - 1] not in _MEN_WORDS
        ):
            k -= 1
        if i - k == 2 and joined(k - 1, k) and words[k - 1] in _LEAD_COLOURS:
            k -= 1
        parts = [*words[k:i], *parts]
        if gender:
            parts = [gender, *parts]
        # "cable-knit" is searched as "cable knit" ("t-shirt" stays, shops spell it so)
        term = " ".join(p if p in _ITEM_CATEGORY_WORDS else p.replace("-", " ") for p in parts)
        if term not in seen:
            seen.add(term)
            terms.append(term)
        i = j + 1
    if expanded and _NO_ACCESSORIES.search(asked_prompt):
        # "party look, no accessories": the ready-made look's clothes only
        terms = [t for t in terms if slot_for(t) not in (OutfitSlot.ACCESSORY, OutfitSlot.WATCH, OutfitSlot.BAG)]
    return terms


def _colour_scope(term: str, prompt: str) -> str:
    """Whose colour applies to this item: its own ("cream sweater"), or the
    only colour in the ask ("all black: jacket, jeans"). With several colours
    in the ask, an item without one of its own isn't held to any."""
    if _words(term) & _COLOUR_WORDS:
        return term
    return prompt if len(_words(prompt) & _COLOUR_WORDS) == 1 else ""


def _core_term(term: str) -> str | None:
    """`term` with only who it's for, colour, material and the item left, for a
    second search: "men charcoal slim trousers" -> "men charcoal trousers"."""
    keep = [
        w for w in term.split()
        if w in _ITEM_CATEGORY_WORDS or w in _COLOUR_WORDS or w in _MATERIALS or w in _WOMEN_WORDS or w in _MEN_WORDS
    ]
    core = " ".join(keep)
    return core if core and core != term else None


def _good_results(term: str, results: list, prompt: str, gender: str | None) -> list:
    """Only listings that really are what was asked: the item, its material and
    colour, for the right person. Nothing else stands in: an item with no
    match is reported to the shopper, not silently replaced."""
    scope = _colour_scope(term, prompt)
    return [
        r
        for r in results
        if not _unsuitable(term, r.raw.name, prompt)
        and _is_the_item(term, r.raw.name)
        and fits_audience(r.raw.name, gender, getattr(r.raw, "gender", None))
        and not _colour_conflicts(scope, f"{r.raw.name} {r.raw.color or ''}")
        and not _whole_outfit_for_a_piece(term, r.raw.name)
    ]


def _not_found_note(missing: list[str]) -> str:
    """Says plainly what couldn't be found, without the search's "men"/"women"."""
    if not missing:
        return ""
    plain = [" ".join(w for w in t.split() if w not in _WOMEN_WORDS and w not in _MEN_WORDS) for t in missing]
    return (
        f" We couldn't find a good match for: {', '.join(plain)}, so nothing else was put in its place. "
        "Try other words, or a different colour."
    )


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


def _narrow_term(term: str) -> str | None:
    """`term` with its leading descriptor word(s) dropped, keeping only
    the gender word (if any) and the item-category words at the end —
    the same word a shopper typed can be one a retailer's own listings
    never use. Live: "karahi heels shoes" (karahi is a specific
    embroidery technique) found nothing at all; "heels shoes" alone
    found ten real listings. None if there's no descriptor left to drop.
    """
    words = term.split()
    core_start = len(words)
    for idx in range(len(words) - 1, -1, -1):
        if words[idx] in _ITEM_CATEGORY_WORDS:
            core_start = idx
        else:
            break
    core = words[core_start:]
    if not core:
        return None
    kept_gender = [w for w in words[:core_start] if w in _WOMEN_WORDS or w in _MEN_WORDS]
    narrowed = " ".join([*kept_gender, *core])
    return narrowed if narrowed != term else None


async def _fetch_candidates(
    req: StylistAskRequest, profile: TasteProfile | None, gender: str | None = None
) -> list[_Candidate]:
    return _trim_pool(await _fetch_pool(req, profile, gender))


async def _read_the_ask(prompt: str, gender: str | None) -> tuple[list[str], str | None, bool]:
    """(the searches, who for, is it about fashion) from whatever the shopper
    typed. The ready-made occasion looks keep their tried lists; otherwise the
    AI reads it (any language, spelling mistakes); word matching if it can't."""
    if not _ready_look(prompt, gender):
        read = await read_prompt(prompt)
        if read is not None:
            if not read["fashion"] and not read["items"]:
                return [], gender, False
            if read["items"]:
                if not _gender_in_prompt(prompt) and read["for"]:
                    gender = read["for"]
                who = gender if gender in ("men", "women") else ""
                return [f"{who} {item}".strip() for item in read["items"]], gender, True
    return _extract_search_terms(prompt, gender), gender, True


async def _fetch_pool(
    req: StylistAskRequest, profile: TasteProfile | None, gender: str | None = None, named: list[str] | None = None
) -> list[_Candidate]:
    """Every candidate is fetched fresh from retailer APIs for this exact
    prompt — nothing here is a pre-synced local row. Budget filtering and
    personalized re-ranking both happen over that live pool in Python
    rather than in SQL, since there's no local table to filter/sort with a
    WHERE/ORDER BY. Each candidate keeps the term that found it, so
    ask_stylist can offer real alternatives at other price points for
    whichever ones the LLM ends up choosing."""
    # only the first max_items things named are searched: a look applies at
    # most that many products, and ask_stylist tells the shopper which were left out
    terms = (named if named is not None else _extract_search_terms(req.prompt, gender))[: req.max_items]
    if terms:
        # One short search per distinct item mentioned (see
        # _extract_search_terms) — a multi-item outfit prompt otherwise
        # returns zero results, since no single real listing's title
        # contains every item type at once.
        per_term_limit = max(_PER_ITEM_RESULTS, _LIVE_FETCH_POOL_SIZE // len(terms))
        term_results = list(await asyncio.gather(*(live_search(t, limit=per_term_limit) for t in terms)))

        # A term that found nothing doesn't mean the item isn't out
        # there — it can mean the shopper's own word for it isn't the
        # retailer's. Retried once, narrowed, rather than silently
        # dropping that item from the outfit: a shopper who asked for
        # five things and got four with no explanation has no way to
        # know one was ever considered.
        # The same when nothing it found is really the item. The second search
        # is wider; the listings still have to pass for the item as asked.
        retries = {
            i: n
            for i, t in enumerate(terms)
            if not _good_results(t, term_results[i], req.prompt, gender) and (n := _core_term(t) or _narrow_term(t))
        }
        if retries:
            retried = await asyncio.gather(*(live_search(n, limit=per_term_limit) for n in retries.values()))
            for i, results in zip(retries.keys(), retried):
                term_results[i] = list(term_results[i]) + list(results)

        pool: list[_Candidate] = []
        seen_ids: set[tuple[str, str]] = set()
        for n, (term, results) in enumerate(zip(terms, term_results)):
            # only listings that really are the item, for the right person
            exact = _good_results(term, results, req.prompt, gender)
            # equally good listings: a TryOnU store's first (recommended to shoppers)
            results = sorted(exact, key=lambda r: (-_fit(term, r.raw.name), store_rank(r)))
            # then the shops take turns, a different one first for each item
            results = _mix_shops(results, term, n)
            # among store products: the best match for the words asked, then the bigger plan
            results = _stores_by_match(results, term)
            for r in results:
                key = (r.provider.slug, r.raw.retailer_product_id)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                pool.append(_Candidate(result=r, term=term))
    else:
        # No recognized item word (e.g. a bare brand/style ask) — fall
        # back to the prompt as a single query, same as before.
        loose = await live_search(req.prompt, limit=_LIVE_FETCH_POOL_SIZE)
        pool = [
            _Candidate(result=r, term=req.prompt)
            for r in loose
            if fits_audience(r.raw.name, gender, getattr(r.raw, "gender", None))
        ]

    if req.budget_min_cents is not None:
        pool = [c for c in pool if c.result.raw.price_cents >= req.budget_min_cents]
    if req.budget_max_cents is not None:
        pool = [c for c in pool if c.result.raw.price_cents <= req.budget_max_cents]

    if profile and profile.has_signal:
        # affinity_score only reads .color/.brand/.style_tags — present on
        # RawProduct with the same names, so this works unmodified even
        # though its signature says Product.
        pool.sort(key=lambda c: (affinity_score(c.result.raw, profile), -store_rank(c.result)), reverse=True)  # type: ignore[arg-type]
    return pool


def _mix_shops(results: list[LiveSearchResult], term: str, start: int) -> list[LiveSearchResult]:
    """Equally good listings from different shops take turns, and each item
    starts with a different shop. eBay answers first and its titles carry every
    keyword, so live a 10-item bridal look came back eBay-only although
    AliExpress had matching jhumkas, necklaces, watches and clutches. A better
    match still comes first, and TryOnU stores keep their place in front."""
    out: list[LiveSearchResult] = []
    i = 0
    while i < len(results):
        fit = _fit(term, results[i].raw.name)
        j = i
        while j < len(results) and _fit(term, results[j].raw.name) == fit:
            j += 1
        group = results[i:j]
        by_shop: dict[str, list[LiveSearchResult]] = {}
        for r in group:
            if not _from_store(r):
                by_shop.setdefault(r.provider.slug, []).append(r)
        queues = list(by_shop.values())
        if queues:
            k = start % len(queues)
            queues = queues[k:] + queues[:k]
        out.extend(r for r in group if _from_store(r))
        while any(queues):
            for q in queues:
                if q:
                    out.append(q.pop(0))
        i = j
    return out


def _trim_pool(pool: list[_Candidate]) -> list[_Candidate]:
    """The shortlist the model chooses from. Alternatives come from the
    whole pool, so trimming here never hides an option from the shopper."""
    # trim without dropping any item entirely: take from each item's
    # (already taste-ranked) results in turn
    by_term: dict[str, list[_Candidate]] = {}
    for c in pool:
        by_term.setdefault(c.term, []).append(c)
    trimmed: list[_Candidate] = []
    queues = list(by_term.values())
    while len(trimmed) < _CANDIDATE_POOL_SIZE and any(queues):
        for q in queues:
            if q and len(trimmed) < _CANDIDATE_POOL_SIZE:
                trimmed.append(q.pop(0))
    return trimmed


_MAX_ALTERNATIVES = _PER_ITEM_RESULTS


def _one_of_each_item(chosen: list[_Candidate], pool: list[_Candidate], max_items: int) -> list[_Candidate]:
    """When the ask names several items ("shalwar kameez with bangles and
    khussa"), the outfit gets one of each — the model's pick for that item
    where it made one, else the best-ranked result for it (the pool is
    already sorted by taste). Without this a model could return six pairs
    of khussa and no kameez; the other options for each item are still
    offered as alternatives. A single-item ask keeps every pick."""
    terms = list(dict.fromkeys(c.term for c in pool))
    if len(terms) < 2:
        return chosen
    by_term: dict[str, _Candidate] = {}
    for c in chosen:
        by_term.setdefault(c.term, c)
    for c in pool:
        by_term.setdefault(c.term, c)
    return [by_term[t] for t in terms if t in by_term][:max_items]


def _alternatives_for(chosen: _Candidate, pool: list[_Candidate], picked_ids: set[str]) -> list[LiveSearchResult]:
    """Other real, live-fetched results for the same item type — spanning
    low to high price so "show me other options, cheap and expensive" is
    real data, not invented. Excludes everything already in the pick: two
    outfit items from the same search would otherwise list each other, and
    swapping one in would put the same product in the outfit twice.

    Keeps the whole LiveSearchResult, not just its RawProduct: the caller
    needs to know which retailer actually found each one — AliExpress
    alternatives were being shown labelled "eBay" because only the raw
    listing survived past this point, from back when eBay really was the
    only retailer with a live search."""
    same_term = [
        c.result
        for c in pool
        if c.term == chosen.term and c.result.raw.retailer_product_id not in picked_ids
    ]
    if not same_term:
        return []
    # TryOnU stores' options first (recommended), then the rest across the price range
    stores = sorted(
        (r for r in same_term if _from_store(r)),
        key=lambda result: (-_match(chosen.term, result.raw.name), store_rank(result), result.raw.price_cents),
    )
    stores = stores[:_MAX_ALTERNATIVES]
    others = sorted((r for r in same_term if not _from_store(r)), key=lambda result: result.raw.price_cents)
    room = _MAX_ALTERNATIVES - len(stores)
    if room <= 0 or len(others) <= room:
        return stores + others[: max(room, 0)]
    if room == 1:
        return stores + [others[len(others) // 2]]
    # spread across the price range rather than just "the next 3 cheapest"
    step = (len(others) - 1) / (room - 1)
    return stores + [others[round(i * step)] for i in range(room)]


def _prefer_store_items(chosen: list[_Candidate], pool: list[_Candidate]) -> tuple[list[_Candidate], bool]:
    """Each pick from elsewhere is replaced by a TryOnU store product for the
    same item when one fits at least as well (same item, colour named if the
    shopper asked for one) - featured and local store products first. The
    pool has already dropped wrong items, costumes, other genders and
    colour clashes, so a store product left in it is a real match."""
    used = {c.result.raw.retailer_product_id for c in chosen}
    out: list[_Candidate] = []
    swapped = False
    for c in chosen:
        if _from_store(c.result):
            out.append(c)
            continue
        fit = _match(c.term, c.result.raw.name)
        options = [
            p
            for p in pool
            if p.term == c.term
            and _from_store(p.result)
            and p.result.raw.retailer_product_id not in used
            and _match(p.term, p.result.raw.name) >= fit
        ]
        if options:
            # the best-matching store product; among equals, the bigger plan
            best = min(options, key=lambda p: (-_match(p.term, p.result.raw.name), store_rank(p.result)))
            used.add(best.result.raw.retailer_product_id)
            out.append(best)
            swapped = True
        else:
            out.append(c)
    return out, swapped


def _match(term: str, name: str) -> int:
    """How well a listing matches an item asked for: the colour asked for and
    no look-alike first (_fit), then how many of the shopper's words it has."""
    return _fit(term, name) * 100 + match_score(term, name)


def _stores_by_match(results: list[LiveSearchResult], term: str) -> list[LiveSearchResult]:
    """The store products, in their places, re-ordered: best match first, then the bigger plan."""
    slots = [i for i, r in enumerate(results) if _from_store(r)]
    ordered = sorted((results[i] for i in slots), key=lambda r: (-_match(term, r.raw.name), store_rank(r)))
    out = list(results)
    for i, r in zip(slots, ordered):
        out[i] = r
    return out


def _shop_of(result: LiveSearchResult) -> str:
    return result.raw.merchant_name or getattr(result.provider, "display_name", None) or result.provider.slug


def _from_store(result: LiveSearchResult) -> bool:
    """Sold by a company store on TryOnU (recommended to shoppers)."""
    return result.provider.slug == "stores"


def _slot_for(raw: RawProduct) -> OutfitSlot:
    return slot_for(raw.name, raw.category_slug)


async def _shopper_gender(db: AsyncSession, user_id: str, prompt: str, chosen: str | None = None) -> str | None:
    """Who the look is for: what the prompt says ("a kurti for my wife"), else
    what they chose on the page (men, women, unisex), else their saved gender,
    else the audience they picked most of in onboarding. Nothing forces them
    to state a gender."""
    said = _gender_in_prompt(prompt)
    if said:
        return said
    if chosen:
        return chosen
    pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if pref is None:
        return None
    audience = audience_of(pref.gender.value if pref.gender else None, pref.preferred_categories or [])
    return audience if audience in ("men", "women") else None


def _left_out_note(left_out: list[str], max_items: int, gender: str | None) -> str:
    """Said plainly, never dropped silently: which named items aren't in this look."""
    if not left_out:
        return ""
    names = [t.removeprefix(f"{gender} ") if gender else t for t in left_out]
    return (
        f" A look can have up to {max_items} products, so I used the first {max_items} you named. "
        f"Not included: {', '.join(names)}. Ask for them in a separate look."
    )


async def ask_stylist(
    db: AsyncSession, *, user_id: str, req: StylistAskRequest
) -> tuple[StylistRequest, dict[str, tuple[str, list[LiveSearchResult]]]]:
    # the most products one look applies is the server's setting (Admin), not the page's
    look_limit = max(1, get_settings().TRYON_DIRECT_MAX_PRODUCTS)
    if req.max_items > look_limit:
        req = req.model_copy(update={"max_items": look_limit})
    wardrobe_item: WardrobeItem | None = None
    if req.wardrobe_item_id:
        wardrobe_item = await _load_owned_wardrobe_item(db, user_id, req.wardrobe_item_id)

    # An explicit "build around this" anchor takes priority over general
    # taste — the user asked for something specific, not just a good match.
    profile = _wardrobe_anchor_profile(wardrobe_item) if wardrobe_item else await build_taste_profile(db, user_id)
    gender = await _shopper_gender(db, user_id, req.prompt, req.audience)
    named_terms, gender, about_fashion = await _read_the_ask(req.prompt, gender)
    if not about_fashion:
        stylist_request = StylistRequest(
            user_id=user_id,
            prompt=req.prompt,
            occasion=req.occasion,
            budget_min_cents=req.budget_min_cents,
            budget_max_cents=req.budget_max_cents,
            style=req.style,
            response_summary="Tell us what you'd like to wear, for example: black leather jacket, white shirt and jeans.",
            recommended_product_ids=[],
        )
        db.add(stylist_request)
        await db.commit()
        await db.refresh(stylist_request)
        return stylist_request, {}
    pool = await _fetch_pool(req, profile, gender, named_terms)
    left_out = named_terms[req.max_items :]
    candidates = _trim_pool(pool)
    llm_candidates = [
        StylistCandidate(
            index=i,
            name=c.result.raw.name,
            brand=c.result.raw.brand,
            category=c.result.raw.category_slug,
            color=c.result.raw.color,
            price_cents=c.result.raw.price_cents,
            style_tags=c.result.raw.style_tags or [],
            local=bool(c.result.raw.origin_country) and c.result.raw.origin_country == current_country(),
            partner=_from_store(c.result),
            featured=_from_store(c.result) and c.result.raw.featured,
        )
        for i, c in enumerate(candidates)
    ]

    provider = get_stylist_provider()
    searched = named_terms[: req.max_items]
    query = StylistQuery(
        # items past the limit weren't searched: without this the model told
        # shoppers "no suitable bangles or clutch are available"
        prompt=req.prompt
        + (
            f"\n(These items were searched this time: {', '.join(searched)}. Say nothing about any"
            " other item; the shopper is told about those separately.)"
            if left_out or _ready_look(req.prompt, gender)
            else ""
        ),
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
        # Also log it. This used to be recorded only in the ai_usage row,
        # so a shopper saw "the stylist is temporarily unavailable" while
        # the logs said nothing at all — the real cause (the OpenAI
        # account being out of credit) was invisible from the outside.
        logger.warning(
            "stylist_llm_failed",
            provider=provider.name,
            model=provider.model,
            error=error_message,
        )
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

    chosen = _one_of_each_item(
        [candidates[i] for i in recommendation.chosen_indexes if 0 <= i < len(candidates)], candidates, req.max_items
    )
    # One product for each thing named, never two of the same kind in one
    # picture: live, "black leather jacket" gave several jackets, and the image
    # blended them into one. The others stay as options under Change.
    if named_terms and len({c.term for c in pool}) == 1:
        chosen = chosen[:1] or pool[:1]
    chosen = _drop_redundant_candidates(chosen)
    # TryOnU stores first: a store product the stylist passed over for an
    # equally good one elsewhere takes that place in the look
    chosen, swapped = _prefer_store_items(chosen, pool)
    summary = recommendation.summary
    if swapped:
        # the stylist's words described what it picked; say plainly what the look now is
        summary = "Your look, with TryOnU store products first: " + "; ".join(
            f"{c.result.raw.name[:60]} from {_shop_of(c.result)}" for c in chosen
        ) + "."

    # The one point a live-searched candidate becomes a saved row — only
    # for what the LLM actually chose, never the rest of the pool it saw.
    chosen_products = [await persist_single_product(db, c.result.provider, c.result.raw) for c in chosen]

    # Real alternatives at other price points for each chosen item — from
    # results already fetched above, never an extra API call, never
    # invented. Keeps the search term alongside them so a client can
    # re-locate and persist one via POST /products/select-live if picked.
    picked_ids = {c.result.raw.retailer_product_id for c in chosen}
    alternatives_by_product_id = {
        product.id: (c.term, _alternatives_for(c, pool, picked_ids)) for product, c in zip(chosen_products, chosen)
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
        response_summary=summary
        + _not_found_note([t for t in named_terms[: req.max_items] if t not in {c.term for c in pool}])
        + _left_out_note(left_out, req.max_items, gender),
        recommended_product_ids=[p.id for p in chosen_products],
        recommended_outfit_id=outfit.id if outfit else None,
    )
    db.add(stylist_request)
    await db.commit()
    await db.refresh(stylist_request)
    from app.services.store_service import record_views

    await record_views(
        db,
        [c.result.raw.retailer_product_id for c in chosen if c.result.provider.slug == "stores"]
        + [
            r.raw.retailer_product_id
            for _, options in alternatives_by_product_id.values()
            for r in options
            if r.provider.slug == "stores"
        ],
    )
    return stylist_request, alternatives_by_product_id
