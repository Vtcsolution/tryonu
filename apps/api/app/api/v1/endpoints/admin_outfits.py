"""Admin → All outfits: every finished try-on picture, from shoppers and
the team, newest first, with who made it and whether it is a Ready look yet."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.deps import AdminUser, DbSession
from app.models.community import CommunityPost
from app.models.enums import JobStatus
from app.models.outfit import Outfit
from app.models.ready_look import ReadyLook
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services.storage_service import get_storage

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminOutfitOut(BaseModel):
    id: str
    image_url: str
    user_email: str | None
    user_name: str | None
    is_team: bool
    what: str  # "Outfit · 6 pieces" or the product's name
    created_at: datetime
    ready_look_id: str | None
    community_posts: int


class AdminOutfitsOut(BaseModel):
    items: list[AdminOutfitOut]
    total: int
    members: int
    team: int


def _team_filter():
    return or_(User.is_team.is_(True), User.is_admin.is_(True))


@router.get("/outfits", response_model=AdminOutfitsOut)
async def all_outfits(
    _: AdminUser,
    db: DbSession,
    who: str = Query(default="all", pattern="^(all|members|team)$"),
    q: str | None = None,
    limit: int = Query(default=24, ge=1, le=60),
    offset: int = Query(default=0, ge=0),
):
    base = (
        select(TryOnJob)
        .join(User, User.id == TryOnJob.user_id)
        .where(TryOnJob.status == JobStatus.COMPLETED)
    )
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        base = base.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    members = int(await db.scalar(select(func.count()).select_from(base.where(~_team_filter()).subquery())) or 0)
    team = int(await db.scalar(select(func.count()).select_from(base.where(_team_filter()).subquery())) or 0)
    if who == "members":
        base = base.where(~_team_filter())
    elif who == "team":
        base = base.where(_team_filter())
    total = {"all": members + team, "members": members, "team": team}[who]
    jobs = (
        await db.execute(
            base.options(
                selectinload(TryOnJob.result),
                selectinload(TryOnJob.user),
                selectinload(TryOnJob.product),
                selectinload(TryOnJob.outfit).selectinload(Outfit.items),
            )
            .order_by(TryOnJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    ids = [j.id for j in jobs]
    looks = dict((await db.execute(select(ReadyLook.tryon_job_id, ReadyLook.id).where(ReadyLook.tryon_job_id.in_(ids or [""])))).all())
    posts = dict(
        (
            await db.execute(
                select(CommunityPost.tryon_job_id, func.count(CommunityPost.id))
                .where(CommunityPost.tryon_job_id.in_(ids or [""]))
                .group_by(CommunityPost.tryon_job_id)
            )
        ).all()
    )
    storage = get_storage()
    items = []
    for job in jobs:
        if job.result is None:
            continue
        if job.outfit is not None:
            what = f"Outfit · {len(job.outfit.items)} pieces"
        elif job.product is not None:
            what = job.product.name
        else:
            what = "Own item"
        items.append(
            AdminOutfitOut(
                id=job.id,
                image_url=storage.signed_url(job.result.storage_key),
                user_email=job.user.email if job.user else None,
                user_name=job.user.full_name if job.user else None,
                is_team=bool(job.user and (job.user.is_team or job.user.is_admin)),
                what=what[:140],
                created_at=job.created_at,
                ready_look_id=looks.get(job.id),
                community_posts=int(posts.get(job.id, 0)),
            )
        )
    return AdminOutfitsOut(items=items, total=total, members=members, team=team)
