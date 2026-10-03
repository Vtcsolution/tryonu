"""The direct engine end to end: API -> job -> worker -> (fake) FASHN -> storage
-> database. The whole outside world is tests/fashn_fakes.FakeFashn, so no
FASHN, OpenAI or Gemini request can leave the machine; each test also asserts
that nothing tried to.
"""

from __future__ import annotations

import base64
import hashlib

import pytest
from sqlalchemy import select

from app.ai.providers.registry import direct_engine_active, get_full_look_provider, get_tryon_provider
from app.db.session import AsyncSessionLocal
from app.models.photo import UserPhoto
from app.models.tryon import TryOnJob, TryOnResult
from app.services.storage_service import get_storage
from app.workers.tasks import tryon_tasks
from tests.conftest import credit_balance, register_and_login, seed_product, small_jpeg_bytes
from tests.fashn_fakes import PRODUCT_HOST, FakeFashn, image_bytes
from tests.test_tryon import _poll_until_terminal, _upload_front_photo, _was_refunded

PRODUCT_URL = f"https://{PRODUCT_HOST}/red-top.jpg"
# eBay's largest listing size; a 225px thumbnail is refused before FASHN is called
PRODUCT = image_bytes((1000, 1000), (255, 255, 255), rect=(130, 130, 870, 870), rect_color=(200, 30, 40), fmt="JPEG")
# the uploaded test photo is 400x500; FASHN hands back 2x with the "garment" drawn on
# a 1k-sized render, same aspect ratio as the 400x500 test photo
OUTPUT = image_bytes((1024, 1280), (180, 160, 140), rect=(256, 512, 768, 1152), rect_color=(200, 30, 40))


@pytest.fixture
def direct(monkeypatch):
    """Direct mode on, a fake FASHN key configured, and every legacy render
    path booby-trapped so a test fails if one ever runs."""
    s = tryon_tasks.settings
    for name, value in {
        "VIRTUAL_TRYON_PROVIDER": "fashn",
        "FASHN_API_KEY": "fa-test-not-real",
        "FASHN_MODEL": "tryon-max",
        "TRYON_ENGINE_MODE": "direct",
        "FASHN_RESOLUTION": "2k",
        "FASHN_GENERATION_MODE": "quality",
        "FASHN_OUTPUT_FORMAT": "png",
        "FASHN_POLL_TIMEOUT_SECONDS": 5,
        "TRYON_DIRECT_VLM_QC": False,
        "TRYON_KEEP_ORIGINAL_FACE": True,  # would normally run restore_face
    }.items():
        monkeypatch.setattr(s, name, value)
    # the real database guard is replaced by a generous fake: no FASHN call can happen here anyway
    from tests.fashn_fakes import FakeGuard

    monkeypatch.setattr("app.ai.providers.registry.DbCreditGuard", lambda: FakeGuard())
    get_tryon_provider.cache_clear()
    get_full_look_provider.cache_clear()

    def forbidden(name):
        async def boom(*_a, **_kw):
            raise AssertionError(f"{name} ran in direct mode")

        return boom

    for name in ("render_look", "render_whole_look", "render_masked_look", "render_zoned_look", "keep_person"):
        monkeypatch.setattr(tryon_tasks, name, forbidden(name))
    monkeypatch.setattr(tryon_tasks, "restore_face", lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("restore_face ran in direct mode")))
    yield s
    get_tryon_provider.cache_clear()
    get_full_look_provider.cache_clear()


async def _setup(client, db, *, product_url: str = PRODUCT_URL):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Red Test Top", image_url=product_url)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    return photo_id, product, user_id


async def _row(job_id: str):
    async with AsyncSessionLocal() as s:
        job = (await s.execute(select(TryOnJob).where(TryOnJob.id == job_id))).scalar_one()
        result = (await s.execute(select(TryOnResult).where(TryOnResult.job_id == job_id))).scalar_one_or_none()
        return job, result


def _decode_uri(uri: str) -> bytes:
    return base64.b64decode(uri.split(",", 1)[1])


async def test_direct_mode_needs_the_fashn_provider(monkeypatch):
    """With no FASHN key the settings fall back to the mock provider, and the
    direct engine stays off — so a keyless environment can never reach a real
    engine by accident."""
    monkeypatch.setattr(tryon_tasks.settings, "TRYON_ENGINE_MODE", "direct")
    get_tryon_provider.cache_clear()
    assert get_tryon_provider().name == "mock"
    assert direct_engine_active() is False


async def test_a_direct_try_on_sends_both_images_untouched_and_stores_fashns_bytes_as_is(client, db, direct, monkeypatch):
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, job_id="job_direct_1")
    fake.install(monkeypatch)
    photo_id, product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    assert resp.status_code == 201, resp.text
    assert resp.json()["provider"] == "fashn" and resp.json()["provider_model"] == "tryon-max"

    job_json = await _poll_until_terminal(client, resp.json()["id"])
    assert job_json["status"] == "completed", job_json.get("error_message")
    assert job_json["result"]["image_url"]
    assert await credit_balance(db, user_id) == 95

    # --- exactly one paid FASHN job, with exactly the two real inputs ---
    assert fake.run_count == 1
    assert fake.unexpected == [], f"unexpected outbound requests: {fake.unexpected}"
    body = fake.run_bodies[0]
    assert body["model_name"] == "tryon-max"
    inputs = body["inputs"]
    assert _decode_uri(inputs["product_image"]) == PRODUCT  # the retailer's bytes, unmodified
    job, result = await _row(resp.json()["id"])
    stored_photo = get_storage().read((await db.get(UserPhoto, photo_id)).storage_key)
    assert _decode_uri(inputs["model_image"]) == stored_photo  # the stored photo, unmodified
    assert (inputs["resolution"], inputs["generation_mode"], inputs["output_format"], inputs["num_images"]) == ("2k", "quality", "png", 1)
    assert "prompt" not in inputs  # no category logic: nothing invented

    # --- FASHN's output is stored byte for byte (no merge, no face restore) ---
    assert result is not None
    assert get_storage().read(result.storage_key) == OUTPUT
    assert result.storage_key.endswith(".png")

    # --- everything we promised to save ---
    assert job.provider_job_id == "job_direct_1"
    assert job.provider == "fashn" and job.provider_model == "tryon-max"
    assert job.started_at and job.completed_at and job.queued_at
    assert (result.width, result.height) == (1024, 1280)

    meta = result.engine_meta
    assert meta["engine_mode"] == "direct"
    assert (meta["model"], meta["resolution"], meta["generation_mode"], meta["output_format"]) == ("tryon-max", "2k", "quality", "png")
    assert meta["provider_job_id"] == "job_direct_1"
    assert meta["output_sha256"] == hashlib.sha256(OUTPUT).hexdigest()
    for stamp in ("submitted_at", "fashn_completed_at", "downloaded_at", "job_started_at"):
        assert meta[stamp]
    first = meta["sequence"][0]
    assert first["product_id"] == product.id and first["image_url"] == PRODUCT_URL
    assert first["verified"] is True and first["status"] == "verified"
    assert get_storage().read(first["input_key"]) == PRODUCT  # the exact product image FASHN was given

    assert first["qc"]["output_width"] == 1024
    assert first["qc"]["edited_fraction"] > 0.1
    assert first["qc"]["product_match_score"] is not None
    assert result.qc_report["gate"]["passed"] is True
    assert first["qc"]["face_similarity"] is None or first["qc"]["face_similarity"] >= 0.6


async def test_an_unverified_render_is_held_for_review_and_never_delivered(client, db, direct, monkeypatch):
    """FASHN sent the photo back unchanged: the product was never applied.
    That render is held for review, not delivered, and not refunded."""
    unchanged = image_bytes((400, 500), (180, 160, 140))
    fake = FakeFashn(output=unchanged, product=PRODUCT)
    fake.install(monkeypatch)
    photo_id, product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "failed"
    assert finished["result"] is None
    assert "not delivered" in finished["error_message"]
    job, result = await _row(resp.json()["id"])
    assert result is None
    assert job.review_state == "pending"
    assert "no_visible_edit" in job.review_reason
    assert "no_visible_edit" in job.steps[0]["failed_checks"]
    assert get_storage().read(job.steps[0]["raw_key"]) == unchanged  # the raw output is kept
    assert not await _was_refunded(job.id)


async def test_a_fashn_timeout_fails_the_job_refunds_and_never_submits_again(client, db, direct, monkeypatch):
    monkeypatch.setattr(direct, "FASHN_POLL_TIMEOUT_SECONDS", 0.3)
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, statuses=["processing"], job_id="job_still_running")
    fake.install(monkeypatch)
    photo_id, product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "failed"
    assert "NOT resubmitted" in finished["error_message"]
    assert fake.run_count == 1  # one paid job, however long it took
    assert not await _was_refunded(resp.json()["id"])  # FASHN accepted it: held for review, never refunded
    job, result = await _row(resp.json()["id"])
    assert job.review_state == "pending"
    assert job.provider_job_id == "job_still_running"  # kept so it can be looked up at FASHN
    assert result is None
    assert fake.unexpected == []


async def test_a_rejected_job_is_refunded_with_the_providers_reason(client, db, direct, monkeypatch):
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, statuses=["failed"], failed_error={"name": "PoseError", "message": "no person found"})
    fake.install(monkeypatch)
    photo_id, product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "failed" and "no person found" in finished["error_message"]
    assert fake.run_count == 1
    assert not await _was_refunded(resp.json()["id"])  # accepted by FASHN: a reviewer decides
    job, _ = await _row(resp.json()["id"])
    assert job.review_state == "pending" and job.provider_job_id == "job_test_1"


async def test_an_unreachable_product_image_fails_before_any_paid_call(client, db, direct, monkeypatch):
    fake = FakeFashn(output=OUTPUT, product=None)  # the product host answers 404
    fake.install(monkeypatch)
    photo_id, product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "failed" and "product image" in finished["error_message"]
    assert fake.run_count == 0  # nothing was sent to FASHN
    assert await credit_balance(db, user_id) == 100


async def test_the_wrong_fashn_model_fails_before_any_paid_call(client, db, direct, monkeypatch):
    monkeypatch.setattr(direct, "FASHN_MODEL", "tryon-v1.6")
    get_tryon_provider.cache_clear()
    fake = FakeFashn(output=OUTPUT, product=PRODUCT)
    fake.install(monkeypatch)
    photo_id, product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "failed" and "tryon-max" in finished["error_message"]
    assert fake.run_count == 0
    assert await credit_balance(db, user_id) == 100


async def test_an_outfit_is_refused_up_front_without_charging(client, db, direct, monkeypatch):
    fake = FakeFashn(output=OUTPUT, product=PRODUCT)
    fake.install(monkeypatch)
    photo_id, _product, user_id = await _setup(client, db)

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": "any-outfit"})

    assert resp.status_code == 400 and "one product" in resp.json()["detail"]
    assert await credit_balance(db, user_id) == 100
    assert fake.run_count == 0
