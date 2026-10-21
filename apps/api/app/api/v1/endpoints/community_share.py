"""What a shared community post shows on LinkedIn, WhatsApp, Facebook, X…

Those sites read the link's page without signing in, so the post page asks
here for its title, words and picture (only posts anyone in the community
may see: not hidden, not from a blocked member). The share card itself is
drawn by the website from these."""

from __future__ import annotations

import asyncio
import io

from fastapi import APIRouter, Depends, HTTPException, Response, status
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession
from app.core.rate_limit import rate_limiter
from app.models.community import CommunityPost
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services.look_products import look_products
from app.services.price_alert_service import price_text
from app.services.storage_service import get_storage

router = APIRouter(
    prefix="/community/share",
    tags=["community"],
    dependencies=[Depends(rate_limiter("community_share_preview", limit=600, window_seconds=3600))],
)

_PHOTO_WIDTH = 900


class ShareProductOut(BaseModel):
    name: str
    price: str | None
    image_url: str | None


class SharePreviewOut(BaseModel):
    id: str
    author_handle: str
    author_name: str | None
    caption: str | None
    media_kind: str
    has_photo: bool
    products: list[ShareProductOut]


async def _shared_post(db: DbSession, post_id: str) -> tuple[CommunityPost, User]:
    row = (
        await db.execute(select(CommunityPost, User).join(User, User.id == CommunityPost.user_id).where(CommunityPost.id == post_id))
    ).first()
    if row is None or row[0].is_hidden or row[1].community_banned_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return row[0], row[1]


async def _job(db: DbSession, post: CommunityPost) -> TryOnJob | None:
    if not post.tryon_job_id:
        return None
    return await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))


def _photo_key(post: CommunityPost, job: TryOnJob | None) -> str | None:
    if post.media_key:
        return post.media_key if post.media_kind == "image" else post.poster_key  # a video: its cover picture
    return job.result.storage_key if job and job.result else None


@router.get("/{post_id}", response_model=SharePreviewOut)
async def share_preview(post_id: str, db: DbSession):
    post, author = await _shared_post(db, post_id)
    job = await _job(db, post)
    products: list[ShareProductOut] = []
    if job is not None and job.result is not None:
        pairs, _ = await look_products(db, job)
        products = [
            ShareProductOut(
                name=p.name,
                price=price_text(p.price_cents, p.currency) if p.price_cents else None,
                image_url=p.primary_image_url,
            )
            for p, _slot in pairs
        ]
    return SharePreviewOut(
        id=post.id,
        author_handle=author.handle or "member",
        author_name=author.full_name,
        caption=post.caption,
        media_kind=post.media_kind,
        has_photo=_photo_key(post, job) is not None,
        products=products,
    )


def _jpeg(data: bytes, width: int) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img.thumbnail((width, width * 2))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            flat = Image.new("RGB", img.size, (255, 255, 255))
            flat.paste(img, mask=img.split()[-1])
            img = flat
        elif img.mode != "RGB":
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()


@router.get("/{post_id}/photo.jpg")
async def share_photo(post_id: str, db: DbSession):
    """The post's picture as a JPEG, for its share card."""
    post, _ = await _shared_post(db, post_id)
    key = _photo_key(post, await _job(db, post))
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This post has no picture")
    try:
        raw = await asyncio.to_thread(get_storage().read, key)
        body = await asyncio.to_thread(_jpeg, raw, _PHOTO_WIDTH)
    except Exception as exc:  # noqa: BLE001 — a missing picture means the plain TryOnU card, never an error page
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Picture not available") from exc
    return Response(content=body, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})
