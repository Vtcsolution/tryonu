"""Real email delivery over SMTP — works with any SMTP relay (SES,
SendGrid, Postmark, Mailgun, or a plain mailbox) without adding a
provider-specific SDK dependency. `smtplib` is synchronous, so the actual
send runs in a worker thread via `asyncio.to_thread`."""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.email.base import EmailProvider


class SMTPEmailProvider(EmailProvider):
    name = "smtp"

    def __init__(self, *, host: str, port: int, username: str | None, password: str | None, from_email: str, use_tls: bool = True) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls

    async def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, text_body, html_body)

    def _send_sync(self, to: str, subject: str, text_body: str, html_body: str | None) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_email
        msg["To"] = to
        msg.attach(MIMEText(text_body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(self._host, self._port, timeout=15) as server:
            if self._use_tls:
                server.starttls()
            if self._username and self._password:
                server.login(self._username, self._password)
            server.sendmail(self._from_email, [to], msg.as_string())
