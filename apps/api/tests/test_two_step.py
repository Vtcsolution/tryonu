"""Two-step sign-in: an authenticator-app code as well as the password."""

from __future__ import annotations

from app.services import two_step
from tests.conftest import register_and_login, unique_email


def test_codes_follow_the_standard():
    # RFC 6238's own example secret ("12345678901234567890"), at 59 seconds: 287082
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert two_step.code_now(secret, at=59) == "287082"
    assert two_step.verify(secret, "287082", at=59) and two_step.verify(secret, "287 082", at=59 + 30)
    assert not two_step.verify(secret, "287082", at=59 + 120) and not two_step.verify(secret, "12", at=59)


async def test_with_two_step_on_signing_in_needs_the_code(client):
    email = unique_email()
    await register_and_login(client, email=email)
    setup = (await client.post("/api/v1/auth/two-step/setup")).json()
    assert setup["link"].startswith("otpauth://totp/TryOnU") and setup["qr"].startswith("data:image/png;base64,")

    wrong = await client.post("/api/v1/auth/two-step/enable", json={"code": "000000"})
    assert wrong.status_code == 400
    on = await client.post("/api/v1/auth/two-step/enable", json={"code": two_step.code_now(setup["secret"])})
    assert on.status_code == 200 and on.json()["totp_enabled"] is True

    await client.post("/api/v1/auth/logout")
    no_code = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert no_code.status_code == 401 and no_code.json()["detail"] == two_step.CODE_NEEDED
    bad = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123", "code": "123456"})
    assert bad.status_code == 401 and "isn't right" in bad.json()["detail"]
    good = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123", "code": two_step.code_now(setup["secret"])}
    )
    assert good.status_code == 200 and good.json()["user"]["totp_enabled"] is True

    off = await client.post("/api/v1/auth/two-step/disable", json={"code": two_step.code_now(setup["secret"])})
    assert off.status_code == 200 and off.json()["totp_enabled"] is False
