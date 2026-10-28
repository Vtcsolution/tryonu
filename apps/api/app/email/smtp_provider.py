"""Real email delivery over SMTP — works with any SMTP relay (SES,
SendGrid, Postmark, Mailgun, or a plain mailbox) without adding a
provider-specific SDK dependency. `smtplib` is synchronous, so the actual
send runs in a worker thread via `asyncio.to_thread`."""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from app.email.base import EmailProvider


class SMTPEmailProvider(EmailProvider):
    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str,
        use_tls: bool = True,
        from_name: str = "",
        reply_to: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls
        self._from_name = from_name
        self._reply_to = reply_to

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
        await asyncio.to_thread(self._send_sync, to, subject, text_body, html_body, reply_to, unsubscribe_url)

    def _send_sync(
        self, to: str, subject: str, text_body: str, html_body: str | None, reply_to: str | None, unsubscribe_url: str | None
    ) -> None:
        # the headers mail programs look for before they trust a message:
        # a named sender, a date, a message id of our own domain, where to
        # reply, and a way to stop the emails
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((self._from_name, self._from_email)) if self._from_name else self._from_email
        msg["To"] = to
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(domain=self._from_email.rsplit("@", 1)[-1])
        if reply_to or self._reply_to:
            msg["Reply-To"] = reply_to or self._reply_to
        if unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(self._host, self._port, timeout=15) as server:
            if self._use_tls:
                server.starttls()
            if self._username and self._password:
                server.login(self._username, self._password)
            server.sendmail(self._from_email, [to], msg.as_string())
