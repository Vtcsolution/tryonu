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


async def copy_look(db: AsyncSession, user_id: str, job: TryOnJob, *, include_hidden: bool = False) -> tuple[str | None, str | None]:
    """Another person's look, ready for this person to try on with their own
    photo: (outfit_id, None) for several products, (None, product_id) for one.
    include_hidden: also products only reachable through a look (a page tried on
    with the browser extension); they become part of an outfit, which never
    needs them to be in search. Returns (None, None) when nothing is left."""
    from app.models.outfit import Outfit
    from app.services.outfit_compatibility import score_outfit
    from app.services.outfit_slots import slot_for

    pairs, _ = await look_products(db, job)
    pairs = [(p, slot) for p, slot in pairs if p.is_active or include_hidden][:10]
    if not pairs:
        return None, None
    if len(pairs) == 1 and pairs[0][0].is_active:
        return None, pairs[0][0].id
    slots = [slot if slot not in (None, OutfitSlot.OTHER) else slot_for(p.name) for p, slot in pairs]
    products = [p for p, _ in pairs]
    coherence = score_outfit(products, slots)
    outfit = Outfit(user_id=user_id, name="Shared look", compatibility_score=coherence.overall, compatibility_notes=coherence.notes or None)
    db.add(outfit)
    await db.flush()
    for pos, (product, slot) in enumerate(zip(products, slots)):
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()
    return outfit.id, None
