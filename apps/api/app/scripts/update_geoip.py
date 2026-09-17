"""Download/refresh the local IP-to-country database used by visitor analytics.

    python -m app.scripts.update_geoip

DB-IP publishes a new free "IP to Country Lite" file monthly; running this
monthly (e.g. from cron) keeps country data current.
"""

from __future__ import annotations

import asyncio
import sys

from app.services.analytics_service import download_geoip_db, geoip_path


async def main() -> int:
    if await download_geoip_db():
        print(f"GeoIP database saved to {geoip_path()}")
        return 0
    print("Could not download the GeoIP database — check network access to download.db-ip.com")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
