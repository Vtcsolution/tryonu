"""Import the approved Admitad programmes' product feeds.

    python -m app.scripts.admitad_import

Run daily (cron). Reads only from Admitad; writes only the admitad_feed_items
table. Prints programme names and counts, never a feed link or credential.
"""

from __future__ import annotations

import asyncio
import sys

from app.db.session import AsyncSessionLocal
from app.services.admitad import AdmitadError
from app.services.admitad_feeds import import_all


async def main() -> int:
    async with AsyncSessionLocal() as db:
        try:
            reports = await import_all(db)
        except AdmitadError as exc:
            print("FAIL:", exc)
            return 1
    failed = 0
    for r in reports:
        if r.error:
            failed += 1
            print(f"FAIL  {r.name}: {r.error}")
        elif not r.feeds_used:
            print(f"SKIP  {r.name}: no fresh feed (stale: {r.feeds_stale or 'none'})")
        else:
            extra = " (capped)" if r.capped else ""
            stale = f", stale feeds skipped: {r.feeds_stale}" if r.feeds_stale else ""
            print(f"OK    {r.name}: {r.rows_kept} products{extra} from {len(r.feeds_used)} feed(s){stale}; {r.rows_skipped} rows unusable")
    return 1 if failed and failed == len(reports) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
