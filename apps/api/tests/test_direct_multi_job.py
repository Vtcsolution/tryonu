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

    def __init__(self, *, fail_on_call: int | None = None, available: int = 1000) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call
        self.available = available

    async def credits_available(self) -> int:
        return self.available

    async def generate(self, payload, *, on_submitted=None, purpose=""):  # noqa: ANN001
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
        top = 0.30 if colour == RED else 0.66  # the top in one place, the scarf in another
        draw.rectangle([int(w * 0.32), int(h * top), int(w * 0.68), int(h * (top + 0.25))], fill=colour)
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


async def test_a_look_the_authorization_cannot_finish_is_refused_before_any_call(client, db, direct, monkeypatch):  # noqa: F811
    job_id, layers = await _job_for_two_products(client, db, monkeypatch)
    fake = FakeFashnProvider(available=5)  # 2 products x 4 credits = 8 needed
    job = (await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))).scalar_one()

    await tryon_tasks._run_direct_job(db, job, fake, layers)

    assert fake.calls == 0
    refused = await _reload(db, job_id)
    assert refused.status == tryon_tasks.JobStatus.FAILED
    assert "needs 8 FASHN credits" in refused.error_message and "allows 5" in refused.error_message
    assert refused.review_state is None


async def test_a_product_the_final_check_cannot_confirm_is_delivered_but_not_claimed(client, db, direct, monkeypatch):  # noqa: F811
    job_id, layers = await _job_for_two_products(client, db, monkeypatch)
    fake = FakeFashnProvider()
    job = (await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))).scalar_one()

    async def unconfirmed(*_a, **_kw):  # noqa: ANN002, ANN003
        return {
            "passed": False,
            "identity_ok": True,
            "products": [
                {"index": 0, "name": "Red Top", "status": "review_required"},
                {"index": 1, "name": "Blue Scarf", "status": "verified"},
            ],
            "vlm": {"enabled": False},
        }

    monkeypatch.setattr(tryon_tasks, "final_check", unconfirmed)
    await tryon_tasks._run_direct_job(db, job, fake, layers)

    done = await _reload(db, job_id)
    assert done.status == tryon_tasks.JobStatus.COMPLETED
    assert [p["drawn"] for p in done.result.placements] == [False, True]
    assert done.result.qc_report["confirmed"] == 1


async def test_a_changed_person_in_the_final_image_is_held_not_delivered(client, db, direct, monkeypatch):  # noqa: F811
    job_id, layers = await _job_for_two_products(client, db, monkeypatch)
    fake = FakeFashnProvider()
    job = (await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))).scalar_one()

    async def other_person(*_a, **_kw):  # noqa: ANN002, ANN003
        return {"passed": False, "identity_ok": False, "products": [
            {"index": 0, "name": "Red Top", "status": "verified"},
            {"index": 1, "name": "Blue Scarf", "status": "verified"},
        ], "vlm": {"enabled": True, "same_person": False}}

    monkeypatch.setattr(tryon_tasks, "final_check", other_person)
    await tryon_tasks._run_direct_job(db, job, fake, layers)

    held = await _reload(db, job_id)
    assert held.status == tryon_tasks.JobStatus.FAILED and held.result is None
    assert held.review_state == "pending"
    assert get_storage().read(held.review_payload["storage_key"])  # kept for the reviewer


async def test_every_selected_product_is_sent_even_when_two_share_a_slot(db):
    """render_plan keeps one item per slot and lets a dress drop separate
    trousers. The direct engine sends everything the shopper selected."""
    from app.models.outfit import Outfit, OutfitItem

    kameez = await seed_product(db, name="White Shalwar Kameez", image_url="https://shop.example/k.jpg")
    trousers = await seed_product(db, name="White Trousers", image_url="https://shop.example/t.jpg")
    ring = await seed_product(db, name="Silver Ring", image_url="https://shop.example/r.jpg")
    bangle = await seed_product(db, name="Gold Bangle", image_url="https://shop.example/b.jpg")
    owner = (await db.execute(select(TryOnJob.user_id).limit(1))).scalar()
    if owner is None:
        from app.models.user import User

        user = User(email="slots@tryonu.app", hashed_password="x", full_name="Slots")
        db.add(user)
        await db.flush()
        owner = user.id
    outfit = Outfit(user_id=owner)
    db.add(outfit)
    await db.flush()
    for pos, (product, slot) in enumerate(
        [(kameez, OutfitSlot.DRESS), (trousers, OutfitSlot.BOTTOM), (ring, OutfitSlot.ACCESSORY), (bangle, OutfitSlot.ACCESSORY)]
    ):
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()

    job = SimpleNamespace(outfit_id=outfit.id, product=None, wardrobe_item=None)
    layers, missing = await tryon_tasks._direct_layers(db, job)

    assert missing == []
    assert sorted(layer.name for layer in layers) == ["Gold Bangle", "Silver Ring", "White Shalwar Kameez", "White Trousers"]
    assert layers[0].name == "White Shalwar Kameez"  # base garment first, accessories last
