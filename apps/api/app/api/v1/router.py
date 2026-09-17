from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    admin_controls,
    admin_settings,
    admin_rakuten,
    affiliate,
    analytics,
    auth,
    credits,
    outfits,
    photos,
    products,
    search,
    stylist,
    subscriptions,
    tryon,
    users,
    wardrobe,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(photos.router)
api_router.include_router(credits.router)
api_router.include_router(subscriptions.router)
api_router.include_router(wardrobe.router)
api_router.include_router(products.router)
api_router.include_router(search.router)
api_router.include_router(tryon.router)
api_router.include_router(outfits.router)
api_router.include_router(stylist.router)
api_router.include_router(affiliate.router)
api_router.include_router(analytics.router)
api_router.include_router(analytics.admin_router)
api_router.include_router(webhooks.router)
api_router.include_router(admin.router)
api_router.include_router(admin_controls.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_rakuten.router)
