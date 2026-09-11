"""A working ProductProvider with no external credentials — proves the
ingestion pipeline (fetch -> normalize -> upsert -> embed) end to end.

Ships the same handful of products the frontend's `/try` demo previously
hardcoded (same names, prices, photos) so flipping the frontend from mock
data to this real API is visually seamless — see apps/web/src/lib/media.ts.
Swap or extend this file with more rows; nothing else changes.
"""

from __future__ import annotations

from app.retailers.base import ProductProvider, RawProduct

_UNSPLASH = "https://images.unsplash.com/photo-{id}?auto=format&fit=crop&w=1200&q=80"


def _img(photo_id: str) -> str:
    return _UNSPLASH.format(id=photo_id)


class SampleCatalogProvider(ProductProvider):
    slug = "sample"
    display_name = "Sample Catalog"

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        products = [
            RawProduct(
                retailer_product_id="sample-cream-knit-poncho",
                name="Cream Knit Poncho",
                brand="Amazon Essentials",
                category_slug="knitwear",
                subcategory="Sweaters",
                gender="women",
                color="Cream",
                sizes=["XS", "S", "M", "L"],
                price_cents=3200,
                description="A relaxed, fringe-hem knit poncho in undyed cream cotton.",
                images=[_img("1434389677669-e08b4cac3105")],
                rating=4.4,
                rating_count=812,
                product_url="https://www.amazon.com/dp/sample-poncho",
                style_tags=["casual", "cozy", "neutral"],
            ),
            RawProduct(
                retailer_product_id="sample-red-evening-dress",
                name="Red Evening Dress",
                brand="Lulus",
                category_slug="dresses",
                subcategory="Evening",
                gender="women",
                color="Red",
                sizes=["XS", "S", "M", "L", "XL"],
                price_cents=4990,
                description="A sweeping floor-length gown in matte satin, built for a grand entrance.",
                images=[_img("1595777457583-95e059d581b8")],
                rating=4.7,
                rating_count=356,
                product_url="https://www.ebay.com/itm/sample-red-dress",
                style_tags=["formal", "evening", "bold"],
            ),
            RawProduct(
                retailer_product_id="sample-rust-bomber-jacket",
                name="Rust Bomber Jacket",
                brand="Levi's",
                category_slug="jackets",
                subcategory="Bombers",
                gender="unisex",
                color="Rust",
                sizes=["S", "M", "L", "XL"],
                price_cents=3499,
                currency="inr",
                description="A lightweight nylon bomber in a warm rust tone, zip pockets, ribbed cuffs.",
                images=[_img("1591047139829-d91aecb6caea")],
                rating=4.3,
                rating_count=201,
                product_url="https://www.flipkart.com/sample-bomber-jacket",
                style_tags=["streetwear", "layering"],
            ),
            RawProduct(
                retailer_product_id="sample-sunset-tracksuit",
                name="Sunset Tracksuit",
                brand="Daraz Active",
                category_slug="activewear",
                subcategory="Tracksuits",
                gender="women",
                color="Yellow",
                sizes=["S", "M", "L"],
                price_cents=5800,
                description="A cropped hoodie and jogger set in a saturated sunset yellow fleece.",
                images=[_img("1515886657613-9f3515b0c78f")],
                rating=4.5,
                rating_count=128,
                product_url="https://www.daraz.pk/sample-tracksuit",
                style_tags=["athleisure", "bold", "streetwear"],
            ),
            RawProduct(
                retailer_product_id="sample-sky-wrap-coat",
                name="Sky Wrap Coat",
                brand="Mango",
                category_slug="coats",
                subcategory="Wrap Coats",
                gender="women",
                color="Blue",
                sizes=["XS", "S", "M", "L"],
                price_cents=12800,
                description="An oversized wool-blend wrap coat in powder blue, belted waist.",
                images=[_img("1539109136881-3be0616acf4b")],
                rating=4.6,
                rating_count=94,
                product_url="https://www.amazon.com/dp/sample-wrap-coat",
                style_tags=["formal", "outerwear", "editorial"],
            ),
            RawProduct(
                retailer_product_id="sample-blush-wrap-coat",
                name="Blush Pink Wrap Coat",
                brand="Zara",
                category_slug="coats",
                subcategory="Wrap Coats",
                gender="women",
                color="Pink",
                sizes=["S", "M", "L"],
                price_cents=9900,
                description="A midi wrap coat in dusty blush wool, patch pockets.",
                images=[_img("1485462537746-965f33f7f6a7")],
                rating=4.2,
                rating_count=67,
                product_url="https://www.ebay.com/itm/sample-pink-coat",
                style_tags=["formal", "outerwear", "romantic"],
            ),
            RawProduct(
                retailer_product_id="sample-classic-denim",
                name="Classic Straight Denim",
                brand="Levi's",
                category_slug="denim",
                subcategory="Jeans",
                gender="unisex",
                color="Indigo",
                sizes=["28", "30", "32", "34", "36"],
                price_cents=6500,
                currency="inr",
                description="Mid-rise straight-leg jeans in classic rigid indigo denim.",
                images=[_img("1576995853123-5a10305d93c0")],
                rating=4.5,
                rating_count=1042,
                product_url="https://www.flipkart.com/sample-denim",
                style_tags=["casual", "everyday"],
            ),
            RawProduct(
                retailer_product_id="sample-teal-crop-top",
                name="Teal Lace Crop Top",
                brand="Daraz Studio",
                category_slug="tops",
                subcategory="Crop Tops",
                gender="women",
                color="Teal",
                sizes=["XS", "S", "M"],
                price_cents=2400,
                description="A fitted lace crop top with adjustable straps in deep teal.",
                images=[_img("1469334031218-e382a71b716b")],
                rating=4.1,
                rating_count=53,
                product_url="https://www.daraz.pk/sample-crop-top",
                style_tags=["going out", "bold", "summer"],
            ),
        ]
        return products[:limit]
