"""Free welcome credits: once per person, on a confirmed email, not again
with another Gmail spelling, the same browser, the same network, or a
throwaway mailbox (app/services/welcome_credits.py)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.welcome_credits import email_key, is_disposable
from tests.conftest import last_verification_token, unique_email


def test_gmail_dots_and_plus_tags_are_the_same_mailbox():
    assert email_key("Ali.Raza+shop@gmail.com") == email_key("aliraza@gmail.com") == email_key("a.li.raza@googlemail.com")
    assert email_key("ali+x@outlook.com") == email_key("ali@outlook.com")
    # dots matter outside Gmail
    assert email_key("ali.raza@outlook.com") != email_key("aliraza@outlook.com")


def test_throwaway_mailboxes_are_recognised():
    assert is_disposable("x@mailinator.com") and is_disposable("x@eu.yopmail.com")
    assert not is_disposable("x@gmail.com")


@pytest.fixture
def real_rules(monkeypatch):  # noqa: ANN001, ANN201
    s = get_settings()
    monkeypatch.setattr(s, "SIGNUP_FREE_CREDITS", 10)
    monkeypatch.setattr(s, "WELCOME_REQUIRE_VERIFIED", True)
    monkeypatch.setattr(s, "WELCOME_MAX_PER_IP", 2)
    return s


async def _sign_up(client, email: str, *, ip: str, device: str | None = None, verify: bool = True) -> dict:  # noqa: ANN001
    headers = {"x-real-ip": ip, **({"x-tryonu-device": device} if device else {})}
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "password123"}, headers=headers)
    assert resp.status_code == 201, resp.text
    out = {"register": resp.json()}
    if verify:
        v = await client.post("/api/v1/auth/verify-email", json={"token": last_verification_token(email)}, headers=headers)
        assert v.status_code == 200, v.text
        out["verify"] = v.json()["detail"]
    out["balance"] = (await client.get("/api/v1/credits/balance")).json()["balance"]
    return out


def _ip() -> str:
    import secrets

    return f"10.{secrets.randbelow(250)}.{secrets.randbelow(250)}.{secrets.randbelow(250)}"


async def test_credits_come_when_the_email_is_confirmed_not_before(client, real_rules):
    email, ip = unique_email(), _ip()
    out = await _sign_up(client, email, ip=ip, verify=False)
    assert out["balance"] == 0
    v = await client.post("/api/v1/auth/verify-email", json={"token": last_verification_token(email)}, headers={"x-real-ip": ip})
    assert "10 free credits" in v.json()["detail"]
    assert (await client.get("/api/v1/credits/balance")).json()["balance"] == 10


async def test_another_spelling_of_the_same_gmail_gets_nothing(client, real_rules):
    import secrets

    name = f"ali{secrets.token_hex(4)}"
    first = await _sign_up(client, f"{name}@gmail.com", ip=_ip())
    second = await _sign_up(client, f"{name[:2]}.{name[2:]}+again@gmail.com", ip=_ip())
    assert first["balance"] == 10 and second["balance"] == 0
    assert second["verify"] == "Email verified. Thank you!"


async def test_the_same_browser_gets_it_once(client, real_rules):
    device = "dev-" + unique_email().split("@")[0][:20]
    assert (await _sign_up(client, unique_email(), ip=_ip(), device=device))["balance"] == 10
    assert (await _sign_up(client, unique_email(), ip=_ip(), device=device))["balance"] == 0


async def test_one_network_gets_it_a_few_times_only(client, real_rules):
    ip = _ip()
    got = [(await _sign_up(client, unique_email(), ip=ip))["balance"] for _ in range(3)]
    assert got == [10, 10, 0]


async def test_throwaway_mailbox_gets_nothing(client, real_rules):
    assert (await _sign_up(client, unique_email().split("@")[0] + "@mailinator.com", ip=_ip()))["balance"] == 0


async def test_turned_off_gives_nothing(client, real_rules, monkeypatch):
    monkeypatch.setattr(real_rules, "SIGNUP_FREE_CREDITS", 0)
    assert (await _sign_up(client, unique_email(), ip=_ip()))["balance"] == 0
