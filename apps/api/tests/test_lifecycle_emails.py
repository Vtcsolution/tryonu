"""The emails the site sends by itself: each once, only to members who keep
emails on, with the stop link."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.email.registry import get_email_provider
from app.models.user import User
from app.services import lifecycle_emails
from tests.conftest import register_and_login, unique_email


async def _member(client, db, *, days_old: int = 0, emails_on: bool = True) -> dict:  # noqa: ANN001
    email = unique_email()
    await register_and_login(client, email=email)
    me = (await client.get("/api/v1/auth/me")).json()
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    await db.execute(update(User).where(User.id == me["id"]).values(created_at=created, notify_email=emails_on))
    await db.commit()
    return me


def _roomy(monkeypatch) -> None:  # noqa: ANN001
    """No pauses, and room for every member the shared test database holds."""
    from app.core.config import get_settings

    monkeypatch.setattr(lifecycle_emails, "PAUSE", 0)
    monkeypatch.setattr(lifecycle_emails, "PER_ROUND", 100000)
    monkeypatch.setattr(get_settings(), "EMAIL_PER_DAY", 10**9)


def _mails_to(email: str, before: int) -> list[dict]:
    return [m for m in get_email_provider().sent[before:] if m["to"] == email]


async def test_a_new_member_gets_the_welcome_once_and_a_quiet_one_gets_nothing(client, db, monkeypatch):
    _roomy(monkeypatch)
    new = await _member(client, db)
    quiet = await _member(client, db, emails_on=False)
    before = len(get_email_provider().sent)

    await lifecycle_emails.run_once(db)
    welcome = [m for m in _mails_to(new["email"], before) if "Welcome to TryOnU" in m["subject"]]
    assert len(welcome) == 1 and "/notifications/unsubscribe" in welcome[0]["unsubscribe"]
    assert "Pick my first look" in welcome[0]["html"]
    assert not _mails_to(quiet["email"], before)

    await lifecycle_emails.run_once(db)  # never twice
    assert len([m for m in _mails_to(new["email"], before) if "Welcome" in m["subject"]]) == 1


async def test_two_days_without_a_try_on_brings_the_first_outfit_offer(client, db, monkeypatch):
    _roomy(monkeypatch)
    waiting = await _member(client, db, days_old=3)
    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    nudge = [m for m in _mails_to(waiting["email"], before) if "first outfit is waiting" in m["subject"]]
    assert len(nudge) == 1 and "$1" in nudge[0]["body"] and "/credits?offer=1" in nudge[0]["body"]


async def test_an_hour_after_a_try_on_the_member_is_asked_to_shop_it_once(client, db, monkeypatch):
    from app.models.tryon import TryOnJob
    from tests.test_shared_looks import _finished_look

    _roomy(monkeypatch)
    job_id, _product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()
    await db.execute(
        update(TryOnJob).where(TryOnJob.id == job_id).values(completed_at=datetime.now(timezone.utc) - timedelta(hours=2))
    )
    await db.commit()
    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    await lifecycle_emails.run_once(db)
    ready = [m for m in _mails_to(me["email"], before) if "Your look is ready" in m["subject"]]
    assert len(ready) == 1 and f"/try?job={job_id}" in ready[0]["body"]
