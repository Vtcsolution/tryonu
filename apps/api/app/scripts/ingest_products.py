"""One-off / cron entrypoint:  python -m app.scripts.ingest_products"""

from __future__ import annotations

import asyncio

from app.core.logging import configure_logging
from app.workers.tasks.ingestion_tasks import run_product_sync_async

if __name__ == "__main__":
    configure_logging(debug=False)
    results = asyncio.run(run_product_sync_async())
    total = sum(results.values())
    print(f"Synced {total} products across {len(results)} retailer(s): {results}")
