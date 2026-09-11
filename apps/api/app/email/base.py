"""Outbound email abstraction — same provider pattern as AI/retailers/
payments: a real implementation (SMTP, works with SES/SendGrid/Postmark/
Mailgun's SMTP relays) plus a mock that never touches the network, so
password-reset etc. are fully testable without sending real email."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmailProvider(ABC):
    name: str

    @abstractmethod
    async def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None: ...
