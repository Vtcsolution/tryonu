"""How fast and how much the site may email, so the mailbox plan (Hostinger)
never blocks the mailbox: group emails and the daily email share one daily
count, and go out at most EMAIL_PER_HOUR an hour."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.admin_email import EmailSendDay


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def gap_seconds() -> float:
    """The pause between two emails: an hour's limit spread evenly."""
    return 3600 / max(1, get_settings().EMAIL_PER_HOUR)


async def used_today(db: AsyncSession) -> int:
    row = await db.get(EmailSendDay, _today())
    return row.count if row else 0


async def take(db: AsyncSession) -> bool:
    """One more email today, if the daily limit allows (the caller commits)."""
    row = await db.get(EmailSendDay, _today())
    if row is None:
        row = EmailSendDay(day=_today(), count=0)
        db.add(row)
    if row.count >= get_settings().EMAIL_PER_DAY:
        return False
    row.count += 1
    await db.flush()
    return True


def slow_down(exc: BaseException) -> bool:
    """The mail server said "not now" (too many, too fast, sign-in refused),
    as opposed to one bad address: stop and try again later instead of
    knocking again, which is what gets a mailbox blocked."""
    import smtplib

    # (every smtplib error is also an OSError, so the order matters)
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return False  # that one address doesn't exist
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return True  # the mailbox refused the sign-in: blocked, or the password changed
    if isinstance(exc, smtplib.SMTPResponseException):
        if exc.smtp_code in (421, 450, 451, 452, 454):
            return True
        raw = exc.smtp_error
        text = (raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw)).lower()
        return any(w in text for w in ("rate", "limit", "too many", "blocked", "suspend", "quota", "try again later"))
    return isinstance(exc, OSError)  # no connection to the mail server at all
