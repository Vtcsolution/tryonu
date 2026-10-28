"""Real email delivery over SMTP — works with any SMTP relay (SES,
SendGrid, Postmark, Mailgun, or a plain mailbox) without adding a
provider-specific SDK dependency. `smtplib` is synchronous, so the actual
send runs in a worker thread via `asyncio.to_thread`.

One sign-in is kept open and reused for the emails that follow (closed after
a few idle minutes): a mailbox host (Hostinger) treats a fresh sign-in for
every email as suspicious and blocks the mailbox."""

from __future__ import annotations

import asyncio
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from app.email.base import EmailProvider

# a kept-open sign-in older than this is closed and made again (mail servers
# drop idle connections after about five minutes)
_IDLE_SECONDS = 240


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
        self._conn: smtplib.SMTP | None = None
        self._last_used = 0.0
        self._lock = threading.Lock()

    def _connection(self) -> smtplib.SMTP:
        if self._conn is not None and time.monotonic() - self._last_used < _IDLE_SECONDS:
            return self._conn
        self._close()
        server = smtplib.SMTP(self._host, self._port, timeout=20)
        if self._use_tls:
            server.starttls()
        if self._username and self._password:
            server.login(self._username, self._password)
        self._conn = server
        return server

    def _close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.quit()
            except Exception:  # noqa: BLE001 - it's going anyway
                pass
            self._conn = None

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

        with self._lock:
            for attempt in (1, 2):
                server = self._connection()
                try:
                    server.sendmail(self._from_email, [to], msg.as_string())
                    self._last_used = time.monotonic()
                    return
                except smtplib.SMTPServerDisconnected:
                    # the kept-open sign-in had timed out on their side: once more, fresh
                    self._conn = None
                    if attempt == 2:
                        raise
                except smtplib.SMTPRecipientsRefused:
                    self._last_used = time.monotonic()  # that address only; the sign-in is fine
                    raise
                except Exception:
                    self._close()
                    raise
