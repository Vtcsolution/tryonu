"""Admin → Send email: to one person now, to a group in the background,
members only when they kept emails on, with a link to stop them."""

from __future__ import annotations

from sqlalchemy import select, update

from app.email.registry import get_email_provider
from app.models.admin_email import AdminEmail
from app.models.user import User
from app.services import admin_email_service
from tests.conftest import register_and_login


async def _admin(client, db) -> dict:  # noqa: ANN001
    await register_and_login(client)
    me = (await client.get("/api/v1/auth/me")).json()
    await db.execute(update(User).where(User.id == me["id"]).values(is_admin=True))
    await db.commit()
    return me


async def test_an_admin_emails_one_person_now(client, db):
    await _admin(client, db)
    sent = get_email_provider().sent
    before = len(sent)
    made = await client.post(
        "/api/v1/admin/email/send",
        json={"audience": "one", "to": "friend@example.com", "subject": "Hello from TryOnU", "message": "Hi {name},\n\nWelcome!"},
    )
    assert made.status_code == 201, made.text
    assert made.json()["sent"] == 1 and made.json()["status"] == "done"
    mail = sent[before]
    assert mail["to"] == "friend@example.com" and mail["subject"] == "Hello from TryOnU"
    assert "Hi there," in mail["body"] and "TryOnU" in mail["html"] and not mail["unsubscribe"]


async def test_a_group_email_reaches_members_who_keep_emails_on(client, db, monkeypatch):
    monkeypatch.setattr(admin_email_service, "GAP_SECONDS", 0)
    await register_and_login(client)  # a member who keeps emails on
    me = await _admin(client, db)
    await db.execute(update(User).values(email_verified=True))
    await db.execute(update(User).where(User.id == me["id"]).values(notify_email=False))  # turned emails off
    await db.commit()
    expected = {
        e.lower()
        for e in (
            await db.execute(
                select(User.email).where(
                    User.is_active.is_(True), User.email_verified.is_(True), User.notify_email.is_(True),
                    User.team_person.is_(False),
                )
            )
        ).scalars()
    }
    if len(expected) > admin_email_service.MAX_PER_SEND:
        monkeypatch.setattr(admin_email_service, "MAX_PER_SEND", len(expected) + 1)
    counts = (await client.get("/api/v1/admin/email/audiences")).json()
    assert counts["members"] == len(expected)

    sent = get_email_provider().sent
    before = len(sent)
    made = await client.post(
        "/api/v1/admin/email/send", json={"audience": "members", "subject": "New looks", "message": "See what's new."}
    )
    assert made.status_code == 201, made.text
    await admin_email_service.wait_for_sending()
    mails = sent[before:]
    assert {m["to"].lower() for m in mails} == expected
    assert me["email"].lower() not in {m["to"].lower() for m in mails}
    assert all("/notifications/unsubscribe" in m["unsubscribe"] for m in mails)

    db.expire_all()
    row = await db.get(AdminEmail, made.json()["id"])
    assert row.status == "done" and row.sent == len(expected) and row.failed == 0
    history = (await client.get("/api/v1/admin/email/history")).json()
    assert history[0]["id"] == row.id


async def test_only_admins_send_email(client):
    await register_and_login(client)
    refused = await client.post(
        "/api/v1/admin/email/send", json={"audience": "me", "subject": "Hi", "message": "Test"}
    )
    assert refused.status_code == 403
