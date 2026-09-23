"""Amazon PA-API 5.0 provider: signing and response mapping.

No real PA-API call is made (there are no credentials, and access needs an
Associates account with 3 qualifying sales). What is pinned here is the
part that silently breaks otherwise: the AWS Signature V4 computation,
recomputed independently below, and the documented SearchItems response
shape.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
import pytest

from app.retailers.amazon import AmazonProductProvider
from app.retailers.errors import RetailerNotConfiguredError

KEY, SECRET, TAG = "AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "tryonu-20"


def _provider(**kw) -> AmazonProductProvider:
    return AmazonProductProvider(
        access_key=kw.pop("access_key", KEY),
        secret_key=kw.pop("secret_key", SECRET),
        partner_tag=kw.pop("partner_tag", TAG),
        **kw,
    )


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _item(**over) -> dict:
    item = {
        "ASIN": "B07XYZ1234",
        "DetailPageURL": "https://www.amazon.com/dp/B07XYZ1234?tag=tryonu-20",
        "ItemInfo": {
            "Title": {"DisplayValue": "Embroidered Cotton Kurta Set for Women"},
            "ByLineInfo": {"Brand": {"DisplayValue": "Libas"}},
            "Classifications": {"ProductGroup": {"DisplayValue": "Apparel"}},
        },
        "Images": {
            "Primary": {"Large": {"URL": "https://m.media-amazon.com/images/I/main.jpg"}},
            "Variants": [{"Large": {"URL": "https://m.media-amazon.com/images/I/alt.jpg"}}],
        },
        "Offers": {
            "Listings": [
                {"Price": {"Amount": 41.99, "Currency": "USD"}, "Availability": {"Message": "In Stock"}}
            ]
        },
    }
    item.update(over)
    return item


async def test_without_credentials_it_says_what_is_missing_and_why():
    with pytest.raises(RetailerNotConfiguredError, match="qualifying sales"):
        await _provider(access_key=None).search_live(query="kurta", limit=5)


async def test_the_request_is_signed_the_way_aws_verifies_it(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content.decode()
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"SearchResult": {"Items": [_item()]}})

    _patch_transport(monkeypatch, handler)
    await _provider().search_live(query="kurta set", limit=5)

    assert seen["url"] == "https://webservices.amazon.com/paapi5/searchitems"
    headers = seen["headers"]
    assert headers["x-amz-target"] == "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    assert headers["content-encoding"] == "amz-1.0"

    body = json.loads(seen["body"])
    assert body["Keywords"] == "kurta set"
    assert body["PartnerTag"] == TAG and body["PartnerType"] == "Associates"
    assert body["ItemCount"] == 5
    # PA-API returns only the ASIN unless every field is named
    assert "ItemInfo.Title" in body["Resources"] and "Offers.Listings.Price" in body["Resources"]

    # recompute the signature independently, the way AWS does
    stamp = headers["x-amz-date"]
    day = stamp[:8]
    canonical = "\n".join(
        [
            "POST",
            "/paapi5/searchitems",
            "",
            "content-encoding:amz-1.0\nhost:webservices.amazon.com\n"
            f"x-amz-date:{stamp}\nx-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems\n",
            "content-encoding;host;x-amz-date;x-amz-target",
            hashlib.sha256(seen["body"].encode()).hexdigest(),
        ]
    )
    scope = f"{day}/us-east-1/ProductAdvertisingAPI/aws4_request"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )

    def sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    key = sign(sign(sign(sign(f"AWS4{SECRET}".encode(), day), "us-east-1"), "ProductAdvertisingAPI"), "aws4_request")
    expected = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    assert f"Signature={expected}" in headers["authorization"]


def test_the_signing_stamp_is_utc_to_the_second():
    """A signature is rejected if the stamp drifts from the header, or
    isn't the basic ISO form AWS expects."""
    provider = _provider()
    moment = datetime(2026, 9, 23, 14, 5, 6, tzinfo=timezone.utc)
    headers = provider._headers("{}", moment)
    assert headers["x-amz-date"] == "20260923T140506Z"
    assert "Credential=AKIDEXAMPLE/20260923/us-east-1/ProductAdvertisingAPI/aws4_request" in headers["Authorization"]


async def test_a_marketplace_picks_its_own_host_and_region(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"SearchResult": {"Items": []}})

    _patch_transport(monkeypatch, handler)
    await _provider(marketplace="www.amazon.ae").search_live(query="abaya", limit=3)
    assert seen["url"].startswith("https://webservices.amazon.ae/")
    assert "/eu-west-1/ProductAdvertisingAPI/" in seen["auth"]


async def test_an_item_maps_onto_our_shape(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"SearchResult": {"Items": [_item()]}}))
    [product] = await _provider().search_live(query="kurta", limit=5)
    assert product.retailer_product_id == "B07XYZ1234"
    assert product.name == "Embroidered Cotton Kurta Set for Women"
    assert product.price_cents == 4199 and product.currency == "usd"
    assert product.brand == "Libas"
    assert product.images == [
        "https://m.media-amazon.com/images/I/main.jpg",
        "https://m.media-amazon.com/images/I/alt.jpg",
    ]
    assert product.availability == "in_stock"


async def test_items_with_no_price_or_picture_are_dropped(monkeypatch):
    items = [
        _item(),
        _item(ASIN="no-offer", Offers={"Listings": []}),
        _item(ASIN="no-image", Images={}),
    ]
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"SearchResult": {"Items": items}}))
    found = await _provider().search_live(query="kurta", limit=10)
    assert [p.retailer_product_id for p in found] == ["B07XYZ1234"]


async def test_amazons_own_refusal_is_reported_not_swallowed(monkeypatch):
    """"Your account is not eligible" arrives as an Errors array — showing
    it beats a bare 401 when someone is wondering why Amazon is quiet."""
    body = {"Errors": [{"Code": "UnrecognizedClient", "Message": "The Access Key ID is not enabled"}]}
    _patch_transport(monkeypatch, lambda r: httpx.Response(401, json=body))
    with pytest.raises(RuntimeError, match="Access Key ID is not enabled"):
        await _provider().search_live(query="kurta", limit=5)


async def test_a_link_that_already_has_our_tag_is_left_alone():
    provider = _provider()
    tagged = "https://www.amazon.com/dp/B07XYZ1234?tag=tryonu-20"
    assert provider.build_affiliate_url(tagged, tracking_tag="other") == tagged
    plain = "https://www.amazon.com/dp/B07XYZ1234"
    assert provider.build_affiliate_url(plain, tracking_tag="other") == f"{plain}?tag={TAG}"
