"""Add 10 test products to a company store, or remove them again.

    python -m app.scripts.sample_store_products                 # add to the test store
    python -m app.scripts.sample_store_products --email x@y.com # add to that owner's store
    python -m app.scripts.sample_store_products --remove        # take the test products out

The products are real fashion items with real photos, copied from the Admitad
catalogue already in the database (one per kind: dress, earrings, bag...), so
search and try-on can be tested on the store. They are marked "sample-" and
--remove deletes only those; the store's own products are never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.admitad_feed import AdmitadFeedItem
from app.models.store import Store, StoreProduct
from app.models.user import User
from app.services import store_service as svc

PREFIX = "sample-"
# (words in the product name, any language the catalogue uses; category on the card; gender)
KINDS = [
    (("dress", "vestido", "robe"), "Dress", "women"),
    (("lehenga",), "Lehenga", "women"),
    (("kurta", "kurti"), "Kurta", "women"),
    (("earrings", "pendientes", "boucles"), "Earrings", "women"),
    (("necklace", "collar", "collier"), "Necklace", "women"),
    (("bracelet", "pulsera"), "Bracelet", "women"),
    (("handbag", "bolso", "sac à main"), "Bag", "women"),
    (("sandals", "sandalias"), "Shoes", "women"),
    (("watch", "reloj", "montre"), "Watch", "women"),
    (("scarf", "pañuelo", "bufanda", "foulard"), "Scarf", "women"),
    (("heels", "tacón", "tacones"), "Shoes", "women"),
    (("blouse", "blusa", "top"), "Top", "women"),
    (("skirt", "falda", "jupe"), "Skirt", "women"),
    ((" ring", "anillo", "bague"), "Ring", "women"),
]
CURRENCIES = ("usd", "eur", "gbp")


async def add_samples(db: AsyncSession, store: Store, *, count: int = 10) -> list[str]:
    """Up to `count` sample products (within the plan's free slots); returns their names."""
    used = await svc.active_product_count(db, store.id)
    room = max(0, store.plan_product_limit - used) if svc.plan_active(store) else 0
    wanted = min(count, room)
    have = set(
        (await db.execute(select(StoreProduct.external_id).where(StoreProduct.store_id == store.id))).scalars()
    )
    added: list[str] = []
    for words, category, gender in KINDS:
        if len(added) >= wanted:
            break
        item = await db.scalar(
            select(AdmitadFeedItem)
            .where(
                AdmitadFeedItem.available.is_(True),
                or_(*(func.lower(AdmitadFeedItem.name).like(f"%{w}%") for w in words)),
                func.lower(AdmitadFeedItem.currency).in_(CURRENCIES),
                AdmitadFeedItem.image_url.like("http%"),
                AdmitadFeedItem.price_cents > 0,
            )
            .order_by(AdmitadFeedItem.price_cents)
            .limit(1)
        )
        if item is None:
            continue
        external_id = f"{PREFIX}{item.campaign_id}-{item.offer_id}"[:128]
        if external_id in have:
            continue
        db.add(
            StoreProduct(
                store_id=store.id,
                source="manual",
                external_id=external_id,
                name=item.name[:512],
                description=(item.description or "")[:4000] or None,
                price_cents=item.price_cents,
                currency=item.currency.lower(),
                images=[item.image_url],
                product_url=item.product_url,
                category=category,
                gender=gender,
                is_active=True,
            )
        )
        have.add(external_id)
        added.append(item.name)
    await db.commit()
    return added


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
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
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
        added = await add_samples(db, store)
        print(f"{store.name}: added {len(added)} test product(s)")
        for name in added:
            print(f"  + {name[:90]}")
        if not added:
            print("Nothing added: the plan is full, the test products are already there, or the Admitad catalogue is empty.")
        live = "LIVE: shoppers can find them" if svc.is_live(store) else "not live yet (needs approval and a plan)"
        print(f"Store is {live}. Remove them later with --remove.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
