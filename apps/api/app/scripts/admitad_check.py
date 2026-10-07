"""Read-only check of the Admitad (Mitgo) API connection.

    python -m app.scripts.admitad_check

1. Shows whether client_id / client_secret / base64_header are loaded, and
   whether the header really is base64("client_id:client_secret").
2. Requests a client-credentials token (no write scope).
3. Reads the publisher's ad spaces (GET /websites/v2/): name, URL, status.

Prints no credential, token or personal data. Changes nothing in the Admitad
account. Exits non-zero if anything fails, so it can be a deployment check.
"""

from __future__ import annotations

import asyncio
import sys

from app.services.admitad import AdmitadError, configuration, get_json, get_token


async def main() -> int:
    config = configuration()
    print("configuration:", config)
    if not (config["client_id_loaded"] and (config["client_secret_loaded"] or config["base64_header_loaded"])):
        print("FAIL: Admitad credentials are not loaded")
        return 1
    if config["base64_header_matches_id_and_secret"] is False:
        print("WARNING: base64_header is not base64(client_id:client_secret); the token request uses base64_header")

    try:
        token = await get_token(["websites"])
    except AdmitadError as exc:
        print("FAIL: token request:", exc)
        return 1
    print(f"token: OK (scopes granted: {token.scopes}, valid for {token.expires_in}s)")

    try:
        body = await get_json(token, "/websites/v2/", {"limit": 20})
    except AdmitadError as exc:
        print("FAIL: reading ad spaces:", exc)
        return 1
    # answered as a plain list, or as {"results": [...]} with paging
    spaces = body if isinstance(body, list) else body.get("results") or []
    print(f"ad spaces: {len(spaces)}")
    for space in spaces:
        print(f"  - {space.get('name')} | {space.get('site_url')} | status: {space.get('status')}")
    print("OK: Admitad credentials load and the API connection works")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
