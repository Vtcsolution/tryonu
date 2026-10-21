"""WhatsApp numbers and wa.me links: how most shoppers in Pakistan (and much
of Asia and the Gulf) order from a local shop and ask for help."""

from __future__ import annotations

import re
from urllib.parse import quote

# country calling codes, for numbers typed the local way ("0300 1234567")
CALLING_CODES = {
    "PK": "92", "IN": "91", "BD": "880", "LK": "94", "NP": "977", "AE": "971", "SA": "966", "QA": "974",
    "KW": "965", "OM": "968", "BH": "973", "GB": "44", "US": "1", "CA": "1", "AU": "61", "MY": "60",
    "ID": "62", "TR": "90", "EG": "20", "NG": "234", "KE": "254", "ZA": "27", "DE": "49", "FR": "33",
}


def normalize(raw: str | None, country: str | None = None) -> str | None:
    """Digits only, with the country code ("+92 300 1234567" or "03001234567" in
    Pakistan -> "923001234567"). None for an empty value; ValueError when it
    can't be a phone number."""
    text = (raw or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        digits = digits[2:]
    elif not text.startswith("+") and digits.startswith("0"):
        code = CALLING_CODES.get((country or "").upper())
        if not code:
            raise ValueError("Please write the number with its country code, e.g. +92 300 1234567.")
        digits = code + digits.lstrip("0")
    if not 8 <= len(digits) <= 15:
        raise ValueError("That doesn't look like a WhatsApp number. Example: +92 300 1234567.")
    return digits


def chat_link(number: str, message: str = "") -> str:
    return f"https://wa.me/{number}" + (f"?text={quote(message)}" if message else "")
