"""Every known ProductProvider, regardless of whether it's actually
configured — the ingestion service (services/product_ingestion_service.py)
tries each and skips the ones that raise RetailerNotConfiguredError. Add a
retailer by adding one adapter class + one line here.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.retailers.aliexpress import AliExpressProductProvider
from app.retailers.amazon import AmazonProductProvider
from app.retailers.base import ProductProvider
from app.retailers.cj import CJProductProvider
from app.retailers.daraz import DarazProductProvider
from app.retailers.ebay import EbayProductProvider
from app.retailers.flipkart import FlipkartProductProvider
from app.retailers.rakuten import RakutenProductProvider


def get_rakuten_provider() -> RakutenProductProvider:
    """Separate accessor (not just part of get_all_providers()) — the
    admin advertisers/partnerships/offers/coupons endpoints need a
    concrete RakutenProductProvider, not just a generic ProductProvider."""
    settings = get_settings()
    return RakutenProductProvider(
        enabled=settings.RAKUTEN_ENABLED,
        client_id=settings.RAKUTEN_CLIENT_ID,
        client_secret=settings.RAKUTEN_CLIENT_SECRET,
        access_token=settings.RAKUTEN_TOKEN,
        refresh_token=settings.RAKUTEN_REFRESH_TOKEN,
        publisher_id=settings.RAKUTEN_PUBLISHER_ID,
        account_id=settings.RAKUTEN_ACCOUNT_ID,
        base_url=settings.RAKUTEN_API_BASE_URL,
    )


def get_all_providers() -> list[ProductProvider]:
    """Real retailers only — app/retailers/sample.py (SampleCatalogProvider)
    is deliberately excluded here. It was only ever a bootstrap fixture to
    prove the ingestion pipeline before any real retailer was configured;
    now that eBay/CJ/Rakuten are live, syncing its fake demo rows back in
    (and re-marking them is_active on every run) would mix fake products
    into real search/AI-stylist results indistinguishably from real ones.
    The class stays importable for tests, which construct it directly."""
    settings = get_settings()
    return [
        AmazonProductProvider(
            access_key=settings.AMAZON_ACCESS_KEY,
            secret_key=settings.AMAZON_SECRET_KEY,
            partner_tag=settings.AMAZON_PARTNER_TAG,
            marketplace=settings.AMAZON_MARKETPLACE,
        ),
        EbayProductProvider(
            client_id=settings.EBAY_CLIENT_ID,
            client_secret=settings.EBAY_CLIENT_SECRET,
            campaign_id=settings.EBAY_CAMPAIGN_ID,
            marketplace_id=settings.EBAY_MARKETPLACE_ID,
        ),
        CJProductProvider(
            api_token=settings.CJ_API_TOKEN,
            company_id=settings.CJ_WEBSITE_ID,
        ),
        FlipkartProductProvider(
            affiliate_id=settings.FLIPKART_AFFILIATE_ID,
            affiliate_token=settings.FLIPKART_AFFILIATE_TOKEN,
        ),
        DarazProductProvider(api_key=settings.DARAZ_API_KEY),
        AliExpressProductProvider(
            app_key=settings.ALIEXPRESS_APP_KEY,
            app_secret=settings.ALIEXPRESS_APP_SECRET,
            tracking_id=settings.ALIEXPRESS_TRACKING_ID,
            ship_to_country=settings.ALIEXPRESS_SHIP_TO_COUNTRY,
            currency=settings.ALIEXPRESS_CURRENCY,
        ),
        get_rakuten_provider(),
    ]
