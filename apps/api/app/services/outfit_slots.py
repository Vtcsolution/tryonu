"""Which part of an outfit a product is — decides what the try-on draws on
the photo (tops, bottoms, full outfits, outerwear, sometimes shoes) versus
what's only listed alongside it (jewellery, watches, bags).

Retailer titles are keyword-stuffed ("Men waistcoat for shalwar kameez",
"Jhumka earrings for saree"), so the product word that appears FIRST in
the title wins — that's what the listing actually is (or, for back-to-back
words like "Tuxedo Vest", the last of them).
"""

from __future__ import annotations

import re

from app.models.enums import OutfitSlot

# (slot, words) — every word is matched as a whole word, case-insensitive
_SLOT_WORDS: list[tuple[OutfitSlot, tuple[str, ...]]] = [
    (OutfitSlot.ACCESSORY, (
        "earring", "earrings", "jhumka", "jhumkas", "chandbali", "bangle", "bangles", "bracelet", "bracelets",
        "necklace", "necklaces", "choker", "pendant", "ring", "rings", "tikka", "anklet", "anklets", "payal",
        "nose pin", "jewelry", "jewellery", "cufflinks", "sunglasses", "belt", "belts", "cap", "hat", "hats",
        "scarf", "scarves", "hijab", "tie", "wallet",
    )),
    (OutfitSlot.WATCH, ("watch", "watches", "smartwatch")),
    (OutfitSlot.BAG, ("bag", "bags", "handbag", "handbags", "clutch", "purse", "tote", "backpack", "duffle")),
    (OutfitSlot.SHOES, (
        "shoe", "shoes", "khussa", "khussas", "jutti", "juttis", "mojari", "chappal", "chappals", "kolhapuri",
        "sandal", "sandals", "heels", "flats", "loafer", "loafers", "sneaker", "sneakers", "boot", "boots",
        "trainers", "slippers", "peshawari",
    )),
    # full outfits — replace both top and bottom on the photo
    (OutfitSlot.DRESS, (
        "shalwar kameez", "salwar kameez", "shalwar", "salwar", "kameez", "kurta pajama", "kurta shalwar",
        "lehenga", "lehengas", "saree", "sarees", "sari", "anarkali", "pishwas", "frock", "frocks",
        "sharara", "gharara", "abaya", "jilbab", "sherwani", "dress", "dresses", "gown", "jumpsuit", "romper",
        "3pc", "3 piece", "2pc", "2 piece", "suit", "tuxedo",
    )),
    (OutfitSlot.OUTERWEAR, (
        "waistcoat", "vest", "blazer", "jacket", "jackets", "coat", "coats", "bomber", "cardigan", "shawl",
        "pashmina", "poncho", "parka",
    )),
    (OutfitSlot.BOTTOM, (
        "jeans", "jean", "trouser", "trousers", "pant", "pants", "chinos", "palazzo", "shorts", "skirt",
        "leggings", "pajama", "pyjama",
    )),
    (OutfitSlot.TOP, (
        "shirt", "shirts", "t-shirt", "tshirt", "tee", "top", "tops", "blouse", "kurta", "kurtas", "kurti",
        "kurtis", "tunic", "sweater", "hoodie", "polo",
    )),
]
_PATTERNS = [
    (slot, re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b"))
    for slot, words in _SLOT_WORDS
]


def slot_for(name: str, category_slug: str | None = None) -> OutfitSlot:
    text = name.lower()
    # longest match wins where they overlap ("kurta pajama" over "kurta")
    hits: list[tuple[int, int, OutfitSlot]] = []
    for start, end, slot in sorted(
        ((m.start(), m.end(), slot) for slot, pattern in _PATTERNS for m in pattern.finditer(text)),
        key=lambda h: (h[0], -h[1]),
    ):
        if not hits or start >= hits[-1][1]:
            hits.append((start, end, slot))
    if hits:
        _, end, slot = hits[0]
        # "Tuxedo Vest", "Suit Jacket": a product word right after the first
        # one names the item
        if len(hits) > 1 and not text[end : hits[1][0]].strip():
            slot = hits[1][2]
        return slot
    cat = (category_slug or "").lower()
    if "dress" in cat:
        return OutfitSlot.DRESS
    if "coat" in cat or "jacket" in cat:
        return OutfitSlot.OUTERWEAR
    if "shoe" in cat or "sneaker" in cat or "boot" in cat:
        return OutfitSlot.SHOES
    if "denim" in cat or "pant" in cat:
        return OutfitSlot.BOTTOM
    if "top" in cat:
        return OutfitSlot.TOP
    if "watch" in cat:
        return OutfitSlot.WATCH
    if "bag" in cat:
        return OutfitSlot.BAG
    return OutfitSlot.OTHER


# drawing order on the photo: the base outfit first, then layers over it
LAYER_ORDER = {
    OutfitSlot.DRESS: 0,
    OutfitSlot.BOTTOM: 1,
    OutfitSlot.TOP: 2,
    OutfitSlot.OUTERWEAR: 3,
    OutfitSlot.SHOES: 4,
}


# --- what the try-on actually draws -------------------------------------

_CLOTHING = {OutfitSlot.TOP, OutfitSlot.BOTTOM, OutfitSlot.DRESS, OutfitSlot.OUTERWEAR}

# tryon-v1.6's "category" (per FASHN's docs: auto/tops/bottoms/one-pieces).
# "auto" guessed wrong on close-up product shots, so it's always explicit.
V16_CATEGORY = {
    OutfitSlot.DRESS: "one-pieces",
    OutfitSlot.TOP: "tops",
    OutfitSlot.OUTERWEAR: "tops",
    OutfitSlot.BOTTOM: "bottoms",
}

# tryon-max takes free-text instructions — used so a waistcoat goes OVER
# the kameez and shoes replace only the shoes, instead of the model
# swapping out whatever it thinks is closest.
MAX_PROMPT = {
    OutfitSlot.DRESS: "Dress the person in this complete outfit, replacing their current top and bottom.",
    OutfitSlot.TOP: "Replace only the person's top with this item; keep everything else unchanged.",
    OutfitSlot.BOTTOM: "Replace only the person's trousers or bottom with this item; keep everything else unchanged.",
    OutfitSlot.OUTERWEAR: "Layer this item over the person's current outfit; keep the clothes underneath visible and unchanged.",
    OutfitSlot.SHOES: "Replace only the person's footwear with these; keep the outfit unchanged.",
}


_WEARABLE = _CLOTHING | {OutfitSlot.SHOES, OutfitSlot.BAG, OutfitSlot.WATCH, OutfitSlot.ACCESSORY}


def renderable_slots(model: str, whole_outfit: bool = False) -> set[OutfitSlot]:
    if whole_outfit:
        # one image-editing render of the whole look: anything wearable
        return set(_WEARABLE)
    # tryon-max draws footwear too (FASHN docs: clothing, shoes, hats, …);
    # v1.6 is clothing only
    return _CLOTHING | {OutfitSlot.SHOES} if model == "tryon-max" else set(_CLOTHING)


def effective_slot(slot: OutfitSlot, product_name: str) -> OutfitSlot:
    # "other" is what items the classifier didn't know yet were saved as
    return slot_for(product_name) if slot == OutfitSlot.OTHER else slot


def render_plan(
    items: list[tuple[OutfitSlot, str]], model: str, whole_outfit: bool = False
) -> list[tuple[int, OutfitSlot]]:
    """(index into `items`, slot) for each item the try-on will draw, in
    drawing order: the base outfit first, then layers over it, then shoes.

    - one item per slot — a second top would just replace the first —
      except jewellery, where bangles AND earrings are both worn
    - a full outfit (shalwar kameez, dress) replaces any separate top/bottom
    - on tryon-v1.6 a full outfit is drawn alone: v1.6 can't layer, so a
      waistcoat sent after it replaces the kameez's top instead of going
      over it. tryon-max and whole-outfit renders layer it properly.
    """
    allowed = renderable_slots(model, whole_outfit)
    picked: list[tuple[int, OutfitSlot]] = []
    for i, (slot, name) in enumerate(items):
        s = effective_slot(slot, name)
        if s not in allowed:
            continue
        if s != OutfitSlot.ACCESSORY and any(ps == s for _, ps in picked):
            continue
        picked.append((i, s))
    slots = {s for _, s in picked}
    if OutfitSlot.DRESS in slots:
        if whole_outfit or model == "tryon-max":
            picked = [(i, s) for i, s in picked if s not in (OutfitSlot.TOP, OutfitSlot.BOTTOM)]
        else:
            picked = [(i, s) for i, s in picked if s == OutfitSlot.DRESS]
    return sorted(picked, key=lambda p: (LAYER_ORDER.get(p[1], 9), p[0]))
