"""Onboarding category tree + the personalised "For you" feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.core.taxonomy import AUDIENCES, NODES, PARENTS, to_dict
from app.models.preference import UserPreference
from app.schemas.product import LiveProductOut
from app.services.feed_service import for_you, parent_label, sections_for
from app.services.live_search_service import to_live_product_out
from app.services.personalization_service import build_taste_profile

catalog_router = APIRouter(prefix="/catalog", tags=["catalog"])
feed_router = APIRouter(prefix="/feed", tags=["feed"])


@catalog_router.get("/taxonomy")
async def taxonomy():
    return {"audiences": [to_dict(a) for a in AUDIENCES]}


class FeedSection(BaseModel):
    id: str
    label: str
    parent_label: str | None


class FeedItem(LiveProductOut):
    category_id: str


class ForYouResponse(BaseModel):
    sections: list[FeedSection]
    active: str | None
    items: list[FeedItem]


@feed_router.get(
    "/for-you",
    response_model=ForYouResponse,
    dependencies=[Depends(rate_limiter("feed_for_you", limit=60, window_seconds=60))],
)
async def for_you_feed(
    user: CurrentUser,
    db: DbSession,
    node: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=24, ge=1, le=48),
):
    pref = (await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))).scalar_one_or_none()
    target = None
    if node is not None:
        target = NODES.get(node)
        if target is None or PARENTS.get(node) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown category")

    profile = await build_taste_profile(db, user.id)
    entries = await for_you(pref, profile, node=target, limit=limit)
    return ForYouResponse(
        sections=[FeedSection(id=s.id, label=s.label, parent_label=parent_label(s)) for s in sections_for(pref)],
        active=target.id if target else None,
        items=[
            FeedItem(**to_live_product_out(e.result).model_dump(exclude={"search_term"}), search_term=e.node.search, category_id=e.node.id)
            for e in entries
        ],
    )
