"""Two-step sign-in: a 6-digit code from an authenticator app (Google
Authenticator, Microsoft Authenticator, Authy...) as well as the password.

The standard time-based codes (RFC 6238: HMAC-SHA1, 30 seconds, 6 digits),
so any of those apps works. The shared secret is kept encrypted."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote

ISSUER = "TryOnU"
STEP = 30
DIGITS = 6
CODE_NEEDED = "TWO_STEP_CODE_NEEDED"  # what login answers when the code is missing


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def code_now(secret: str, at: float | None = None) -> str:
    return _code(secret, int((at if at is not None else time.time()) // STEP))


def verify(secret: str, code: str | None, at: float | None = None) -> bool:
    """The code, allowing for a phone clock half a minute off either way."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != DIGITS:
        return False
    now = int((at if at is not None else time.time()) // STEP)
    return any(hmac.compare_digest(_code(secret, now + d), code) for d in (-1, 0, 1))


def setup_link(email: str, secret: str) -> str:
    """The otpauth:// link the apps read (from the QR code, or a tap on a phone)."""
    label = quote(f"{ISSUER}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}&digits={DIGITS}&period={STEP}"


def qr_data_uri(link: str) -> str:
    import qrcode

    img = qrcode.make(link, box_size=6, border=2)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
