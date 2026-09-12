from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.outfit import Outfit, OutfitItem
from app.models.product import Product
from app.models.stylist import StylistRequest
from app.schemas.product import ProductOut
from app.schemas.stylist import StylistAskRequest, StylistAskResponse
from app.services import history_service
from app.services.similarity_service import find_cheaper, find_similar
from app.services.stylist_service import ask_stylist

router = APIRouter(prefix="/stylist", tags=["stylist"])

_stylist_rate_limit = Depends(rate_limiter("stylist_ask", limit=20, window_seconds=3600))


async def _run_stylist_request(payload: StylistAskRequest, user_id: str, db: DbSession) -> StylistAskResponse:
    request_row = await ask_stylist(db, user_id=user_id, req=payload)
    return await _to_response(db, request_row)


async def _to_response(db: DbSession, request_row: StylistRequest) -> StylistAskResponse:
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
        prompt=request_row.prompt,
        summary=request_row.response_summary or "",
        products=products,
        outfit=outfit,
        created_at=request_row.created_at,
    )


@router.post("/ask", response_model=StylistAskResponse, dependencies=[_stylist_rate_limit])
async def ask(payload: StylistAskRequest, user: CurrentUser, db: DbSession):
    """Kept as the original/canonical route — the frontend calls this one.
    /chat, /recommend and /outfit below are the same underlying behavior
    under the route names from the spec; nothing is duplicated."""
    return await _run_stylist_request(payload, user.id, db)


@router.post("/chat", response_model=StylistAskResponse, dependencies=[_stylist_rate_limit])
async def chat(payload: StylistAskRequest, user: CurrentUser, db: DbSession):
    """Conversational entry point — same engine as /ask. A prompt like
    "I need a smart casual outfit for dinner under $200" goes in; only
    real database products come back."""
    return await _run_stylist_request(payload, user.id, db)


@router.post("/recommend", response_model=StylistAskResponse, dependencies=[_stylist_rate_limit])
async def recommend(payload: StylistAskRequest, user: CurrentUser, db: DbSession):
    """Product-recommendation entry point — same engine as /ask."""
    return await _run_stylist_request(payload, user.id, db)


@router.post("/outfit", response_model=StylistAskResponse, dependencies=[_stylist_rate_limit])
async def outfit(payload: StylistAskRequest, user: CurrentUser, db: DbSession):
    """Outfit-generation entry point. Set max_items > 1 to get a full
    outfit back (an Outfit row is created automatically once more than one
    real product is selected — see services/stylist_service.py)."""
    return await _run_stylist_request(payload, user.id, db)


async def _load_active_product(db: DbSession, product_id: str) -> Product:
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.is_active.is_(True))
        .options(selectinload(Product.images), selectinload(Product.retailer), selectinload(Product.category))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("/similar/{product_id}", response_model=list[ProductOut])
async def similar(product_id: str, user: CurrentUser, db: DbSession, limit: int = 6):
    """Deterministic catalog lookup, not an LLM call — same category,
    ranked by embedding similarity. Nothing to invent: it's a plain query."""
    product = await _load_active_product(db, product_id)
    results = await find_similar(db, product, limit=limit)
    await history_service.log_product_view(db, user_id=user.id, product_id=product.id, source="find_similar")
    return results


@router.get("/cheaper/{product_id}", response_model=list[ProductOut])
async def cheaper(product_id: str, user: CurrentUser, db: DbSession, limit: int = 6):
    product = await _load_active_product(db, product_id)
    results = await find_cheaper(db, product, limit=limit)
    await history_service.log_product_view(db, user_id=user.id, product_id=product.id, source="find_cheaper")
    return results


@router.get("/history", response_model=list[StylistAskResponse])
async def history(user: CurrentUser, db: DbSession, limit: int = 20):
    result = await db.execute(
        select(StylistRequest)
        .where(StylistRequest.user_id == user.id)
        .order_by(StylistRequest.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [await _to_response(db, row) for row in rows]
