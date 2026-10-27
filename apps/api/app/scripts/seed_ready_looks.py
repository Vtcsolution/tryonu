"""Publish the three winter looks from the home page slider (women, men, kids)
as the first Ready looks on tryonu.app/looks. Safe to run again: a look whose
title already exists is skipped.

    python -m app.scripts.seed_ready_looks

Finds each product live in its shop, saves it, copies the "after" picture from
apps/web/public/showcase and makes the outfit-receipt picture. Uses no try-on
credits (the pictures already exist).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.api.v1.endpoints.ready_looks import _get, _render
from app.api.v1.endpoints.showcase import LOOKS
from app.db.session import AsyncSessionLocal
from app.models.ready_look import ReadyLook, ReadyLookItem
from app.services.live_search_service import find_live_result
from app.services.product_ingestion_service import persist_single_product
from app.services.storage_service import get_storage

SHOWCASE = Path(__file__).resolve().parents[3] / "web" / "public" / "showcase"
SEED = [
    ("women", "Women's camel coat winter look", "studio-after.jpg"),
    ("men", "Men's winter overcoat look", "men-after.jpg"),
    ("kids", "Kids' winter puffer look", "kids-after.jpg"),
]


async def main() -> int:
    storage = get_storage()
    async with AsyncSessionLocal() as db:
        for order, (audience, title, picture) in enumerate(SEED):
            if await db.scalar(select(ReadyLook.id).where(ReadyLook.title == title)):
                print(f"skip   {title} (already published)")
                continue
            products = []
            for item in LOOKS[audience]:
                result = await find_live_result(item["q"], retailer_slug=item["r"], retailer_product_id=item["id"])
                if result is None:
                    print(f"       {item['name']}: no longer sold, left out")
                    continue
                products.append(await persist_single_product(db, result.provider, result.raw))
            if not products:
                print(f"skip   {title}: none of its products are sold any more")
                continue
            look = ReadyLook(title=title, audience=audience, season="Winter", image_key="pending", sort_order=10 - order)
            db.add(look)
            await db.flush()
            key = f"ready-looks/{look.id}/model.jpg"
            storage.put(key, (SHOWCASE / picture).read_bytes(), "image/jpeg")
            look.image_key = key
            for pos, product in enumerate(products):
                db.add(ReadyLookItem(look_id=look.id, product_id=product.id, position=pos))
            await db.commit()
            look = await _get(db, look.id)
            await _render(db, look)
            await db.commit()
            print(f"added  {title}: {len(products)} products  ->  /looks/{look.id}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
