"""Check the PayPal keys without charging anything.

    python -m app.scripts.paypal_check            # the mode PAYPAL_MODE picks
    python -m app.scripts.paypal_check sandbox    # or name one
    python -m app.scripts.paypal_check live

Shows which keys are loaded (yes/no only) and asks PayPal for a sign-in token.
Creates no order and moves no money. Prints no key or token.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.core.config import get_settings
from app.payments.paypal_provider import PayPalPaymentProvider


async def check(mode: str) -> bool:
    s = get_settings()
    live = mode == "live"
    client_id = s.PAYPAL_CLIENT_ID if live else s.PAYPAL_SANDBOX_CLIENT_ID
    secret = s.PAYPAL_CLIENT_SECRET if live else s.PAYPAL_SANDBOX_CLIENT_SECRET
    print(f"[{mode}] client id loaded: {bool(client_id)} | secret loaded: {bool(secret)}")
    if not (client_id and secret):
        return False
    provider = PayPalPaymentProvider(client_id=client_id, client_secret=secret, mode=mode, return_url="", cancel_url="")
    try:
        async with provider._client() as client:  # noqa: SLF001 — the provider's own sign-in, nothing else
            await provider._access_token(client)  # noqa: SLF001
    except Exception as exc:  # noqa: BLE001
        print(f"[{mode}] sign-in FAILED: {exc}")
        return False
    print(f"[{mode}] sign-in OK: PayPal accepted these keys")
    return True


async def main() -> int:
    s = get_settings()
    modes = sys.argv[1:] or [s.PAYPAL_MODE]
    print(f"PAYMENT_PROVIDER={s.PAYMENT_PROVIDER} | PAYPAL_MODE={s.PAYPAL_MODE} | return page: {str(s.FRONTEND_URL).rstrip('/')}/credits/paypal")
    results = [await check(m) for m in modes if m in ("sandbox", "live")]
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
