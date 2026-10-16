"""Every product in a finished look, across its "Add more to this look" rounds."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import OutfitSlot
from app.models.outfit import OutfitItem
from app.models.product import Product
from app.models.tryon import TryOnJob

_PRODUCT_LOAD = (selectinload(Product.images), selectinload(Product.retailer))


async def look_products(db: AsyncSession, job: TryOnJob) -> tuple[list[tuple[Product, OutfitSlot | None]], set[str] | None]:
    """Every product in the look, earliest round first, and the ones drawn on
    the picture (None when the result doesn't say)."""
    chain: list[TryOnJob] = []
    current: TryOnJob | None = job
    while current is not None and len(chain) < 6:
        chain.append(current)
        if not current.base_job_id:
            break
        current = await db.scalar(
            select(TryOnJob).where(TryOnJob.id == current.base_job_id).options(selectinload(TryOnJob.result))
        )
    out: list[tuple[Product, OutfitSlot | None]] = []
    seen: set[str] = set()
    drawn: set[str] | None = None
    for round_job in reversed(chain):
        if round_job.result is not None and round_job.result.placements:
            drawn = drawn or set()
            drawn |= {p.get("product_id") for p in round_job.result.placements if isinstance(p, dict) and p.get("drawn")}
        if round_job.product_id:
            product = await db.scalar(select(Product).where(Product.id == round_job.product_id).options(*_PRODUCT_LOAD))
            if product is not None and product.id not in seen:
                seen.add(product.id)
                out.append((product, None))
        elif round_job.outfit_id:
            items = (
                await db.execute(
                    select(OutfitItem)
                    .where(OutfitItem.outfit_id == round_job.outfit_id)
                    .options(selectinload(OutfitItem.product).options(*_PRODUCT_LOAD))
                    .order_by(OutfitItem.position)
                )
            ).scalars()
            for item in items:
                if item.product is not None and item.product.id not in seen:
                    seen.add(item.product.id)
                    out.append((item.product, item.slot))
    return out, drawn
