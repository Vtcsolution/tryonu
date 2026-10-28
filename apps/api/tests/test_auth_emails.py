"""The verify and reset-password emails: a working link (live, the address
came out as tryonu.app//verify-email), the TryOnU design, and sign-up still
working when email can't be sent."""

from __future__ import annotations

import re

from app.email.registry import get_email_provider
from tests.conftest import register_and_login, unique_email


async def test_the_reset_link_has_no_double_slash_and_a_button(client):
    email = unique_email()
    await register_and_login(client, email=email)
    await client.post("/api/v1/auth/logout")
    sent = get_email_provider().sent
    before = len(sent)
    asked = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert asked.status_code in (200, 202), asked.text
    mail = next(m for m in sent[before:] if m["to"] == email)
    link = re.search(r"https?://\S+/reset-password\?token=[\w-]+", mail["body"]).group(0)
    assert "//reset-password" not in link.split("://", 1)[1]
    assert "Choose a new password" in mail["html"] and link in mail["html"]


async def test_signing_up_works_even_when_email_cant_be_sent(client, monkeypatch):
    provider = get_email_provider()

    async def broken(**kwargs):  # noqa: ANN003
        raise ConnectionError("mail server down")

    monkeypatch.setattr(provider, "send", broken)
    made = await client.post(
        "/api/v1/auth/register", json={"email": unique_email(), "password": "password123", "full_name": "Sana"}
    )
    assert made.status_code == 201, made.text
