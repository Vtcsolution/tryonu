"""Emails an admin writes in Admin → Send email: who gets them, how they
look, and sending a group one by one in the background.

Members get one only when they kept emails on (the same switch as the daily
email), with a link to stop them; shop owners and the team always do. One
email at a time, a little apart: a mailbox plan (Hostinger's) allows only so
many an hour, and a burst looks like spam to the receiving side."""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.models.admin_email import AdminEmail
from app.models.store import Store
from app.models.user import User

AUDIENCES = ("one", "me", "members", "stores", "team")
# the most one group email may go to; the rest would be over a mailbox plan's daily limit
MAX_PER_SEND = 500
GAP_SECONDS = 1.5


@dataclass(frozen=True)
class Recipient:
    email: str
    name: str | None
    user_id: str | None  # a member who can turn these emails off


def _first(name: str | None) -> str | None:
    return name.split()[0] if name and name.strip() else None


async def recipients(db: AsyncSession, audience: str, *, me: User, address: str | None = None) -> list[Recipient]:
    if audience == "one":
        user = await db.scalar(select(User).where(User.email == (address or "").strip().lower()))
        return [Recipient((address or "").strip(), _first(user.full_name) if user else None, None)]
    if audience == "me":
        return [Recipient(me.email, _first(me.full_name), None)]
    if audience == "members":
        rows = await db.execute(
            select(User).where(
                User.is_active.is_(True), User.email_verified.is_(True), User.notify_email.is_(True),
                User.team_person.is_(False),
            ).order_by(User.created_at)
        )
        return [Recipient(u.email, _first(u.full_name), u.id) for u in rows.scalars()]
    if audience == "team":
        rows = await db.execute(
            select(User).where(User.is_active.is_(True), User.team_person.is_(False), (User.is_team.is_(True)) | (User.is_admin.is_(True)))
        )
        return [Recipient(u.email, _first(u.full_name), None) for u in rows.scalars()]
    if audience == "stores":
        rows = await db.execute(
            select(Store, User).join(User, User.id == Store.owner_user_id).where(Store.status != "rejected")
        )
        seen: dict[str, Recipient] = {}
        for store, owner in rows.all():
            email = (store.contact_email or owner.email or "").strip()
            if email and email.lower() not in seen:
                seen[email.lower()] = Recipient(email, _first(owner.full_name), None)
        return list(seen.values())
    raise ValueError(f"unknown audience {audience}")


_URL = re.compile(r"(https?://[^\s<]+)")


def render(
    subject: str,
    message: str,
    name: str | None,
    *,
    unsubscribe_url: str | None,
    audience: str,
    looks: list[dict] | None = None,
) -> tuple[str, str]:
    """The email as plain text and as a branded page. "{name}" in the message
    becomes the person's first name ("there" when unknown). With `looks`, the
    message is the opening of the trending-looks email (looks_email)."""
    s = get_settings()
    body = message.replace("{name}", name or "there").strip()
    if unsubscribe_url:
        footer = f"You get this because you have a TryOnU account. Stop these emails: {unsubscribe_url}"
    elif audience == "stores":
        footer = f"You get this because you have a store on TryOnU. Questions? Reply to this email or write to {s.SALES_EMAIL}."
    else:
        footer = f"Questions? Reply to this email or write to {s.SUPPORT_EMAIL}."

    paragraphs = "".join(
        "<p style=\"margin:0 0 14px\">"
        + _URL.sub(r'<a href="\1" style="color:#57634f">\1</a>', html.escape(p).replace("\n", "<br>"))
        + "</p>"
        for p in re.split(r"\n\s*\n", body)
        if p.strip()
    )
    footer_html = _URL.sub(r'<a href="\1" style="color:#8a8a80">\1</a>', html.escape(footer))
    if looks is not None:
        from app.services.looks_email import render_looks

        text, page = render_looks(paragraphs, body, looks, footer_html)
        return f"{text}\n\n--\nTryOnU · https://tryonu.app\n{footer}\n", page
    text = f"{body}\n\n--\nTryOnU · https://tryonu.app\n{footer}\n"
    page = (
        "<!doctype html><html><body style=\"margin:0;background:#f6f3ee;font-family:Arial,Helvetica,sans-serif\">"
        "<div style=\"max-width:560px;margin:0 auto;padding:28px 18px\">"
        "<p style=\"margin:0 0 18px;font:bold 20px Georgia,serif;color:#57634f\">TryOnU</p>"
        "<div style=\"background:#ffffff;border:1px solid #e5ddd3;border-radius:16px;padding:24px;"
        f"font-size:15px;line-height:1.55;color:#1c1b17\">{paragraphs}</div>"
        f"<p style=\"margin:18px 4px 0;font-size:12.5px;line-height:1.5;color:#8a8a80\">{footer_html}</p>"
        f"<p style=\"display:none\">{html.escape(subject)}</p>"
        "</div></body></html>"
    )
    return text, page


# group emails being sent now: kept so a send isn't collected halfway
_sending: set[asyncio.Task] = set()


async def send_one(recipient: Recipient, subject: str, message: str, audience: str, looks: list[dict] | None = None) -> None:
    from app.email.registry import get_email_provider
    from app.services.notification_service import unsubscribe_url

    link = unsubscribe_url(recipient.user_id) if recipient.user_id else None
    text, page = render(subject, message, recipient.name, unsubscribe_url=link, audience=audience, looks=looks)
    reply_to = get_settings().SALES_EMAIL if audience == "stores" else None
    await get_email_provider().send(
        to=recipient.email, subject=subject, text_body=text, html_body=page, reply_to=reply_to, unsubscribe_url=link
    )


def send_later(email_id: str, people: list[Recipient], looks: list[dict] | None = None) -> None:
    task = asyncio.create_task(_send_all(email_id, people, GAP_SECONDS, looks))
    _sending.add(task)
    task.add_done_callback(_sending.discard)


async def _send_all(email_id: str, people: list[Recipient], gap: float, looks: list[dict] | None = None) -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        row = await db.get(AdminEmail, email_id)
        if row is None:
            return
        for k, person in enumerate(people):
            try:
                await send_one(person, row.subject, row.message, row.audience, looks)
                row.sent += 1
            except Exception as exc:  # noqa: BLE001 - one bad address doesn't stop the rest
                row.failed += 1
                logger.warning("admin_email_failed", email_id=email_id, error=str(exc)[:200])
            if k % 10 == 9:
                await db.commit()
            if gap and k < len(people) - 1:
                await asyncio.sleep(gap)
        row.status = "done"
        await db.commit()
        logger.info("admin_email_done", email_id=email_id, sent=row.sent, failed=row.failed)


async def wait_for_sending() -> None:
    """Tests: until every group email started is sent."""
    if _sending:
        await asyncio.gather(*list(_sending), return_exceptions=True)
