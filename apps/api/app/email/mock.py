from __future__ import annotations

from app.core.logging import logger
from app.email.base import EmailProvider


class MockEmailProvider(EmailProvider):
    """Used automatically without SMTP_HOST configured. Logs the full
    email (including any reset/verification link) at INFO level — in local
    dev this is how you "receive" one: read the server log. Also keeps an
    in-memory record (`sent`) of everything it's "sent" — the registry
    caches one instance per process (see registry.py), so tests can read
    tokens straight out of it instead of scraping logs."""

    name = "mock"

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject, "body": text_body})
        logger.info("email_sent_mock", to=to, subject=subject, body=text_body)
