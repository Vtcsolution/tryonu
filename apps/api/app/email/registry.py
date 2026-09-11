from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.email.base import EmailProvider
from app.email.mock import MockEmailProvider
from app.email.smtp_provider import SMTPEmailProvider


@lru_cache
def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.EMAIL_PROVIDER == "smtp":
        return SMTPEmailProvider(
            host=settings.SMTP_HOST,  # type: ignore[arg-type]
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            from_email=settings.SMTP_FROM_EMAIL,
        )
    return MockEmailProvider()
