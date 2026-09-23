"""The shopper's own saved / favourited / purchased products.

Only products someone actually interacted with live here — never a
retailer's catalogue. Each row is a snapshot taken at that moment, so the
list still shows what they saved after the retailer changes or removes
the listing, and the affiliate link saved with it keeps earning whenever
they open it again.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.core.deps import CurrentUser, DbSession
from app.models.enums import AffiliateSource, SavedProductStatus
from app.schemas.common import Page
from app.schemas.saved_product import SaveProductRequest, SavedProductOut, UpdateSavedProductRequest
from app.services import saved_product_service as service
from app.services.affiliate_service import record_saved_click

router = APIRouter(prefix="/saved-products", tags=["saved-products"])


@router.post("", response_model=SavedProductOut, status_code=status.HTTP_201_CREATED)
async def save_product(payload: SaveProductRequest, user: CurrentUser, db: DbSession):
    """Save, favourite or mark as purchased. A live result is re-fetched
    from the retailer first, so the price and affiliate link written down
    are the retailer's, not the client's."""
    try:
        saved = await service.save_product(
            db,
            user_id=user.id,
            status=payload.status,
            product_id=payload.product_id,
            retailer_slug=payload.retailer_slug,
            retailer_product_id=payload.retailer_product_id,
            query=payload.query,
        )
    except service.ProductGone as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return saved


@router.get("", response_model=Page[SavedProductOut])
async def list_saved_products(
    user: CurrentUser,
    db: DbSession,
    status_filter: SavedProductStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=100),
    offset: int = 0,
):
    items, total = await service.list_saved(
        db, user_id=user.id, status=status_filter, limit=limit, offset=offset
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.patch("/{saved_id}", response_model=SavedProductOut)
async def update_saved_product(
    saved_id: str, payload: UpdateSavedProductRequest, user: CurrentUser, db: DbSession
):
    saved = await service.get_saved(db, user_id=user.id, saved_id=saved_id)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in your saved products")
    saved.status = payload.status
    await db.commit()
    await db.refresh(saved)
    return saved


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_product(saved_id: str, user: CurrentUser, db: DbSession):
    saved = await service.get_saved(db, user_id=user.id, saved_id=saved_id)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in your saved products")
    await db.delete(saved)
    await db.commit()


@router.get("/{saved_id}/go")
async def open_saved_product(saved_id: str, request: Request, user: CurrentUser, db: DbSession):
    """Opening a saved product goes through here so the affiliate link
    stays attached however long ago it was saved — and the click is
    recorded, as it is for any other shop-now link."""
    saved = await service.get_saved(db, user_id=user.id, saved_id=saved_id)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in your saved products")
    await record_saved_click(db, request, user=user, saved=saved, source=AffiliateSource.SAVED)
    return RedirectResponse(saved.affiliate_url, status_code=status.HTTP_302_FOUND)
