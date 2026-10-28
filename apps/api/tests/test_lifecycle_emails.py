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


async def _payment(db, user_id: str, *, status, hours_ago: float, credits: int = 50):  # noqa: ANN001, ANN202
    from app.models.subscription import Payment
    from tests.conftest import seed_credit_package

    pack = await seed_credit_package(db, name=f"Pack {credits}", credits=credits)
    when = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    pay = Payment(user_id=user_id, amount_cents=499, currency="usd", status=status, provider="paypal",
                  credit_package_id=pack.id, created_at=when, updated_at=when)
    db.add(pay)
    await db.commit()
    return pay


async def test_a_paid_pack_brings_a_receipt_even_with_emails_off(client, db, monkeypatch):
    from app.models.enums import PaymentStatus

    _roomy(monkeypatch)
    buyer = await _member(client, db, emails_on=False)
    await _payment(db, buyer["id"], status=PaymentStatus.SUCCEEDED, hours_ago=0.1, credits=50)
    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    await lifecycle_emails.run_once(db)
    receipts = [m for m in _mails_to(buyer["email"], before) if "receipt" in m["subject"]]
    assert len(receipts) == 1 and "50 credits" in receipts[0]["body"] and "$4.99" in receipts[0]["body"]
    assert receipts[0]["unsubscribe"] == ""  # a receipt, not a newsletter


async def test_an_unfinished_payment_is_followed_up_once(client, db, monkeypatch):
    from app.models.enums import PaymentStatus

    _roomy(monkeypatch)
    shopper = await _member(client, db)
    await _payment(db, shopper["id"], status=PaymentStatus.PENDING, hours_ago=3)
    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    await lifecycle_emails.run_once(db)
    follow = [m for m in _mails_to(shopper["email"], before) if "didn't finish" in m["subject"]]
    assert len(follow) == 1 and "Finish my purchase" in follow[0]["html"] and "$1" in follow[0]["body"]


async def test_a_member_away_for_a_month_is_welcomed_back(client, db, monkeypatch):
    _roomy(monkeypatch)
    away = await _member(client, db, days_old=45)
    await db.execute(
        update(User).where(User.id == away["id"]).values(last_login_at=datetime.now(timezone.utc) - timedelta(days=40))
    )
    await db.commit()
    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    assert [m for m in _mails_to(away["email"], before) if "New looks are waiting" in m["subject"]]


async def test_google_sign_ups_get_the_welcome_too(db, monkeypatch):
    from app.services import auth_service

    _roomy(monkeypatch)
    email = unique_email("google")
    await auth_service.find_or_create_google_user(db, google_sub=f"sub-{email}", email=email, full_name="Ali Raza", avatar_url=None)
    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    assert [m for m in _mails_to(email, before) if "Welcome to TryOnU" in m["subject"]]


async def test_shop_owners_hear_before_their_plan_ends_and_get_monday_numbers(client, db, monkeypatch):
    import uuid

    from app.models.store import Store, StoreProduct

    _roomy(monkeypatch)
    owner = await _member(client, db)
    store = Store(
        owner_user_id=owner["id"], name="Lahore Couture", slug=f"lahore-{uuid.uuid4().hex[:8]}", country="PK",
        status="approved", plan_expires_at=datetime.now(timezone.utc) + timedelta(days=2), contact_email="shop@example.com",
    )
    db.add(store)
    await db.flush()
    db.add(StoreProduct(store_id=store.id, external_id="lawn-1", name="Lawn suit", price_cents=2500, currency="usd",
                        product_url="https://x.test/p", images=["https://x.test/p.jpg"]))
    await db.commit()

    class Monday(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)

    before = len(get_email_provider().sent)
    await lifecycle_emails.run_once(db)
    to_shop = [m for m in get_email_provider().sent[before:] if m["to"] == "shop@example.com"]
    assert any("plan ends" in m["subject"] for m in to_shop)

    monkeypatch.setattr(lifecycle_emails, "datetime", Monday)
    await lifecycle_emails.run_once(db)
    to_shop = [m for m in get_email_provider().sent[before:] if m["to"] == "shop@example.com"]
    assert any("Lahore Couture on TryOnU last week" in m["subject"] for m in to_shop)
