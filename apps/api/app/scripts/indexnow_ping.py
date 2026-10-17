"""Tell Bing, Yandex and other IndexNow search engines that TryOnU's pages
changed, so they (and ChatGPT search / Copilot, which use Bing) pick them up
within hours instead of weeks. Run after a deploy:

    python -m app.scripts.indexnow_ping

Reads every page from https://tryonu.app/sitemap.xml. The key is public by
design: IndexNow checks it at https://tryonu.app/<key>.txt.
"""

from __future__ import annotations

import re
import sys

import httpx

SITE = "https://tryonu.app"
KEY = "f8c9bf429f8d4d3d1b89fd2033c4bcfc"


def main() -> int:
    sitemap = httpx.get(f"{SITE}/sitemap.xml", timeout=30, follow_redirects=True)
    sitemap.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap.text)
    if not urls:
        print("No pages found in the sitemap.")
        return 1
    resp = httpx.post(
        "https://api.indexnow.org/indexnow",
        json={"host": "tryonu.app", "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt", "urlList": urls[:10000]},
        timeout=30,
    )
    print(f"Sent {len(urls)} pages to IndexNow: HTTP {resp.status_code} (200 or 202 = accepted)")
    return 0 if resp.status_code in (200, 202) else 1


if __name__ == "__main__":
    sys.exit(main())
