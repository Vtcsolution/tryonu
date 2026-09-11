from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    affiliate,
    auth,
    credits,
    outfits,
    photos,
    products,
    search,
    stylist,
    tryon,
    users,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(photos.router)
api_router.include_router(credits.router)
api_router.include_router(products.router)
api_router.include_router(search.router)
api_router.include_router(tryon.router)
api_router.include_router(outfits.router)
api_router.include_router(stylist.router)
api_router.include_router(affiliate.router)
api_router.include_router(webhooks.router)
api_router.include_router(admin.router)
