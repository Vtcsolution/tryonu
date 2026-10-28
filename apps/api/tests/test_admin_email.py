"""Admin → Send email: to one person now, to a group in the background,
members only when they kept emails on, with a link to stop them."""

from __future__ import annotations

from sqlalchemy import select, update

from app.email.registry import get_email_provider
from app.models.admin_email import AdminEmail
from app.models.user import User
from app.services import admin_email_service
from tests.conftest import register_and_login


async def _drain(db) -> list[str]:  # noqa: ANN001
    """Runs the email queue until it has nothing left (the server does this slowly, in the background)."""
    outcomes = []
    for _ in range(5000):
        outcome = await admin_email_service.send_next(db)
        outcomes.append(outcome)
        if outcome in ("idle", "budget", "paused"):
            break
    return outcomes


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
    assert made.json()["status"] == "queued"
    await _drain(db)
    mails = sent[before:]
    assert {m["to"].lower() for m in mails} == expected
    assert me["email"].lower() not in {m["to"].lower() for m in mails}
    assert all("/notifications/unsubscribe" in m["unsubscribe"] for m in mails)

    db.expire_all()
    row = await db.get(AdminEmail, made.json()["id"])
    assert row.status == "done" and row.sent == len(expected) and row.failed == 0
    history = (await client.get("/api/v1/admin/email/history")).json()
    assert row.id in [h["id"] for h in history]


async def test_only_admins_send_email(client):
    await register_and_login(client)
    refused = await client.post(
        "/api/v1/admin/email/send", json={"audience": "me", "subject": "Hi", "message": "Test"}
    )
    assert refused.status_code == 403


async def test_a_contact_message_reaches_the_help_inbox_with_reply_to_the_sender(client):
    from app.core.config import get_settings

    sent = get_email_provider().sent
    before = len(sent)
    made = await client.post(
        "/api/v1/contact",
        json={"name": "Sana Malik", "email": "sana.inbox@example.com", "topic": "tryon", "message": "My credits didn't arrive after paying."},
    )
    assert made.status_code == 201, made.text
    inbox = [m for m in sent[before:] if m["to"] == get_settings().SUPPORT_EMAIL]
    assert len(inbox) == 1 and inbox[0]["reply_to"] == "sana.inbox@example.com"
    assert "My credits didn't arrive" in inbox[0]["body"]


def test_the_trending_looks_email_shows_each_look_with_a_try_it_link():
    from app.services.admin_email_service import render

    looks = [
        {"id": f"l{i}", "title": f"Look {i}", "picture": f"https://api.tryonu.app/api/v1/looks/l{i}/card.jpg?v=1&size=small",
         "pieces": 5, "price": "$120.00", "url": f"https://tryonu.app/looks/l{i}?utm_source=email"}
        for i in range(3)
    ]
    text, page = render("Top looks", "Hi {name},\n\nSee yourself in these.", "Zia", unsubscribe_url="https://x/unsub",
                        audience="members", looks=looks)
    assert "Hi Zia," in page and "Trending looks this week" in page and "How it works" in page
    from html import escape

    assert all(escape(lk["picture"]) in page and escape(lk["url"]) in page for lk in looks)
    assert page.count("Try it on you") == 3 and "https://x/unsub" in page
    assert "Look 2 (5 pieces, $120.00)" in text and "https://x/unsub" in text


async def test_the_preview_shows_published_ready_looks(client, db, monkeypatch):  # noqa: ANN001
    from tests.conftest import small_jpeg_bytes
    from tests.test_ready_looks import _finished_look, _team

    async def no_network(url: str) -> bytes:  # noqa: ARG001 - product photos without the internet
        return small_jpeg_bytes()

    monkeypatch.setattr("app.services.tryon_direct.inputs.fetch_product_image", no_network)
    job_id, _product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()
    await _team(db, me["id"])
    look = (await client.post("/api/v1/team/looks", json={"tryon_job_id": job_id, "title": "Emerald Party Look"})).json()
    await db.execute(update(User).where(User.id == me["id"]).values(is_admin=True))
    await db.commit()

    page = await client.post(
        "/api/v1/admin/email/preview", json={"subject": "Hi", "message": "Hi {name}", "template": "looks"}
    )
    shown = page.json()["html"]
    assert page.status_code == 200 and "Emerald Party Look" in shown
    assert f"/looks/{look['id']}?utm_source=email" in shown and look["card_small_url"].replace("&", "&amp;") in shown



async def test_a_group_email_pauses_when_the_mail_server_says_slow_down_and_goes_on_later(client, db, monkeypatch):
    import smtplib
    from datetime import datetime, timedelta, timezone

    from app.models.admin_email import AdminEmail

    await _admin(client, db)
    row = AdminEmail(audience="team", subject="Hi", message="Hello", total=2)
    admin_email_service.queued_row(
        row, [admin_email_service.Recipient("a@example.com", None, None), admin_email_service.Recipient("b@example.com", None, None)], None
    )
    db.add(row)
    await db.commit()

    calls = []

    async def refuse(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0].email)
        raise smtplib.SMTPResponseException(421, b"Too many messages, try again later")

    monkeypatch.setattr(admin_email_service, "send_one", refuse)
    assert await admin_email_service.send_next(db) == "paused"
    await db.refresh(row)
    assert row.status == "paused" and row.next_index == 0 and "Too many" in row.last_error
    await admin_email_service.send_next(db)  # not before its time
    await db.refresh(row)
    assert row.status == "paused" and row.next_index == 0 and len(calls) == 1

    async def deliver(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0].email)

    monkeypatch.setattr(admin_email_service, "send_one", deliver)
    row.paused_until = datetime.now(timezone.utc) - timedelta(seconds=1)  # an hour later
    await db.commit()
    while (await admin_email_service.send_next(db)) in ("sent",):
        pass
    await db.refresh(row)
    assert row.status == "done" and row.sent == 2 and calls[-2:] == ["a@example.com", "b@example.com"]


async def test_the_daily_limit_holds_a_group_email_until_tomorrow(client, db, monkeypatch):
    from app.core.config import get_settings
    from app.models.admin_email import AdminEmail
    from app.services import email_budget

    await _admin(client, db)
    monkeypatch.setattr(get_settings(), "EMAIL_PER_DAY", await email_budget.used_today(db) + 1)
    row = AdminEmail(audience="team", subject="Hi", message="Hello", total=2)
    admin_email_service.queued_row(
        row, [admin_email_service.Recipient("c@example.com", None, None), admin_email_service.Recipient("d@example.com", None, None)], None
    )
    db.add(row)
    await db.commit()
    outcomes = await _drain(db)
    await db.refresh(row)
    assert outcomes[-1] == "budget" and row.sent == 1 and row.status != "done"
    row.status = "done"  # leave nothing queued for later tests
    await db.commit()


def test_page_names_in_a_message_become_links():
    from app.services.admin_email_service import linked

    out = linked("See our Ready looks, then try it on. Join the community at tryonu.app or https://tryonu.app/earn")
    assert 'href="https://tryonu.app/looks?utm_source=email' in out and ">Ready looks</a>" in out
    assert "/try?utm_source=email" in out and "/community?utm_source=email" in out
    assert '<a href="https://tryonu.app/earn"' in out and out.count("<a ") == 5
