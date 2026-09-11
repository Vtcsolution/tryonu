"""Every known ProductProvider, regardless of whether it's actually
configured — the ingestion service (services/product_ingestion_service.py)
tries each and skips the ones that raise RetailerNotConfiguredError. Add a
retailer by adding one adapter class + one line here.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.retailers.amazon import AmazonProductProvider
from app.retailers.base import ProductProvider
from app.retailers.daraz import DarazProductProvider
from app.retailers.ebay import EbayProductProvider
from app.retailers.flipkart import FlipkartProductProvider
from app.retailers.sample import SampleCatalogProvider


def get_all_providers() -> list[ProductProvider]:
    settings = get_settings()
    return [
        SampleCatalogProvider(),
        AmazonProductProvider(
            access_key=settings.AMAZON_ACCESS_KEY,
            secret_key=settings.AMAZON_SECRET_KEY,
            partner_tag=settings.AMAZON_PARTNER_TAG,
        ),
        EbayProductProvider(
            client_id=settings.EBAY_CLIENT_ID,
            client_secret=settings.EBAY_CLIENT_SECRET,
            campaign_id=settings.EBAY_CAMPAIGN_ID,
        ),
        FlipkartProductProvider(
            affiliate_id=settings.FLIPKART_AFFILIATE_ID,
            affiliate_token=settings.FLIPKART_AFFILIATE_TOKEN,
        ),
        DarazProductProvider(api_key=settings.DARAZ_API_KEY),
    ]
