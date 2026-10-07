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
from app.core.logging import logger
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from app.models.preference import UserPreference
from app.models.stylist import StylistRequest
from app.models.wardrobe import WardrobeItem
from app.retailers.base import RawProduct
from app.schemas.stylist import StylistAskRequest
from app.services.gender_filter import keep_for_gender
from app.services.live_search_service import LiveSearchResult, live_search
from app.services.outfit_compatibility import score_outfit
from app.services.outfit_slots import slot_for
from app.services.personalization_service import TasteProfile, affinity_score, build_taste_profile
from app.services.product_ingestion_service import persist_single_product

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
}
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
    "women", "women's", "womens", "woman", "woman's", "ladies", "lady", "girls", "girl's", "female",
    "wife", "wife's", "girlfriend", "mum", "mom", "mother", "sister", "daughter", "bride",
}
_MEN_WORDS = {
    "men", "men's", "mens", "man", "man's", "gents", "boys", "boy's", "male",
    "husband", "husband's", "boyfriend", "dad", "father", "brother", "son", "groom",
}


_COLOUR_WORDS = {
    "white", "black", "red", "blue", "green", "pink", "yellow", "maroon", "grey", "gray", "gold",
    "silver", "brown", "navy", "purple", "orange", "beige", "cream", "ivory", "teal", "mint",
    "multicolor", "multicolour", "multicolored", "multicoloured", "rainbow", "aurora",
}
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
    "anklets", "payal", "shoe", "shoes", "heels", "sandals", "flats", "chappal", "chappals", "sunglasses",
}


def _fold(word: str) -> str:
    return _ITEM_FOLD.get(word, word)


def _is_the_item(term: str, name: str) -> bool:
    """The listing names the item the shopper asked for (any of its item
    words, folded so a "jutti" counts as a "khussa"), and any qualifier."""
    asked = {_fold(w) for w in _words(term) & _ITEM_CATEGORY_WORDS}
    have = {_fold(w) for w in _words(name)}
    if asked and not asked & have:
        return False
    return all(_words(name) & alts for q, alts in _QUALIFIERS.items() if q in _words(term))


def _unsuitable(term: str, name: str, prompt: str) -> bool:
    """A costume the shopper didn't ask for, or a multi-pack offered for an
    item worn singly: its photo shows many different designs, so the try-on
    can only guess which one was meant."""
    lowered = name.lower()
    if _COSTUME.search(lowered) and not _COSTUME.search(prompt.lower()):
        return True
    one_piece = {_fold(w) for w in _words(term) & _ITEM_CATEGORY_WORDS} & _ONE_PIECE_ITEMS
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


def _extract_search_terms(prompt: str, gender: str | None = None) -> list[str]:
    """Finds each recognized item in the prompt, one short query per item,
    in the order they appear, deduplicated:
    - item words written back to back ("shalwar kameez", "khussa shoes")
      stay one item, but a comma splits them ("jacket, jeans")
    - up to two describing words right before it are kept ("leather
      jacket", "white lawn shalwar kameez")
    - "for women" / "men's" anywhere in the prompt — or, failing that, the
      shopper's own saved gender — is added to every query, since eBay
      otherwise mixes in the other gender's listings."""
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[a-z']+", prompt.lower())]
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
        parts = [*words[k:i], *parts]
        if gender:
            parts = [gender, *parts]
        term = " ".join(parts)
        if term not in seen:
            seen.add(term)
            terms.append(term)
        i = j + 1
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


async def _fetch_pool(
    req: StylistAskRequest, profile: TasteProfile | None, gender: str | None = None
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
    terms = _extract_search_terms(req.prompt, gender)[: req.max_items]
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
        retries = {i: n for i, t in enumerate(terms) if not term_results[i] and (n := _narrow_term(t))}
        if retries:
            retried = await asyncio.gather(*(live_search(n, limit=per_term_limit) for n in retries.values()))
            for i, results in zip(retries.keys(), retried):
                term_results[i] = results

        pool: list[_Candidate] = []
        seen_ids: set[tuple[str, str]] = set()
        for term, results in zip(terms, term_results):
            results = [r for r in results if not _unsuitable(term, r.raw.name, req.prompt)]
            # only listings that are the item asked for, while any are
            exact = [r for r in results if _is_the_item(term, r.raw.name)]
            results = sorted(exact or results, key=lambda r: -_fit(term, r.raw.name))
            # Retailers match words, not shoppers: "men leather ankle boots"
            # still returns women's heels, and those became the alternatives
            # offered under a man's boots. Filter each term separately, so
            # one badly-matched item can't leave the shopper without boots.
            for r in keep_for_gender(results, gender, lambda r: r.raw.name):
                if _colour_conflicts(req.prompt, r.raw.name):
                    continue
                if _whole_outfit_for_a_piece(term, r.raw.name):
                    continue
                key = (r.provider.slug, r.raw.retailer_product_id)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                pool.append(_Candidate(result=r, term=term))
    else:
        # No recognized item word (e.g. a bare brand/style ask) — fall
        # back to the prompt as a single query, same as before.
        loose = await live_search(req.prompt, limit=_LIVE_FETCH_POOL_SIZE)
        pool = [_Candidate(result=r, term=req.prompt) for r in keep_for_gender(loose, gender, lambda r: r.raw.name)]

    if req.budget_min_cents is not None:
        pool = [c for c in pool if c.result.raw.price_cents >= req.budget_min_cents]
    if req.budget_max_cents is not None:
        pool = [c for c in pool if c.result.raw.price_cents <= req.budget_max_cents]

    if profile and profile.has_signal:
        # affinity_score only reads .color/.brand/.style_tags — present on
        # RawProduct with the same names, so this works unmodified even
        # though its signature says Product.
        pool.sort(key=lambda c: affinity_score(c.result.raw, profile), reverse=True)  # type: ignore[arg-type]
    return pool


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
    by_price = sorted(same_term, key=lambda result: result.raw.price_cents)
    if len(by_price) <= _MAX_ALTERNATIVES:
        return by_price
    # spread across the price range rather than just "the next 3 cheapest"
    step = (len(by_price) - 1) / (_MAX_ALTERNATIVES - 1)
    return [by_price[round(i * step)] for i in range(_MAX_ALTERNATIVES)]


def _slot_for(raw: RawProduct) -> OutfitSlot:
    return slot_for(raw.name, raw.category_slug)


async def _shopper_gender(db: AsyncSession, user_id: str, prompt: str) -> str | None:
    """Who the look is for: what the prompt says ("a kurti for my wife"),
    else their saved gender, else the audience they picked most of in
    onboarding — nothing forces them to state a gender."""
    said = _gender_in_prompt(prompt)
    if said:
        return said
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
    wardrobe_item: WardrobeItem | None = None
    if req.wardrobe_item_id:
        wardrobe_item = await _load_owned_wardrobe_item(db, user_id, req.wardrobe_item_id)

    # An explicit "build around this" anchor takes priority over general
    # taste — the user asked for something specific, not just a good match.
    profile = _wardrobe_anchor_profile(wardrobe_item) if wardrobe_item else await build_taste_profile(db, user_id)
    gender = await _shopper_gender(db, user_id, req.prompt)
    pool = await _fetch_pool(req, profile, gender)
    left_out = _extract_search_terms(req.prompt, gender)[req.max_items :]
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
    chosen = _drop_redundant_candidates(chosen)

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
        response_summary=recommendation.summary + _left_out_note(left_out, req.max_items, gender),
        recommended_product_ids=[p.id for p in chosen_products],
        recommended_outfit_id=outfit.id if outfit else None,
    )
    db.add(stylist_request)
    await db.commit()
    await db.refresh(stylist_request)
    return stylist_request, alternatives_by_product_id
