"""Register/login/session/authorization — no mocked HTTP needed, this is
all real app + real (test) DB."""

from __future__ import annotations

from tests.conftest import register_and_login, unique_email


async def test_register_grants_signup_bonus_immediately(client):
    """Credits are granted at registration, not gated behind email
    verification — new accounts can start using the product right away
    (see test_email_verification.py for the verification flow itself,
    which now only affects the email_verified flag, not the balance)."""
    email = unique_email()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["credits_balance"] == 100
    assert data["user"]["email_verified"] is False
    assert data["user"]["is_admin"] is False
    assert "access_token" in data


async def test_register_and_login_helper_grants_signup_bonus(client):
    data = await register_and_login(client)
    assert data["user"]["credits_balance"] == 100
    assert data["user"]["email_verified"] is True


async def test_duplicate_email_is_rejected(client):
    email = unique_email()
    await register_and_login(client, email=email)

    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 409


async def test_login_wrong_password_is_401(client):
    email = unique_email()
    await register_and_login(client, email=email)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "totally-wrong"},
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user_when_authenticated(client):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == data["user"]["email"]


async def test_logout_clears_session(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_google_login_501_when_not_configured(client):
    # No GOOGLE_CLIENT_ID/SECRET set in the test environment — must fail
    # clearly rather than pretend to work.
    resp = await client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 501


async def test_change_password_needs_the_current_one_and_keeps_you_signed_in(client):
    email = unique_email()
    await register_and_login(client, email=email)

    wrong = await client.post(
        "/api/v1/auth/change-password", json={"current_password": "not-it", "new_password": "brand-new-pass"}
    )
    assert wrong.status_code == 400

    ok = await client.post(
        "/api/v1/auth/change-password", json={"current_password": "password123", "new_password": "brand-new-pass"}
    )
    assert ok.status_code == 200, ok.text
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    old = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert old.status_code == 401
    new = await client.post("/api/v1/auth/login", json={"email": email, "password": "brand-new-pass"})
    assert new.status_code == 200
    assert new.json()["user"]["has_password"] is True


async def test_change_password_requires_sign_in(client):
    await client.post("/api/v1/auth/logout")
    resp = await client.post("/api/v1/auth/change-password", json={"new_password": "brand-new-pass"})
    assert resp.status_code == 401


async def test_account_without_password_can_set_its_first(client):
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    email = unique_email()
    await register_and_login(client, email=email)
    async with AsyncSessionLocal() as db:  # as if signed up with Google
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.hashed_password = None
        await db.commit()

    me = await client.get("/api/v1/auth/me")
    assert me.json()["has_password"] is False
    resp = await client.post("/api/v1/auth/change-password", json={"new_password": "first-password"})
    assert resp.status_code == 200, resp.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "first-password"})
    assert login.status_code == 200



async def test_sign_up_saves_the_country_the_shopper_chose(client):
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.preference import UserPreference

    email = unique_email()
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "country": "pk"}
    )
    assert resp.status_code == 201, resp.text
    async with AsyncSessionLocal() as db:
        pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == resp.json()["user"]["id"]))
    assert pref is not None and pref.country == "PK"
    prefs = await client.get("/api/v1/users/me/preferences")
    assert prefs.json()["country"] == "PK"


async def test_country_hint_comes_from_the_visitors_location(client):
    resp = await client.get("/api/v1/auth/country-hint", headers={"cf-ipcountry": "AE"})
    assert resp.status_code == 200 and resp.json() == {"country": "AE"}


def test_new_accounts_get_no_free_credits_and_a_try_on_costs_10_by_default():
    from app.core.config import Settings

    fields = Settings.model_fields
    assert fields["SIGNUP_FREE_CREDITS"].default == 0
    assert fields["TRYON_CREDIT_COST"].default == 10 and fields["OUTFIT_TRYON_CREDIT_COST"].default == 10



def _google_on(monkeypatch):  # noqa: ANN001, ANN202
    from app.services import google_oauth

    for key, value in (("GOOGLE_CLIENT_ID", "id"), ("GOOGLE_CLIENT_SECRET", "secret"),
                       ("GOOGLE_REDIRECT_URI", "https://api.tryonu.test/api/v1/auth/google/callback")):
        monkeypatch.setattr(google_oauth.settings, key, value)

    async def fake_profile(code):  # noqa: ANN001, ANN202
        return google_oauth.GoogleProfile(sub=f"g-{code}", email=f"{code}@gmail.example.com", name="G User", picture=None)

    monkeypatch.setattr(google_oauth, "exchange_code_for_profile", fake_profile)


async def test_google_sign_in_returns_to_the_page_it_started_from(client, monkeypatch):
    _google_on(monkeypatch)
    assert (await client.get("/api/v1/auth/google/enabled")).json() == {"enabled": True}
    start = await client.get("/api/v1/auth/google/login", params={"next": "/business"}, follow_redirects=False)
    assert start.status_code in (302, 307)
    state = start.headers["location"].split("state=")[1].split("&")[0]
    back = await client.get(
        "/api/v1/auth/google/callback", params={"code": "gstore1", "state": state}, follow_redirects=False
    )
    assert back.headers["location"].endswith("/business")
    assert (await client.get("/api/v1/auth/me")).json()["email"] == "gstore1@gmail.example.com"


async def test_google_sign_in_someone_else_started_is_refused(client, monkeypatch):
    _google_on(monkeypatch)
    await client.post("/api/v1/auth/logout")
    await client.get("/api/v1/auth/google/login", follow_redirects=False)
    forged = await client.get(
        "/api/v1/auth/google/callback", params={"code": "attacker", "state": "not-the-one"}, follow_redirects=False
    )
    assert "/sign-in?error=google" in forged.headers["location"]
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_google_never_sends_people_to_another_site(client, monkeypatch):
    _google_on(monkeypatch)
    start = await client.get("/api/v1/auth/google/login", params={"next": "//evil.example.com"}, follow_redirects=False)
    state = start.headers["location"].split("state=")[1].split("&")[0]
    back = await client.get("/api/v1/auth/google/callback", params={"code": "g2", "state": state}, follow_redirects=False)
    assert back.headers["location"].endswith("/try") and "evil" not in back.headers["location"]


async def test_the_verification_email_leads_back_to_the_look_shared_with_them(client):
    """A friend's shared look: opened on a phone, the email link still goes back to it."""
    from app.email.registry import get_email_provider

    email = unique_email()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "next": "/look/abc123/try"},
    )
    assert resp.status_code == 201
    body = next(m["body"] for m in reversed(get_email_provider().sent) if m["to"] == email)
    assert "/verify-email?token=" in body and "&next=%2Flook%2Fabc123%2Ftry" in body

    other = unique_email()  # never another website
    await client.post("/api/v1/auth/register", json={"email": other, "password": "password123", "next": "//evil.example"})
    body = next(m["body"] for m in reversed(get_email_provider().sent) if m["to"] == other)
    assert "next=" not in body
