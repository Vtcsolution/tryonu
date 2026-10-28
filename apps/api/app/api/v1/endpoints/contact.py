"""The website's Contact page: anyone can write; admins read the messages in
Admin → Messages and also get them by email (when email is set up)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.deps import AdminUser, DbSession, OptionalUser
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.email.registry import get_email_provider
from app.models.contact import ContactMessage
from app.models.user import User
from app.services import whatsapp

router = APIRouter(tags=["contact"])

TOPICS = {
    "general": "General question",
    "tryon": "Try-ons, credits and payments",
    "store": "Selling on TryOnU (stores)",
    "developer": "Developer API and plugins",
    "partnership": "Partnerships and press",
    "privacy": "Privacy and my data",
}


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    topic: str = Field(default="general", max_length=40)
    message: str = Field(min_length=10, max_length=5000)


class ContactMessageOut(BaseModel):
    id: str
    name: str
    email: str
    topic: str
    topic_label: str
    message: str
    created_at: datetime
    handled_at: datetime | None


def _out(m: ContactMessage) -> ContactMessageOut:
    return ContactMessageOut(
        id=m.id, name=m.name, email=m.email, topic=m.topic, topic_label=TOPICS.get(m.topic, m.topic),
        message=m.message, created_at=m.created_at, handled_at=m.handled_at,
    )


@router.get("/contact/info")
async def contact_info():
    """How to reach TryOnU besides the form: the help WhatsApp number, if set,
    and the email addresses."""
    s = get_settings()
    try:
        number = whatsapp.normalize(s.SUPPORT_WHATSAPP, "PK")
    except ValueError:
        number = None
    return {"whatsapp": number, "support": s.SUPPORT_EMAIL, "sales": s.SALES_EMAIL, "billing": s.BILLING_EMAIL}


@router.post(
    "/contact",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("contact_message", limit=5, window_seconds=3600))],
)
async def send_message(payload: ContactIn, db: DbSession, user: OptionalUser):
    topic = payload.topic if payload.topic in TOPICS else "general"
    msg = ContactMessage(
        name=payload.name.strip(),
        email=str(payload.email),
        topic=topic,
        message=payload.message.strip(),
        user_id=user.id if user else None,
    )
    db.add(msg)
    await db.commit()

    # also by email to the help inbox and the admins, a reply going straight
    # to the sender; the message is saved either way
    admins = (await db.execute(select(User.email).where(User.is_admin.is_(True)))).scalars().all()
    inbox = get_settings().SUPPORT_EMAIL
    for to in dict.fromkeys([inbox, *admins] if inbox else admins):
        try:
            await get_email_provider().send(
                to=to,
                subject=f"TryOnU contact: {TOPICS[topic]} from {msg.name}",
                text_body=f"From: {msg.name} <{msg.email}>\nTopic: {TOPICS[topic]}\n\n{msg.message}\n\nReply to them at {msg.email}.",
                reply_to=msg.email,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("contact_email_failed", error=str(exc)[:200])
    return {"detail": "Thanks, we got your message and will reply by email."}


@router.get("/admin/messages", response_model=list[ContactMessageOut])
async def list_messages(_: AdminUser, db: DbSession, show: str = "open"):
    query = select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(300)
    if show == "open":
        query = query.where(ContactMessage.handled_at.is_(None))
    return [_out(m) for m in (await db.execute(query)).scalars()]


@router.get("/admin/messages/count")
async def open_count(_: AdminUser, db: DbSession):
    count = await db.scalar(select(func.count()).select_from(ContactMessage).where(ContactMessage.handled_at.is_(None)))
    return {"open": int(count or 0)}


@router.post("/admin/messages/{message_id}/handled", response_model=ContactMessageOut)
async def mark_handled(message_id: str, _: AdminUser, db: DbSession, undo: bool = False):
    msg = await db.get(ContactMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    msg.handled_at = None if undo else datetime.now(timezone.utc)
    await db.commit()
    return _out(msg)
