"""Product catalog sync — run periodically (cron/RQ scheduler) in
production, or manually via `python -m app.scripts.ingest_products`."""

from __future__ import annotations

import asyncio

from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.services.product_ingestion_service import sync_all_retailers


async def run_product_sync_async() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        results = await sync_all_retailers(session)
        logger.info("product_sync_complete", results=results)
        return results


def run_product_sync() -> None:
    """Sync entrypoint RQ calls in the worker process."""
    asyncio.run(run_product_sync_async())
