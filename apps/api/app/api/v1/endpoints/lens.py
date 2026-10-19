"""Find the look: a member uploads a photo or screenshot (or picks one of
their try-on looks, or a community photo) and gets the shop products in it,
exact matches first and the nearest alternatives after.
See services/visual_search_service.py for how."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.models.community import CommunityPost
from app.models.enums import JobStatus
from app.models.tryon import TryOnJob
from app.models.user import User
from app.models.visual_search import VisualSearch
from app.schemas.product import LiveProductOut
from app.services import visual_search_service as lens
from app.services.storage_service import get_storage

router = APIRouter(prefix="/lens", tags=["lens"])


class LensMatchOut(BaseModel):
    product: LiveProductOut
    score: int
    match: str  # exact | close | similar


class LensItemOut(BaseModel):
    label: str
    category: str
    query: str
    color: str | None = None
    details: str | None = None
    box: list[float]
    matches: list[LensMatchOut]


class LensOut(BaseModel):
    id: str
    image_url: str
    width: int
    height: int
    summary: str | None
    items: list[LensItemOut]
    created_at: datetime


class LensSummaryOut(BaseModel):
    id: str
    image_url: str
    summary: str | None
    items: int
    created_at: datetime


def _out(s: VisualSearch) -> LensOut:
    return LensOut(
        id=s.id, image_url=get_storage().signed_url(s.image_key), width=s.width, height=s.height, summary=s.summary,
        items=[LensItemOut(**item) for item in (s.result or {}).get("items", [])], created_at=s.created_at,
    )


async def _check_allowance(db: DbSession, me: User) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    used = await db.scalar(select(func.count()).select_from(VisualSearch).where(VisualSearch.user_id == me.id, VisualSearch.created_at >= since))
    if int(used or 0) >= get_settings().LENS_DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="You've used today's photo searches. Please try again tomorrow."
        )


async def _run(db: DbSession, me: User, raw: bytes, source: str) -> LensOut:
    await _check_allowance(db, me)
    photo, width, height = lens.prepare_photo(raw)
    try:
        result = await lens.find_the_look(photo)
    except lens.LensError as exc:
        logger.warning("lens_failed", user_id=me.id, error=str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo search couldn't look at this picture right now. Please try again in a moment.",
        ) from exc
    key = f"lens/{me.id}/{secrets.token_urlsafe(12)}.jpg"
    get_storage().put(key, photo, "image/jpeg")
    search = VisualSearch(
        user_id=me.id, image_key=key, width=width, height=height, source=source, summary=result.get("summary") or None, result=result
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)
    return _out(search)


@router.post("", response_model=LensOut, dependencies=[Depends(rate_limiter("lens", limit=20, window_seconds=3600))])
async def search_by_photo(me: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    """A photo or screenshot of an outfit: the products in it."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please choose a photo.")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="That photo is too big. Please use one under 15 MB.")
    return await _run(db, me, raw, "upload")


class FromIn(BaseModel):
    tryon_job_id: str | None = None  # one of my try-on looks
    post_id: str | None = None  # a photo or look in the community


@router.post("/from", response_model=LensOut, dependencies=[Depends(rate_limiter("lens", limit=20, window_seconds=3600))])
async def search_from(payload: FromIn, me: CurrentUser, db: DbSession):
    """The products in one of my looks, or in a community post's picture."""
    storage = get_storage()
    if payload.tryon_job_id:
        job = await db.scalar(select(TryOnJob).where(TryOnJob.id == payload.tryon_job_id).options(selectinload(TryOnJob.result)))
        if job is None or job.user_id != me.id or job.status != JobStatus.COMPLETED or job.result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Look not found")
        return await _run(db, me, storage.read(job.result.storage_key), "look")
    if payload.post_id:
        post = await db.get(CommunityPost, payload.post_id)
        if post is None or post.is_hidden:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        if post.media_key:
            key = post.poster_key if post.media_kind == "video" else post.media_key
            if not key:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This video has no picture to search with.")
        else:
            job = await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))
            if job is None or job.result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
            key = job.result.storage_key
        return await _run(db, me, storage.read(key), "post")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a photo, a look or a post.")


@router.get("", response_model=list[LensSummaryOut])
async def my_searches(me: CurrentUser, db: DbSession, limit: int = 12):
    rows = (
        await db.execute(
            select(VisualSearch).where(VisualSearch.user_id == me.id).order_by(VisualSearch.created_at.desc()).limit(min(max(limit, 1), 30))
        )
    ).scalars()
    storage = get_storage()
    return [
        LensSummaryOut(
            id=s.id, image_url=storage.signed_url(s.image_key), summary=s.summary, items=len((s.result or {}).get("items", [])),
            created_at=s.created_at,
        )
        for s in rows
    ]


async def _mine(db: DbSession, search_id: str, me: User) -> VisualSearch:
    search = await db.get(VisualSearch, search_id)
    if search is None or search.user_id != me.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return search


@router.get("/{search_id}", response_model=LensOut)
async def get_search(search_id: str, me: CurrentUser, db: DbSession):
    return _out(await _mine(db, search_id, me))


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search(search_id: str, me: CurrentUser, db: DbSession):
    search = await _mine(db, search_id, me)
    key = search.image_key
    await db.delete(search)
    await db.commit()
    try:
        get_storage().delete(key)
    except Exception:  # noqa: BLE001 — a leftover file is harmless
        pass
