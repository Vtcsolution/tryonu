"""Outbound email abstraction — same provider pattern as AI/retailers/
payments: a real implementation (SMTP, works with SES/SendGrid/Postmark/
Mailgun's SMTP relays) plus a mock that never touches the network, so
password-reset etc. are fully testable without sending real email."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmailProvider(ABC):
    name: str

    @abstractmethod
    async def send(
        self,
        *,
        to: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
        unsubscribe_url: str | None = None,
    ) -> None:
        """reply_to: where a reply goes (default: the support address);
        unsubscribe_url: a one-click "stop these emails" link for mail
        programs (List-Unsubscribe), for emails a member can turn off."""
