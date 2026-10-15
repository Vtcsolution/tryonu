"""Add test products to a company store (10, or --count N), or remove them again.

    python -m app.scripts.sample_store_products --preview       # show what would be added
    python -m app.scripts.sample_store_products                 # add 10 to the test store
    python -m app.scripts.sample_store_products --email x@y.com --count 20  # 20 to that owner's store
    python -m app.scripts.sample_store_products --remove        # take the test products out
    python -m app.scripts.sample_store_products --count 20 --csv /root/products.csv
        # write them to a CSV file instead, for a store's "Upload CSV/JSON file" button

The products are real fashion items with real photos, copied from the Admitad
catalogue already in the database (a dress, earrings, a bag... then a second of
each kind, and so on; women's items only), so
search and try-on can be tested on the store. They are marked "sample-" and
--remove deletes only those; the store's own products are never touched.

Picking: whole words only ("heels" never matches "wheels"), obvious
non-fashion items skipped (cups, cases, tools, costumes, kids), fashion
categories and women's items preferred, and a normal price rather than the
cheapest match.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.admitad_feed import AdmitadFeedItem
from app.models.store import Store, StoreProduct
from app.models.user import User
from app.services import store_service as svc

PREFIX = "sample-"
# (whole words in the product name, in the catalogue's languages; category on
# the card; words that mean it's something else: a shirt "collar", a "reloj
# de pulsera" is a watch, a blouse with a "ring" detail)
KINDS = [
    (("dress", "vestido", "robe"), "Dress", r"shirt|camisa|blouse|blusa|bag|bolso"),
    (("lehenga",), "Lehenga", None),
    (("kurta", "kurti"), "Kurta", None),
    (("earrings", "pendientes", "boucles"), "Earrings", None),
    (("necklace", "collar", "collier", "colgante", "gargantilla"), "Necklace",
     r"shirt|camisa|blouse|blusa|dress|vestido|sleeve|manga|jacket|chaqueta|sweater|jersey|coat|abrigo|polo|perro|dog"),
    (("bracelet", "pulsera"), "Bracelet", r"reloj|relojes|watch|watches"),
    (("handbag", "bolso", "shoulder bag", "tote"), "Bag", None),
    (("sandals", "sandalias"), "Shoes", None),
    (("watch", "reloj", "montre"), "Watch", r"band|correa|strap"),
    (("scarf", "pañuelo", "bufanda", "foulard"), "Scarf", None),
    (("heels", "tacón", "tacones", "pumps"), "Shoes", None),
    (("blouse", "blusa"), "Top", None),
    (("skirt", "falda", "jupe"), "Skirt", r"dress|vestido"),
    (("ring", "anillo", "bague"), "Ring", r"blouse|dress|shirt|sleeve|keyring|llavero"),
]
CURRENCIES = ("usd", "eur", "gbp")
# a normal fashion price: not a 1-euro trinket, not a luxury outlier
MIN_CENTS, MAX_CENTS = 900, 40_000

# names with any of these are not something to wear
_NOT_FASHION = re.compile(
    r"\b(vasos?|cups?|tazas?|mugs?|fundas?|case|cover|funda|juego|set de|destornillador\w*|recambio|repuesto|"
    r"pedal|rodamiento|wheels?|plástico|plastico|plastic|fiesta|party|halloween|disfraz|costume|carnaval\w*|"
    r"juguete|toy|niñ[oa]s?|kids?|infantil|bebé|baby|perro|dog|gato|cat|mascota|pet|móvil|movil|phone|"
    r"iphone|samsung|llavero|keychain|pegatina|sticker|póster|poster|cojín|cushion|lámpara|lamp|herramienta|tool|"
    r"tablet|ebook|laptop|portátil|portatil|compatible|honor|xiaomi|huawei|ipad|kindle)\b",
    re.IGNORECASE,
)
_FASHION_CATEGORY = re.compile(
    r"ropa|moda|fashion|vestidos?|clothing|apparel|joyer|jewel|bisuter|bolsos|bags?|calzado|zapat|shoes|"
    r"accesorios|accessories|relojes|watches|mujer|women",
    re.IGNORECASE,
)
# men's items stay out of a women's test store
_MEN = re.compile(r"\b(hombre|hombres|caballero|men|mens|men's|man|homme|masculino)\b", re.IGNORECASE)
_WOMEN = re.compile(r"\b(mujer|women|woman|womens|ladies|señora|dama|femme|femenin[oa])\b", re.IGNORECASE)


def _word_re(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


def _score(item: AdmitadFeedItem) -> int:
    score = 0
    if item.category and _FASHION_CATEGORY.search(item.category):
        score += 3
    if _WOMEN.search(item.name) or (item.category and _WOMEN.search(item.category)):
        score += 2
    return score


async def pick_samples(db: AsyncSession, *, count: int = 10, skip: set[str] | None = None) -> list[tuple[AdmitadFeedItem, str]]:
    """Up to `count` good women's catalogue items, spread over the kinds (a dress,
    earrings, a bag, ... then a second of each, and so on): (item, category label)."""
    skip = set(skip or ())
    ranked: list[tuple[str, list[AdmitadFeedItem]]] = []
    for words, category, not_this in KINDS:
        candidates = (
            await db.execute(
                select(AdmitadFeedItem)
                .where(
                    AdmitadFeedItem.available.is_(True),
                    or_(*(func.lower(AdmitadFeedItem.name).like(f"%{w}%") for w in words)),
                    func.lower(AdmitadFeedItem.currency).in_(CURRENCIES),
                    AdmitadFeedItem.image_url.like("http%"),
                    AdmitadFeedItem.price_cents.between(MIN_CENTS, MAX_CENTS),
                )
                .order_by(AdmitadFeedItem.id)  # the same picks in --preview and when adding
                .limit(600)
            )
        ).scalars().all()
        whole = _word_re(words)
        other = re.compile(rf"\b({not_this})\b", re.IGNORECASE) if not_this else None
        good = [
            c
            for c in candidates
            if whole.search(c.name)
            and not _NOT_FASHION.search(c.name)
            and not _MEN.search(c.name)
            and not (other and other.search(c.name))
        ]
        if not good:
            continue
        # best matches first; among equals, normal prices (closest to the middle) first
        prices = sorted(c.price_cents for c in good)
        middle = prices[len(prices) // 2]
        good.sort(key=lambda c: (-_score(c), abs(c.price_cents - middle)))
        ranked.append((category, good))

    picks: list[tuple[AdmitadFeedItem, str]] = []
    names: set[str] = set()
    position = {category: 0 for category, _ in ranked}
    while len(picks) < count and any(position[c] < len(items) for c, items in ranked):
        for category, items in ranked:
            if len(picks) >= count:
                break
            while position[category] < len(items):
                item = items[position[category]]
                position[category] += 1
                key = item.name.strip().lower()[:60]  # the same product listed twice: once
                if _external_id(item) in skip or key in names:
                    continue
                skip.add(_external_id(item))
                names.add(key)
                picks.append((item, category))
                break
    return picks


def _external_id(item: AdmitadFeedItem) -> str:
    return f"{PREFIX}{item.campaign_id}-{item.offer_id}"[:128]


async def add_samples(db: AsyncSession, store: Store, *, count: int = 10) -> list[str]:
    """Up to `count` sample products (within the plan's free slots); returns their names."""
    used = await svc.active_product_count(db, store.id)
    room = max(0, store.plan_product_limit - used) if svc.plan_active(store) else 0
    have = set(
        (await db.execute(select(StoreProduct.external_id).where(StoreProduct.store_id == store.id))).scalars()
    )
    picks = await pick_samples(db, count=min(count, room), skip=have)
    for item, category in picks:
        db.add(
            StoreProduct(
                store_id=store.id,
                source="manual",
                external_id=_external_id(item),
                name=item.name[:512],
                description=(item.description or "")[:4000] or None,
                price_cents=item.price_cents,
                currency=item.currency.lower(),
                images=[item.image_url],
                product_url=item.product_url,
                category=category,
                gender="women",
                is_active=True,
            )
        )
    await db.commit()
    return [item.name for item, _ in picks]


def write_csv(path: str, picks: list[tuple[AdmitadFeedItem, str]]) -> None:
    """The columns a store's "Upload CSV/JSON file" reads (see store_service.normalize_feed_row)."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh)
        out.writerow(["id", "name", "price", "currency", "link", "image", "category", "gender", "description"])
        for item, category in picks:
            out.writerow([
                f"{item.campaign_id}-{item.offer_id}",
                item.name,
                f"{item.price_cents / 100:.2f}",
                item.currency.upper(),
                item.product_url,
                item.image_url,
                category,
                "women",
                (item.description or "")[:500],
            ])


async def remove_samples(db: AsyncSession, store: Store) -> int:
    result = await db.execute(
        delete(StoreProduct).where(StoreProduct.store_id == store.id, StoreProduct.external_id.like(f"{PREFIX}%"))
    )
    await db.commit()
    return result.rowcount or 0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="ranazia943+store@gmail.com", help="the store owner's sign-in email")
    parser.add_argument("--remove", action="store_true", help="remove the test products")
    parser.add_argument("--preview", action="store_true", help="only show what would be added")
    parser.add_argument("--count", type=int, default=10, help="how many products to add (1-50)")
    parser.add_argument("--csv", help="write the products to this CSV file instead of adding them")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        if args.csv:
            picks = await pick_samples(db, count=max(1, min(args.count, 50)))
            write_csv(args.csv, picks)
            print(f"Wrote {len(picks)} product(s) to {args.csv}")
            for item, category in picks:
                print(f"  {category:9} {item.price_cents / 100:>8.2f} {item.currency.upper()}  {item.name[:70]}")
            return 0
        if args.preview:
            picks = await pick_samples(db, count=max(1, min(args.count, 50)))
            print(f"Would add {len(picks)} product(s):")
            for item, category in picks:
                print(f"  {category:9} {item.price_cents / 100:>8.2f} {item.currency.upper()}  {item.name[:80]}")
            return 0
        user = await db.scalar(select(User).where(User.email == args.email.lower()))
        store = await db.scalar(select(Store).where(Store.owner_user_id == user.id)) if user else None
        if store is None:
            print(f"No store found for {args.email}. Open the store at /business first.")
            return 1
        if args.remove:
            print(f"{store.name}: removed {await remove_samples(db, store)} test product(s)")
            return 0
        if not svc.plan_active(store):
            print(f"{store.name} has no active plan. Give it one in Admin -> Company stores first.")
            return 1
        added = await add_samples(db, store, count=max(1, min(args.count, 50)))
        print(f"{store.name}: added {len(added)} test product(s)")
        for name in added:
            print(f"  + {name[:90]}")
        if not added:
            print("Nothing added: the plan is full, the test products are already there, or nothing fashion-like matched.")
        live = "LIVE: shoppers can find them" if svc.is_live(store) else "not live yet (needs approval and a plan)"
        print(f"Store is {live}. Remove them later with --remove.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
