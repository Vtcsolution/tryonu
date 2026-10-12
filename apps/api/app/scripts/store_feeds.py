"""Import every live company store's product feed. Run daily (cron).

    python -m app.scripts.store_feeds

Only stores that are approved, have an active plan and a feed link are
imported; each keeps its typed-in products and stays within its plan limit.
Prints store names and results, never a feed link.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.store import Store
from app.services import store_service as svc


async def main() -> int:
    async with AsyncSessionLocal() as db:
        stores = (await db.execute(select(Store).where(Store.feed_url.is_not(None)))).scalars().all()
        live = [s for s in stores if svc.is_live(s)]
        for store in live:
            print(f"{store.name}: {await svc.import_store_feed(db, store)}")
    print(f"{len(live)} store feed(s) imported")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
