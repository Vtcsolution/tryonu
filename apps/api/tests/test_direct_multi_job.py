"""The direct worker drawing several products, one FASHN call each, offline.

The FASHN provider is a local fake that paints each product's colour onto the
photo it is given. Nothing here reaches the network or spends a credit.
"""

from __future__ import annotations

import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.providers.base import TryOnOutput, TryOnProviderError
from app.models.enums import OutfitSlot
from app.models.tryon import TryOnJob
from app.services.storage_service import get_storage
from app.workers.tasks import tryon_tasks
from tests.conftest import register_and_login, seed_product
from tests.fashn_fakes import image_bytes
from tests.test_direct_fashn_job import direct  # noqa: F401 — fixture
from tests.test_tryon import _upload_front_photo

RED = (200, 30, 40)
BLUE = (30, 60, 200)
PRODUCT_1 = image_bytes((1000, 1000), (255, 255, 255), rect=(130, 130, 870, 870), rect_color=RED, fmt="JPEG")
PRODUCT_2 = image_bytes((1000, 1000), (255, 255, 255), rect=(130, 130, 870, 870), rect_color=BLUE, fmt="JPEG")
RECT_FOR = {PRODUCT_1: RED, PRODUCT_2: BLUE}


def _decode_uri(uri: str) -> bytes:
    return base64.b64decode(uri.split(",", 1)[1])


class FakeFashnProvider:
    """Paints the product's colour into the photo it receives, like a render would."""

    name = "fashn"
    model = "tryon-max"
    whole_outfit = False
    supports_masked_edit = False
    preserves_person = False

    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call

    async def generate(self, payload, *, on_submitted=None):  # noqa: ANN001
        self.calls += 1
        job_id = f"job_{self.calls}"
        if on_submitted is not None:
            await on_submitted(job_id)
        if self.fail_on_call == self.calls:
            raise TryOnProviderError("FASHN job failed: no person found", provider_job_id=job_id)
        model = Image.open(io.BytesIO(_decode_uri(payload.model_image_url))).convert("RGB")
        model = model.resize((1024, 1280))  # a 1k-sized render, same aspect ratio as the 400x500 photo
        product_bytes = _decode_uri(payload.garment_image_url)
        colour = RECT_FOR[self._match(product_bytes)]
        draw = ImageDraw.Draw(model)
        w, h = model.size
        draw.rectangle([int(w * 0.32), int(h * 0.32), int(w * 0.68), int(h * 0.62)], fill=colour)
        buf = io.BytesIO()
        model.save(buf, format="PNG")
        return TryOnOutput(
            image_bytes=buf.getvalue(),
            content_type="image/png",
            provider_job_id=job_id,
            latency_ms=1,
            meta={"model": "tryon-max", "resolution": "2k", "generation_mode": "quality", "output_format": "png"},
        )

    @staticmethod
    def _match(product_bytes: bytes) -> bytes:
        for original in RECT_FOR:
            if original == product_bytes:
                return original
        raise AssertionError("unknown product image sent to the fake")


def _layer(name: str, product_id: str, url: str):
    return SimpleNamespace(name=name, product_id=product_id, image_url=url, slot=OutfitSlot.TOP)


async def _job_for_two_products(client, db, monkeypatch):  # noqa: ANN001
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    p1 = await seed_product(db, name="Red Top", image_url="https://shop.example/red.jpg")
    p2 = await seed_product(db, name="Blue Scarf", image_url="https://shop.example/blue.jpg")
    images = {"https://shop.example/red.jpg": PRODUCT_1, "https://shop.example/blue.jpg": PRODUCT_2}

    async def fetch(url):  # noqa: ANN001
        return images[url]

    monkeypatch.setattr(tryon_tasks, "fetch_product_image", fetch)
    job = TryOnJob(
        user_id=user_id,
        user_photo_id=photo_id,
        product_id=p1.id,
        provider="fashn",
        provider_model="tryon-max",
        status=tryon_tasks.JobStatus.QUEUED,
        credit_cost=5,
    )
    db.add(job)
    await db.commit()
    layers = [_layer("Red Top", p1.id, "https://shop.example/red.jpg"), _layer("Blue Scarf", p2.id, "https://shop.example/blue.jpg")]
    return job.id, layers


async def _reload(db, job_id: str) -> TryOnJob:  # noqa: ANN001
    db.expire_all()
    row = await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo), selectinload(TryOnJob.result)))
    return row.scalar_one()


async def test_two_products_are_drawn_in_order_and_both_are_delivered(client, db, direct, monkeypatch):  # noqa: F811
    job_id, layers = await _job_for_two_products(client, db, monkeypatch)
    fake = FakeFashnProvider()
    job = (await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))).scalar_one()

    await tryon_tasks._run_direct_job(db, job, fake, layers)

    assert fake.calls == 2  # one FASHN call per product, nothing more
    done = await _reload(db, job_id)
    assert done.status == tryon_tasks.JobStatus.COMPLETED
    assert done.result is not None
    assert [p["name"] for p in done.result.placements] == ["Red Top", "Blue Scarf"]
    assert all(p["drawn"] for p in done.result.placements)
    assert [s["status"] for s in done.result.engine_meta["sequence"]] == ["verified", "verified"]
    assert [s["provider_job_id"] for s in done.result.engine_meta["sequence"]] == ["job_1", "job_2"]
    assert get_storage().read(done.result.storage_key)  # the final image is stored


async def test_a_second_product_that_fails_at_fashn_holds_the_job_and_keeps_the_first(client, db, direct, monkeypatch):  # noqa: F811
    job_id, layers = await _job_for_two_products(client, db, monkeypatch)
    fake = FakeFashnProvider(fail_on_call=2)
    job = (await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))).scalar_one()

    await tryon_tasks._run_direct_job(db, job, fake, layers)

    assert fake.calls == 2
    held = await _reload(db, job_id)
    assert held.status == tryon_tasks.JobStatus.FAILED
    assert held.result is None  # never delivered as a look
    assert held.review_state == "pending"
    assert held.provider_job_id == "job_2"
    first, second = held.steps
    assert first["status"] == "verified" and first["raw_key"]  # the first product's raw output is kept
    assert second["status"] == "sent" and second["provider_job_id"] == "job_2"
    assert "no person found" in held.review_reason or "failed" in held.review_reason


async def test_a_look_over_the_product_limit_is_refused_before_any_call(client, db, direct, monkeypatch):  # noqa: F811
    job_id, layers = await _job_for_two_products(client, db, monkeypatch)
    monkeypatch.setattr(direct, "TRYON_DIRECT_MAX_FASHN_CREDITS", 4)  # 2 products x 4 credits = 8 > 4
    fake = FakeFashnProvider()
    job = (await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))).scalar_one()

    await tryon_tasks._run_direct_job(db, job, fake, layers)

    assert fake.calls == 0
    refused = await _reload(db, job_id)
    assert refused.status == tryon_tasks.JobStatus.FAILED
    assert "FASHN credits" in refused.error_message
    assert refused.review_state is None  # nothing was billed, so nothing is held
