"""Shared test fixtures.

Everything here runs against an isolated SQLite file (never the dev DB),
with every external provider forced to its offline mock — no FASHN/OpenAI/
Stripe credits are spent running this suite. The env vars below MUST be set
before the first `app.*` import: app/db/session.py builds its engine from
settings at import time, so ordering here is load-bearing.
"""

from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).parent
TEST_DB_PATH = _HERE / "test_tryonu.db"
TEST_STORAGE_DIR = _HERE / "test_storage"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["ENV"] = "development"  # keeps /docs etc. enabled; not "production" behavior
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DEBUG"] = "true"
os.environ["REDIS_URL"] = ""  # force the in-process job runner — no Redis needed for tests
os.environ["VIRTUAL_TRYON_PROVIDER"] = "mock"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["EMAIL_PROVIDER"] = "mock"
os.environ["FASHN_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["S3_ENDPOINT_URL"] = ""
os.environ["S3_ACCESS_KEY_ID"] = ""
os.environ["STORAGE_LOCAL_DIR"] = str(TEST_STORAGE_DIR)
os.environ["CORS_ORIGINS"] = '["http://testserver"]'
os.environ["GEOIP_AUTO_DOWNLOAD"] = "false"
os.environ["GEOIP_DB_PATH"] = str(TEST_STORAGE_DIR / "no-geoip.mmdb")

import contextlib  # noqa: E402
import io  # noqa: E402
import shutil  # noqa: E402
import uuid  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    """Fresh schema once per test session; torn down after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    with contextlib.suppress(FileNotFoundError):
        TEST_DB_PATH.unlink()
    shutil.rmtree(TEST_STORAGE_DIR, ignore_errors=True)


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limits():
    """The in-process rate limiter's buckets are module-level and keyed by
    client IP — every test looks like the same IP through ASGITransport, so
    without this, tests that call auth/tryon/etc. repeatedly would trip
    each other's limits. Real request-level rate limiting is still
    exercised (see test_rate_limit.py); this just isolates test cases."""
    from app.core.rate_limit import _local_buckets

    _local_buckets.clear()
    yield


@pytest.fixture(autouse=True)
def _reset_tryon_providers():
    """Provider factories are lru_cached; a test that swaps in a provider
    must not leave it cached for the next test (a leaked OpenAI provider
    would make later tests try to reach the real API)."""
    from app.ai.providers.registry import get_full_look_provider, get_tryon_provider

    get_tryon_provider.cache_clear()
    get_full_look_provider.cache_clear()
    yield
    get_tryon_provider.cache_clear()
    get_full_look_provider.cache_clear()


def unique_email(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def last_verification_token(email: str) -> str:
    """Pulls the verification token straight out of the mock email
    provider's in-memory record (see app/email/mock.py) instead of
    scraping logs — the registry is a process-wide singleton, so whatever
    register_user()/resend_verification_email() just "sent" is right
    here."""
    import re

    from app.email.registry import get_email_provider

    provider = get_email_provider()
    for msg in reversed(provider.sent):
        if msg["to"] == email and "Verify your TryOnU email" in msg["subject"]:
            match = re.search(r"token=([\w-]+)", msg["body"])
            assert match, f"no token found in verification email body: {msg['body']!r}"
            return match.group(1)
    raise AssertionError(f"no verification email found for {email}")


async def register_and_login(
    client: AsyncClient, *, email: str | None = None, password: str = "password123", verify: bool = True
) -> dict:
    """Registers a fresh user (already funded with the signup bonus — see
    auth_service.register_user) and leaves the client authenticated
    (cookies persist on the shared AsyncClient instance). Returns the
    response JSON.

    By default also verifies the email, since most tests just need a
    verified account and aren't exercising verification itself. Pass
    verify=False for tests of the unverified state."""
    email = email or unique_email()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    if verify:
        token = last_verification_token(email)
        verify_resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert verify_resp.status_code == 200, verify_resp.text
        me = await client.get("/api/v1/auth/me")
        data["user"] = me.json()

    return data


async def make_admin(db, user_id: str) -> None:
    user = await db.get(User, user_id)
    user.is_admin = True
    await db.commit()


def small_jpeg_bytes(size: tuple[int, int] = (400, 500), color=(180, 160, 140)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def seed_product(
    db,
    *,
    name: str = "Test Poncho",
    price_cents: int = 3200,
    image_url: str = "https://images.unsplash.com/photo-1434389677669-e08b4cac3105",
    color: str | None = None,
    style_tags: list[str] | None = None,
    gender: str = "unisex",
):
    """Creates a minimal Retailer + Product directly (no network calls) —
    used by tests that don't need the full ingestion pipeline."""
    from app.models.product import Product, ProductImage
    from app.models.retailer import Retailer
    from sqlalchemy import select

    result = await db.execute(select(Retailer).where(Retailer.slug == "test-retailer"))
    retailer = result.scalar_one_or_none()
    if retailer is None:
        retailer = Retailer(slug="test-retailer", name="Test Retailer")
        db.add(retailer)
        await db.flush()

    product = Product(
        retailer_id=retailer.id,
        retailer_product_id=f"sku-{uuid.uuid4().hex[:8]}",
        name=name,
        price_cents=price_cents,
        currency="usd",
        color=color,
        style_tags=style_tags,
        gender=gender,
        product_url="https://example.com/product",
        affiliate_url="https://example.com/product?tag=test",
    )
    db.add(product)
    await db.flush()
    db.add(ProductImage(product_id=product.id, url=image_url, position=0, is_primary=True))
    await db.commit()
    await db.refresh(product)
    return product


async def seed_credit_package(db, *, name: str = "Test Pack", credits: int = 50, price_cents: int = 499):
    from app.models.credit import CreditPackage

    package = CreditPackage(name=name, credits=credits, price_cents=price_cents, currency="usd")
    db.add(package)
    await db.commit()
    await db.refresh(package)
    return package


async def credit_balance(db, user_id: str) -> int:
    # The try-on worker runs on its own DB session (as it does in
    # production); with expire_on_commit=False, this session's identity
    # map won't see that write until we force a refresh. Refresh only this
    # one object (not expire_all()) — expiring the whole session would
    # leave *other* objects the test still holds (e.g. a seeded Product)
    # needing a lazy reload, which AsyncSession can't do outside an await.
    user = await db.get(User, user_id)
    if user is not None:
        await db.refresh(user)
    return user.credits_balance if user else 0
