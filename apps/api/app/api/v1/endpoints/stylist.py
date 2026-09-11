from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.outfit import Outfit, OutfitItem
from app.models.product import Product
from app.models.stylist import StylistRequest
from app.schemas.stylist import StylistAskRequest, StylistAskResponse
from app.services.stylist_service import ask_stylist

router = APIRouter(prefix="/stylist", tags=["stylist"])


@router.post(
    "/ask",
    response_model=StylistAskResponse,
    dependencies=[Depends(rate_limiter("stylist_ask", limit=20, window_seconds=3600))],
)
async def ask(payload: StylistAskRequest, user: CurrentUser, db: DbSession):
    request_row = await ask_stylist(db, user_id=user.id, req=payload)

    products: list[Product] = []
    if request_row.recommended_product_ids:
        result = await db.execute(
            select(Product)
            .where(Product.id.in_(request_row.recommended_product_ids))
            .options(selectinload(Product.images), selectinload(Product.retailer))
        )
        by_id = {p.id: p for p in result.scalars().all()}
        products = [by_id[pid] for pid in request_row.recommended_product_ids if pid in by_id]

    outfit = None
    if request_row.recommended_outfit_id:
        result = await db.execute(
            select(Outfit)
            .where(Outfit.id == request_row.recommended_outfit_id)
            .options(
                selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.images),
                selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.retailer),
            )
        )
        outfit = result.scalar_one_or_none()

    return StylistAskResponse(
        id=request_row.id,
        summary=request_row.response_summary or "",
        products=products,
        outfit=outfit,
        created_at=request_row.created_at,
    )


@router.get("/history", response_model=list[StylistAskResponse])
async def history(user: CurrentUser, db: DbSession, limit: int = 20):
    result = await db.execute(
        select(StylistRequest)
        .where(StylistRequest.user_id == user.id)
        .order_by(StylistRequest.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    out: list[StylistAskResponse] = []
    for row in rows:
        products = []
        if row.recommended_product_ids:
            pr = await db.execute(
                select(Product)
                .where(Product.id.in_(row.recommended_product_ids))
                .options(selectinload(Product.images), selectinload(Product.retailer))
            )
            by_id = {p.id: p for p in pr.scalars().all()}
            products = [by_id[pid] for pid in row.recommended_product_ids if pid in by_id]
        out.append(
            StylistAskResponse(
                id=row.id, summary=row.response_summary or "", products=products, outfit=None, created_at=row.created_at
            )
        )
    return out
