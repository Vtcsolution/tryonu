"""Append-only capture for personalization — no ranking logic here yet
(that's Phase 4); this only ever writes an event row, never reads one back
for a response. Never raises: a logging failure must not break a search or
product-view request."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.history import ProductView, SearchHistory
from app.schemas.product import ProductSearchFilters


async def log_search(db: AsyncSession, *, user_id: str | None, filters: ProductSearchFilters, result_count: int) -> None:
    if not filters.q:
        return  # only free-text searches are a personalization signal — not every browse/filter listing
    try:
        db.add(
            SearchHistory(
                user_id=user_id,
                query=filters.q,
                filters=filters.model_dump(exclude={"q", "limit", "offset"}, exclude_none=True),
                result_count=result_count,
            )
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("search_history_log_failed", error=str(exc))


async def log_product_view(db: AsyncSession, *, user_id: str | None, product_id: str, source: str | None = None) -> None:
    try:
        db.add(ProductView(user_id=user_id, product_id=product_id, source=source))
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("product_view_log_failed", error=str(exc))
