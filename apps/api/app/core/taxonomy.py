"""The shopping-preference category tree: audience -> category ->
subcategory -> style. Single source of truth for the onboarding wizard
(served via GET /catalog/taxonomy), for validating what users save, and for
turning a saved choice into the live retailer search behind "For you".

Every `search` phrase was checked against eBay's live search and returns
real listings. Ids are stable once shipped — users' saved choices store
them — so rename labels freely, but never repurpose an id.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    search: str
    icon: str = ""
    children: tuple["Node", ...] = field(default_factory=tuple)


def n(id: str, label: str, search: str, *children: Node, icon: str = "") -> Node:  # noqa: A002
    return Node(id=id, label=label, search=search, icon=icon, children=tuple(children))


WOMEN = n(
    "w", "Women", "women fashion",
    n("w.eastern", "Eastern wear", "women pakistani dress",
      n("w.eastern.shalwar", "Shalwar kameez", "women shalwar kameez",
        n("w.eastern.shalwar.lawn", "Lawn", "lawn shalwar kameez"),
        n("w.eastern.shalwar.cotton", "Cotton", "cotton shalwar kameez women"),
        n("w.eastern.shalwar.chiffon", "Chiffon", "chiffon shalwar kameez"),
        n("w.eastern.shalwar.embroidered", "Embroidered", "embroidered shalwar kameez women"),
        n("w.eastern.shalwar.party", "Party wear", "party wear salwar kameez"),
        n("w.eastern.shalwar.winter", "Khaddar & winter", "khaddar suit women")),
      n("w.eastern.kurti", "Kurti & kurta", "women kurti",
        n("w.eastern.kurti.short", "Short kurti", "short kurti women"),
        n("w.eastern.kurti.long", "Long kurta", "long kurta women"),
        n("w.eastern.kurti.embroidered", "Embroidered kurti", "embroidered kurti")),
      n("w.eastern.pishwas", "Pishwas & frocks", "pishwas",
        n("w.eastern.pishwas.anarkali", "Anarkali", "anarkali dress"),
        n("w.eastern.pishwas.maxi", "Maxi pishwas", "pakistani maxi dress women"),
        n("w.eastern.pishwas.frock", "Long frock", "pakistani long frock")),
      n("w.eastern.bridal", "Lehenga & bridal", "lehenga choli",
        n("w.eastern.bridal.lehenga", "Lehenga choli", "lehenga choli"),
        n("w.eastern.bridal.sharara", "Sharara", "sharara suit"),
        n("w.eastern.bridal.gharara", "Gharara", "gharara dress"),
        n("w.eastern.bridal.bridal", "Bridal dress", "pakistani bridal dress")),
      n("w.eastern.saree", "Saree", "saree",
        n("w.eastern.saree.silk", "Silk", "silk saree"),
        n("w.eastern.saree.chiffon", "Chiffon", "chiffon saree"),
        n("w.eastern.saree.party", "Party wear", "party wear saree")),
      n("w.eastern.modest", "Abaya & hijab", "abaya",
        n("w.eastern.modest.abaya", "Abaya", "abaya"),
        n("w.eastern.modest.hijab", "Hijab", "hijab scarf"),
        n("w.eastern.modest.jilbab", "Jilbab", "jilbab")),
      n("w.eastern.dupatta", "Dupatta & shawl", "dupatta",
        n("w.eastern.dupatta.dupatta", "Dupatta", "dupatta"),
        n("w.eastern.dupatta.shawl", "Shawl", "women shawl"),
        n("w.eastern.dupatta.pashmina", "Pashmina", "pashmina shawl")),
      icon="👘"),
    n("w.western", "Western wear", "women clothing",
      n("w.western.tops", "Tops & blouses", "women blouse top"),
      n("w.western.dresses", "Dresses", "women dress",
        n("w.western.dresses.maxi", "Maxi", "women maxi dress"),
        n("w.western.dresses.midi", "Midi", "women midi dress"),
        n("w.western.dresses.evening", "Evening gown", "evening gown women")),
      n("w.western.jeans", "Jeans & trousers", "women jeans"),
      n("w.western.skirts", "Skirts", "women skirt"),
      n("w.western.outerwear", "Jackets & coats", "women jacket",
        n("w.western.outerwear.leather", "Leather", "women leather jacket"),
        n("w.western.outerwear.denim", "Denim", "women denim jacket"),
        n("w.western.outerwear.coat", "Long coat", "women long coat")),
      n("w.western.active", "Activewear", "women activewear"),
      icon="👗"),
    n("w.jewellery", "Jewellery", "women jewelry",
      n("w.jewellery.bangles", "Bangles", "bangles",
        n("w.jewellery.bangles.glass", "Glass (churi)", "glass bangles set"),
        n("w.jewellery.bangles.kundan", "Kundan", "kundan bangles"),
        n("w.jewellery.bangles.gold", "Gold-plated", "gold plated bangles"),
        n("w.jewellery.bangles.silver", "Silver", "silver bangles women"),
        n("w.jewellery.bangles.bridal", "Bridal set", "bridal bangles set"),
        n("w.jewellery.bangles.kada", "Kada", "kada bangle")),
      n("w.jewellery.rings", "Rings", "women ring",
        n("w.jewellery.rings.engagement", "Engagement", "engagement ring"),
        n("w.jewellery.rings.gold", "Gold", "gold ring women"),
        n("w.jewellery.rings.silver", "Silver", "sterling silver ring women"),
        n("w.jewellery.rings.fashion", "Fashion", "fashion ring women")),
      n("w.jewellery.earrings", "Earrings", "women earrings",
        n("w.jewellery.earrings.jhumka", "Jhumka", "jhumka earrings"),
        n("w.jewellery.earrings.chandbali", "Chandbali", "chandbali earrings"),
        n("w.jewellery.earrings.studs", "Studs", "stud earrings women"),
        n("w.jewellery.earrings.hoops", "Hoops", "hoop earrings")),
      n("w.jewellery.necklaces", "Necklaces", "women necklace",
        n("w.jewellery.necklaces.choker", "Choker", "choker necklace"),
        n("w.jewellery.necklaces.pendant", "Pendant", "pendant necklace women"),
        n("w.jewellery.necklaces.bridal", "Bridal set", "bridal jewelry set")),
      n("w.jewellery.tikka", "Maang tikka", "maang tikka"),
      n("w.jewellery.nose", "Nose pin", "nose pin"),
      n("w.jewellery.payal", "Anklet (payal)", "payal anklet"),
      icon="💍"),
    n("w.shoes", "Shoes", "women shoes",
      n("w.shoes.khussa", "Khussa", "khussa"),
      n("w.shoes.heels", "Heels", "women heels"),
      n("w.shoes.sandals", "Sandals", "women sandals"),
      n("w.shoes.flats", "Flats", "women flats"),
      n("w.shoes.sneakers", "Sneakers", "women sneakers"),
      n("w.shoes.boots", "Boots", "women boots"),
      icon="👠"),
    n("w.bags", "Bags", "women handbag",
      n("w.bags.handbag", "Handbags", "women handbag"),
      n("w.bags.clutch", "Clutches", "clutch purse"),
      n("w.bags.tote", "Totes", "tote bag women"),
      n("w.bags.crossbody", "Crossbody", "crossbody bag women"),
      icon="👜"),
    n("w.watches", "Watches", "women watch",
      n("w.watches.analog", "Analog", "women analog watch"),
      n("w.watches.bracelet", "Bracelet watch", "women bracelet watch"),
      n("w.watches.smart", "Smartwatch", "women smartwatch"),
      icon="⌚"),
    n("w.accessories", "Accessories", "women accessories",
      n("w.accessories.sunglasses", "Sunglasses", "women sunglasses"),
      n("w.accessories.scarves", "Scarves", "women scarf"),
      n("w.accessories.hair", "Hair accessories", "hair accessories women"),
      n("w.accessories.belts", "Belts", "women belt"),
      icon="🕶️"),
    icon="👩",
)

MEN = n(
    "m", "Men", "men fashion",
    n("m.eastern", "Eastern wear", "men shalwar kameez",
      n("m.eastern.shalwar", "Shalwar kameez", "men shalwar kameez",
        n("m.eastern.shalwar.washwear", "Wash & wear", "wash and wear shalwar kameez men"),
        n("m.eastern.shalwar.cotton", "Cotton", "cotton shalwar kameez men"),
        n("m.eastern.shalwar.embroidered", "Embroidered", "embroidered kameez men")),
      n("m.eastern.kurta", "Kurta", "men kurta",
        n("m.eastern.kurta.plain", "Plain kurta", "men plain kurta"),
        n("m.eastern.kurta.embroidered", "Embroidered kurta", "men embroidered kurta"),
        n("m.eastern.kurta.pajama", "Kurta pajama", "men kurta pajama")),
      n("m.eastern.waistcoat", "Waistcoat", "men waistcoat"),
      n("m.eastern.sherwani", "Sherwani", "men sherwani",
        n("m.eastern.sherwani.wedding", "Wedding sherwani", "wedding sherwani men"),
        n("m.eastern.sherwani.prince", "Prince coat", "prince coat men")),
      n("m.eastern.shawl", "Shawl", "men shawl"),
      icon="🧥"),
    n("m.western", "Western wear", "men clothing",
      n("m.western.tshirts", "T-shirts", "men t-shirt"),
      n("m.western.shirts", "Shirts", "men shirt",
        n("m.western.shirts.formal", "Formal", "men formal shirt"),
        n("m.western.shirts.casual", "Casual", "men casual shirt"),
        n("m.western.shirts.polo", "Polo", "men polo shirt")),
      n("m.western.jeans", "Jeans", "men jeans"),
      n("m.western.trousers", "Trousers & chinos", "men chinos"),
      n("m.western.outerwear", "Jackets & coats", "men jacket",
        n("m.western.outerwear.leather", "Leather", "men leather jacket"),
        n("m.western.outerwear.denim", "Denim", "men denim jacket"),
        n("m.western.outerwear.puffer", "Puffer", "men puffer jacket"),
        n("m.western.outerwear.blazer", "Blazer", "men blazer")),
      n("m.western.suits", "Suits", "men suit",
        n("m.western.suits.two", "2-piece", "men 2 piece suit"),
        n("m.western.suits.three", "3-piece", "men 3 piece suit"),
        n("m.western.suits.tuxedo", "Tuxedo", "men tuxedo")),
      n("m.western.hoodies", "Hoodies & sweatshirts", "men hoodie"),
      n("m.western.active", "Activewear", "men activewear"),
      icon="👔"),
    n("m.shoes", "Shoes", "men shoes",
      n("m.shoes.peshawari", "Peshawari chappal", "peshawari chappal"),
      n("m.shoes.khussa", "Khussa", "men khussa"),
      n("m.shoes.formal", "Formal shoes", "men formal shoes"),
      n("m.shoes.sneakers", "Sneakers", "men sneakers"),
      n("m.shoes.loafers", "Loafers", "men loafers"),
      n("m.shoes.boots", "Boots", "men boots"),
      icon="👞"),
    n("m.watches", "Watches", "men watch",
      n("m.watches.analog", "Analog", "men analog watch"),
      n("m.watches.chrono", "Chronograph", "men chronograph watch"),
      n("m.watches.smart", "Smartwatch", "men smartwatch"),
      icon="⌚"),
    n("m.accessories", "Accessories", "men accessories",
      n("m.accessories.wallets", "Wallets", "men wallet"),
      n("m.accessories.belts", "Belts", "men leather belt"),
      n("m.accessories.sunglasses", "Sunglasses", "men sunglasses"),
      n("m.accessories.caps", "Caps & hats", "men cap"),
      n("m.accessories.ties", "Ties & cufflinks", "men tie cufflinks"),
      n("m.accessories.rings", "Rings & bracelets", "men ring"),
      icon="🕶️"),
    n("m.bags", "Bags", "men bag",
      n("m.bags.backpack", "Backpacks", "men backpack"),
      n("m.bags.messenger", "Messenger", "men messenger bag"),
      n("m.bags.duffle", "Duffle", "duffle bag"),
      icon="🎒"),
    icon="👨",
)

KIDS = n(
    "k", "Kids", "kids clothing",
    n("k.girls", "Girls", "girls dress",
      n("k.girls.frocks", "Frocks", "girls frock"),
      n("k.girls.eastern", "Eastern suits", "girls shalwar kameez"),
      n("k.girls.tops", "Tops & jeans", "girls tops"),
      icon="👧"),
    n("k.boys", "Boys", "boys clothing",
      n("k.boys.shirts", "Shirts & tees", "boys shirt"),
      n("k.boys.kurta", "Kurta shalwar", "boys kurta shalwar"),
      n("k.boys.jeans", "Jeans & trousers", "boys jeans"),
      icon="👦"),
    n("k.baby", "Baby", "baby clothes",
      n("k.baby.rompers", "Rompers", "baby romper"),
      n("k.baby.sets", "Outfit sets", "baby outfit set"),
      icon="👶"),
    n("k.shoes", "Kids shoes", "kids shoes",
      n("k.shoes.sneakers", "Sneakers", "kids sneakers"),
      n("k.shoes.sandals", "Sandals", "kids sandals"),
      n("k.shoes.school", "School shoes", "kids school shoes"),
      icon="👟"),
    icon="🧒",
)

AUDIENCES: tuple[Node, ...] = (WOMEN, MEN, KIDS)


def _index(nodes: tuple[Node, ...], out: dict[str, Node], parents: dict[str, str | None], parent: str | None) -> None:
    for node in nodes:
        if node.id in out:
            raise ValueError(f"duplicate taxonomy id {node.id}")
        out[node.id] = node
        parents[node.id] = parent
        _index(node.children, out, parents, node.id)


NODES: dict[str, Node] = {}
PARENTS: dict[str, str | None] = {}
_index(AUDIENCES, NODES, PARENTS, None)


def ancestors(node_id: str) -> list[str]:
    chain = []
    parent = PARENTS.get(node_id)
    while parent is not None:
        chain.append(parent)
        parent = PARENTS.get(parent)
    return chain


def normalize_selection(ids: list[str]) -> list[str]:
    """Known ids only, de-duplicated, order kept."""
    seen: set[str] = set()
    return [i for i in ids if i in NODES and not (i in seen or seen.add(i))]


AUDIENCE_OF_GENDER = {"men": "m", "women": "w", "kids": "k"}
_GENDER_OF_AUDIENCE = {letter: gender for gender, letter in AUDIENCE_OF_GENDER.items()}


def audience_of(gender: str | None, selected: list[str]) -> str | None:
    """Who someone is shopping for: "men", "women", "kids" or unknown.

    Onboarding doesn't force a gender and the tree lets anyone tick
    anything, so when there's no gender saved, fall back to the audience
    they picked most of — otherwise one stray pick spoke for all of
    them ("Kurti for men with wallet and heels")."""
    if gender in AUDIENCE_OF_GENDER:
        return gender
    counts = Counter(node.id.split(".")[0] for node in feed_nodes(selected or []))
    return _GENDER_OF_AUDIENCE.get(counts.most_common(1)[0][0]) if counts else None


def audience_categories(gender: str | None) -> list[Node]:
    """The categories of that audience (Eastern wear, Shoes, …) — what to
    show someone whose saved picks don't fit their gender."""
    audience = AUDIENCE_OF_GENDER.get(gender or "")
    return list(NODES[audience].children) if audience else []


def feed_nodes(selected: list[str], gender: str | None = None) -> list[Node]:
    """The most specific choices: a selected node whose own selected
    descendants exist is represented by those descendants instead
    (picking "Bangles" then "Kundan" means kundan bangles, not all bangles).
    Audience-level picks (Women/Men/Kids) are skipped — too broad to search.

    With a gender, only that audience's picks count: saved categories can
    span audiences (onboarding lets anyone browse the whole tree), and a
    man was being offered "Kurti for men with wallet and heels". If none of
    the picks belong to his audience, that audience's own categories are
    used instead."""
    chosen = set(normalize_selection(selected))
    has_selected_descendant = {a for i in chosen for a in ancestors(i)}
    nodes = [
        NODES[i]
        for i in normalize_selection(selected)
        if i not in has_selected_descendant and PARENTS.get(i) is not None
    ]
    audience = AUDIENCE_OF_GENDER.get(gender or "")
    if audience:
        matching = [n for n in nodes if n.id.split(".")[0] == audience]
        return matching or audience_categories(gender)
    return nodes


def to_dict(node: Node) -> dict:
    return {
        "id": node.id,
        "label": node.label,
        "icon": node.icon,
        "children": [to_dict(c) for c in node.children],
    }
