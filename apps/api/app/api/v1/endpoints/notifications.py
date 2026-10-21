"""The bell: a member's notifications, marking them read, the daily-email
setting, and phones that want notifications (Web Push)."""

from __future__ import annotations

import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.community import CommunityPost
from app.models.notification import Announcement, Notification, PushSubscription
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services import notification_service as svc
from app.services.storage_service import get_storage

router = APIRouter(prefix="/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/admin/announcements", tags=["admin"])


class ActorOut(BaseModel):
    handle: str | None
    name: str | None
    avatar_url: str | None


class NotificationOut(BaseModel):
    id: str
    kind: str
    text: str
    url: str
    actor: ActorOut | None
    image_url: str | None  # the post it is about, small
    credits: int | None
    read: bool
    created_at: datetime


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int
    next_offset: int | None


async def _unread(db: DbSession, user_id: str) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None)))
        or 0
    )


async def _post_images(db: DbSession, post_ids: set[str]) -> dict[str, str]:
    if not post_ids:
        return {}
    storage = get_storage()
    posts = (await db.execute(select(CommunityPost).where(CommunityPost.id.in_(post_ids)))).scalars().all()
    jobs = {
        j.id: j
        for j in (
            await db.execute(
                select(TryOnJob)
                .where(TryOnJob.id.in_({p.tryon_job_id for p in posts if p.tryon_job_id and not p.media_key}))
                .options(selectinload(TryOnJob.result))
            )
        ).scalars()
    }
    out: dict[str, str] = {}
    for p in posts:
        if p.media_key:
            if p.poster_key or p.media_kind == "image":
                out[p.id] = storage.signed_url(p.poster_key or p.media_key)
        elif (job := jobs.get(p.tryon_job_id)) and job.result:
            out[p.id] = storage.signed_url(job.result.storage_key)
    return out


@router.get("", response_model=NotificationsOut)
async def list_notifications(me: CurrentUser, db: DbSession, offset: int = 0, limit: int = 20):
    limit = min(max(limit, 1), 50)
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == me.id)
            .order_by(Notification.created_at.desc())
            .offset(max(offset, 0))
            .limit(limit + 1)
        )
    ).scalars().all()
    page = list(rows[:limit])
    actors = {
        u.id: u for u in (await db.execute(select(User).where(User.id.in_({n.actor_id for n in page if n.actor_id})))).scalars()
    }
    images = await _post_images(db, {n.post_id for n in page if n.post_id})
    items = []
    for n in page:
        actor = actors.get(n.actor_id) if n.actor_id else None
        items.append(
            NotificationOut(
                id=n.id,
                kind=n.kind,
                text=svc.words(n, actor),
                url=svc.link(n, actor),
                actor=ActorOut(handle=actor.handle, name=actor.full_name, avatar_url=actor.avatar_url) if actor else None,
                image_url=images.get(n.post_id) if n.post_id else None,
                credits=n.credits,
                read=n.read_at is not None,
                created_at=n.created_at,
            )
        )
    return NotificationsOut(items=items, unread=await _unread(db, me.id), next_offset=offset + limit if len(rows) > limit else None)


@router.get("/unread-count")
async def unread_count(me: CurrentUser, db: DbSession):
    return {"unread": await _unread(db, me.id)}


@router.post("/read-all")
async def read_all(me: CurrentUser, db: DbSession):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == me.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"unread": 0}


@router.post("/{notification_id}/read")
async def read_one(notification_id: str, me: CurrentUser, db: DbSession):
    note = await db.get(Notification, notification_id)
    if note is None or note.user_id != me.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        await db.commit()
    return {"unread": await _unread(db, me.id)}


# ------------------------------------------------------------------ settings


class SettingsOut(BaseModel):
    email: bool
    push_key: str | None  # the VAPID public key phones subscribe with; None while phone notifications aren't set up
    phones: int


class SettingsIn(BaseModel):
    email: bool


async def _settings(db: DbSession, me: User) -> SettingsOut:
    phones = await db.scalar(select(func.count()).select_from(PushSubscription).where(PushSubscription.user_id == me.id))
    return SettingsOut(email=me.notify_email, push_key=get_settings().VAPID_PUBLIC_KEY if svc.push_ready() else None, phones=int(phones or 0))


@router.get("/settings", response_model=SettingsOut)
async def get_notification_settings(me: CurrentUser, db: DbSession):
    return await _settings(db, me)


@router.patch("/settings", response_model=SettingsOut)
async def update_notification_settings(payload: SettingsIn, me: CurrentUser, db: DbSession):
    me.notify_email = payload.email
    await db.commit()
    return await _settings(db, me)


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=255)
    auth: str = Field(min_length=8, max_length=255)


class SubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1024)
    keys: PushKeys


@router.post(
    "/push",
    response_model=SettingsOut,
    dependencies=[Depends(rate_limiter("push_subscribe", limit=20, window_seconds=3600))],
)
async def subscribe_push(payload: SubscribeIn, request: Request, me: CurrentUser, db: DbSession):
    """This phone or browser wants notifications."""
    if not svc.push_ready():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone notifications aren't switched on yet.")
    if not payload.endpoint.startswith("https://"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That isn't a notification address.")
    sub = await db.scalar(select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint))
    if sub is None:
        sub = PushSubscription(endpoint=payload.endpoint, user_id=me.id, p256dh=payload.keys.p256dh, auth=payload.keys.auth)
        db.add(sub)
    else:  # the same phone, maybe now signed in as someone else
        sub.user_id, sub.p256dh, sub.auth = me.id, payload.keys.p256dh, payload.keys.auth
    sub.user_agent = (request.headers.get("user-agent") or "")[:300] or None
    await db.commit()
    return await _settings(db, me)


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1024)


@router.post("/push/remove", response_model=SettingsOut)
async def unsubscribe_push(payload: UnsubscribeIn, me: CurrentUser, db: DbSession):
    await db.execute(delete(PushSubscription).where(PushSubscription.endpoint == payload.endpoint, PushSubscription.user_id == me.id))
    await db.commit()
    return await _settings(db, me)


@router.get("/unsubscribe", response_class=HTMLResponse, include_in_schema=False)
async def unsubscribe_email(u: str, t: str, db: DbSession):
    """The link at the bottom of the daily email: no sign-in needed."""
    user = await db.get(User, u)
    if user is None or not hmac.compare_digest(t, svc.unsubscribe_token(u)):
        return HTMLResponse(_page("This link doesn't work anymore", "You can turn the emails off in your notification settings."), status_code=400)
    user.notify_email = False
    await db.commit()
    return HTMLResponse(_page("Done: no more daily emails", "You'll still see your notifications on TryOnU. You can turn the emails back on any time."))


def _page(title: str, text: str) -> str:
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    return (
        "<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{title} · TryOnU</title>"
        "<body style='font-family:system-ui,sans-serif;background:#fbfaf6;color:#1d1d1a;display:grid;place-items:center;min-height:90vh;margin:0;padding:16px'>"
        f"<div style='max-width:440px;text-align:center'><h1 style='font-size:24px'>{title}</h1>"
        f"<p style='font-size:17px;line-height:1.5;color:#55554d'>{text}</p>"
        f"<p><a href='{site}/notifications' style='color:#3b463c;font-weight:600'>Notification settings</a></p></div>"
    )


# ------------------------------------------------------------------ admin: a message to every member


class AnnouncementIn(BaseModel):
    text: str = Field(min_length=3, max_length=280)
    # a TryOnU page ("/community/challenges" or "https://tryonu.app/pricing"); empty = the bell
    url: str | None = Field(default=None, max_length=300)


class AnnouncementOut(BaseModel):
    id: str
    text: str
    url: str | None
    sent_to: int
    created_at: datetime


class AnnouncementsOut(BaseModel):
    members: int
    items: list[AnnouncementOut]


def _members():
    return select(User.id).where(User.is_active.is_(True))


def _tryonu_page(url: str | None) -> str | None:
    """Only TryOnU's own pages: a path, or a full tryonu.app link made a path."""
    url = (url or "").strip()
    if not url:
        return None
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    for prefix in (site, "https://tryonu.app", "https://www.tryonu.app"):
        if url.startswith(prefix):
            url = url[len(prefix):] or "/"
            break
    if not url.startswith("/") or url.startswith("//"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The link must be a TryOnU page, e.g. /pricing")
    return url


@admin_router.get("", response_model=AnnouncementsOut)
async def list_announcements(_: AdminUser, db: DbSession):
    members = await db.scalar(select(func.count()).select_from(_members().subquery())) or 0
    rows = (await db.execute(select(Announcement).order_by(Announcement.created_at.desc()).limit(50))).scalars()
    return AnnouncementsOut(
        members=members,
        items=[AnnouncementOut(id=a.id, text=a.text, url=a.url, sent_to=a.sent_to, created_at=a.created_at) for a in rows],
    )


@admin_router.post("", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
async def send_announcement(payload: AnnouncementIn, admin: AdminUser, db: DbSession):
    """Every active member gets it in the bell, and on their phone when they said yes."""
    from app.db.base import new_uuid
    from sqlalchemy import insert

    text = " ".join(payload.text.split())
    url = _tryonu_page(payload.url)
    members = (await db.execute(_members())).scalars().all()
    ids: list[str] = []
    for start in range(0, len(members), 1000):
        rows = [
            {"id": new_uuid(), "user_id": uid, "kind": "announcement", "text": text, "url": url}
            for uid in members[start : start + 1000]
        ]
        if rows:
            await db.execute(insert(Notification), rows)
            ids.extend(r["id"] for r in rows)
    note = Announcement(text=text, url=url, sent_to=len(ids), created_by_id=admin.id)
    db.add(note)
    db.sync_session.info.setdefault(svc.PENDING_KEY, []).extend(ids)  # phone notifications go out once saved
    await db.commit()
    await db.refresh(note)
    return AnnouncementOut(id=note.id, text=note.text, url=note.url, sent_to=note.sent_to, created_at=note.created_at)
