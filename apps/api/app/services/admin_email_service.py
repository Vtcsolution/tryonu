"""Emails an admin writes in Admin → Send email: who gets them, how they
look, and the queue that sends a group out slowly.

The admin only types words. Links are added from the words themselves
("Ready looks", "try on", "community"...) and, for the smart email, Ready
looks that fit the message are picked and shown with their pictures.

Members get one only when they kept emails on (the same switch as the daily
email), with a link to stop them; shop owners and the team always do.

A group email is saved with its list of people and sent one by one by
queue_forever, EMAIL_PER_HOUR an hour and never more than EMAIL_PER_DAY a day
(shared with the daily email), over one kept-open mailbox sign-in. When the
mail server says "slow down" the email pauses for an hour and goes on by
itself; it also picks up where it was after a restart. Bursts and a fresh
sign-in per email are what get a Hostinger mailbox blocked."""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.models.admin_email import AdminEmail
from app.models.store import Store
from app.models.user import User
from app.services import email_budget

AUDIENCES = ("one", "me", "members", "stores", "team")
# the most one group email may go to (it is spread over as many days as it needs)
MAX_PER_SEND = 5000
PAUSE_AFTER_REFUSAL = timedelta(hours=1)
SITE = "https://tryonu.app"


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
            select(User).where(User.is_active.is_(True), User.team_person.is_(False), or_(User.is_team.is_(True), User.is_admin.is_(True)))
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


# ------------------------------------------------------------------ links from words

_URL = re.compile(r"(https?://[^\s<]+)")
_A_TAG = re.compile(r"(<a\b[^>]*>.*?</a>)", re.S)
# words in a message that become links to the page they name (first time only)
_PHRASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(ready looks?)\b", re.I), "/looks"),
    (re.compile(r"\b(find by photo|search by photo)\b", re.I), "/find-look"),
    (re.compile(r"\b(ai stylist|stylist)\b", re.I), "/stylist"),
    (re.compile(r"\b(style challenges?|challenges?)\b", re.I), "/community/challenges"),
    (re.compile(r"\b(community)\b", re.I), "/community"),
    (re.compile(r"\b(try (?:it|them|this|these|your look)? ?on|try-on|try on)\b", re.I), "/try"),
    (re.compile(r"\b(pricing|credit packs?|credits)\b", re.I), "/pricing"),
    (re.compile(r"\b(invite (?:a )?friends?|invite & earn)\b", re.I), "/earn"),
    (re.compile(r"\b(sell on tryonu|open (?:a|your) store)\b", re.I), "/sell"),
    (re.compile(r"(?<![/@\w.])(tryonu\.app)\b", re.I), "/"),
]


def tracked(path: str, campaign: str = "admin_email") -> str:
    from urllib.parse import urlencode

    sep = "&" if "?" in path else "?"
    return f"{SITE}{path}{sep}{urlencode({'utm_source': 'email', 'utm_medium': 'email', 'utm_campaign': campaign})}"


def linked(escaped: str, *, color: str = "#57634f") -> str:
    """Already-escaped text with its web addresses and page names as links."""
    out = _URL.sub(rf'<a href="\1" style="color:{color}">\1</a>', escaped)
    used: set[str] = set()
    for pattern, path in _PHRASES:
        if path in used:
            continue
        parts = _A_TAG.split(out)
        for k, part in enumerate(parts):
            if part.startswith("<a"):
                continue
            new, n = pattern.subn(
                lambda m: f'<a href="{html.escape(tracked(path))}" style="color:{color};font-weight:bold">{m.group(1)}</a>',
                part,
                count=1,
            )
            if n:
                parts[k] = new
                used.add(path)
                break
        out = "".join(parts)
    return out


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
    message opens the looks email (looks_email)."""
    s = get_settings()
    body = message.replace("{name}", name or "there").strip()
    if unsubscribe_url:
        footer = f"You get this because you have a TryOnU account. Stop these emails: {unsubscribe_url}"
    elif audience == "stores":
        footer = f"You get this because you have a store on TryOnU. Questions? Reply to this email or write to {s.SALES_EMAIL}."
    else:
        footer = f"Questions? Reply to this email or write to {s.SUPPORT_EMAIL}."

    paragraphs = "".join(
        '<p style="margin:0 0 14px">' + linked(html.escape(p).replace("\n", "<br>")) + "</p>"
        for p in re.split(r"\n\s*\n", body)
        if p.strip()
    )
    footer_html = _URL.sub(r'<a href="\1" style="color:#8a8a80">\1</a>', html.escape(footer))
    if looks is not None:
        from app.services.looks_email import render_looks

        text, page = render_looks(paragraphs, body, looks, footer_html)
        return f"{text}\n\n--\nTryOnU · {SITE}\n{footer}\n", page
    text = f"{body}\n\n--\nTryOnU · {SITE}\n{footer}\n"
    page = (
        '<!doctype html><html><body style="margin:0;background:#f6f3ee;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:28px 18px">'
        '<p style="margin:0 0 18px;font:bold 20px Georgia,serif;color:#57634f">TryOnU</p>'
        '<div style="background:#ffffff;border:1px solid #e5ddd3;border-radius:16px;padding:24px;'
        f'font-size:15px;line-height:1.55;color:#1c1b17">{paragraphs}</div>'
        f'<p style="margin:18px 4px 0;font-size:12.5px;line-height:1.5;color:#8a8a80">{footer_html}</p>'
        f'<p style="display:none">{html.escape(subject)}</p>'
        "</div></body></html>"
    )
    return text, page


async def send_one(recipient: Recipient, subject: str, message: str, audience: str, looks: list[dict] | None = None) -> None:
    from app.email.registry import get_email_provider
    from app.services.notification_service import unsubscribe_url

    link = unsubscribe_url(recipient.user_id) if recipient.user_id else None
    text, page = render(subject, message, recipient.name, unsubscribe_url=link, audience=audience, looks=looks)
    reply_to = get_settings().SALES_EMAIL if audience == "stores" else None
    await get_email_provider().send(
        to=recipient.email, subject=subject, text_body=text, html_body=page, reply_to=reply_to, unsubscribe_url=link
    )


# ------------------------------------------------------------------ the queue


def queued_row(row: AdminEmail, people: list[Recipient], looks: list[dict] | None) -> AdminEmail:
    """A group email, ready for the queue: its people and looks saved with it."""
    row.recipients = [asdict(p) for p in people]
    row.looks = looks
    row.next_index = 0
    row.status = "queued"
    return row


async def send_next(db: AsyncSession) -> str:
    """Sends the next email of the oldest group email that may go now.
    Returns what happened: sent, failed (one bad address), paused (the mail
    server said not now), budget (today's limit reached), done or idle."""
    now = datetime.now(timezone.utc)
    row = await db.scalar(
        select(AdminEmail)
        .where(
            AdminEmail.recipients.is_not(None),
            or_(
                AdminEmail.status.in_(("queued", "sending")),
                (AdminEmail.status == "paused") & (AdminEmail.paused_until <= now),
            ),
        )
        .order_by(AdminEmail.created_at)
        .limit(1)
    )
    if row is None:
        return "idle"
    people = row.recipients or []
    if row.next_index >= len(people):
        row.status = "done"
        row.recipients = None  # the list isn't needed any more
        await db.commit()
        return "done"
    if not await email_budget.take(db):
        await db.commit()
        return "budget"
    person = Recipient(**people[row.next_index])
    try:
        await send_one(person, row.subject, row.message, row.audience, row.looks)
        row.sent += 1
        outcome = "sent"
    except Exception as exc:  # noqa: BLE001 - classified below
        if email_budget.slow_down(exc):
            row.status = "paused"
            row.paused_until = now + PAUSE_AFTER_REFUSAL
            row.last_error = f"The mail server said: {str(exc)[:220]}"
            await db.commit()
            logger.warning("admin_email_paused", email_id=row.id, error=str(exc)[:200])
            return "paused"
        row.failed += 1
        outcome = "failed"
        logger.warning("admin_email_failed", email_id=row.id, error=str(exc)[:200])
    row.next_index += 1
    row.status = "sending"
    row.paused_until = None
    if row.next_index >= len(people):
        row.status = "done"
        row.recipients = None
    await db.commit()
    return outcome


async def queue_forever() -> None:
    """Runs for the life of the API process."""
    from app.db.session import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                outcome = await send_next(db)
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            logger.warning("admin_email_queue_failed", error=str(exc)[:200])
            outcome = "error"
        if outcome in ("sent", "failed"):
            await asyncio.sleep(email_budget.gap_seconds())
        elif outcome == "done":
            await asyncio.sleep(1)
        elif outcome == "budget":
            await asyncio.sleep(600)  # tomorrow's limit starts at midnight UTC
        else:
            await asyncio.sleep(30)
