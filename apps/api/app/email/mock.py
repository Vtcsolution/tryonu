from __future__ import annotations

from app.core.logging import logger
from app.email.base import EmailProvider


class MockEmailProvider(EmailProvider):
    """Used automatically without SMTP_HOST configured. Logs the full
    email (including any reset link) at INFO level — in local dev this is
    how you "receive" a password-reset email: read the server log."""

    name = "mock"

    async def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        logger.info("email_sent_mock", to=to, subject=subject, body=text_body)
