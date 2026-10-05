"""A look of 2+ products drawn in ONE Gemini generation, offline.

The Gemini provider is replaced by a local fake; FASHN must never be called.
Nothing here reaches the network or spends anything.
"""

from __future__ import annotations

import base64
import io
from types import SimpleNamespace

from PIL import Image
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


class FakeGemini:
    instances: list["FakeGemini"] = []

    def __init__(self, *, api_key, model, image_size="2K", fail=False):  # noqa: ANN001
        self.name, self.model = "gemini", model
        self.calls: list[tuple[str, list]] = []
        self.fail = fail
        FakeGemini.instances.append(self)

    async def generate_outfit(self, model_image_url, pieces):  # noqa: ANN001
        self.calls.append((model_image_url, pieces))
        if self.fail:
            raise TryOnProviderError("Gemini returned no image: refused")
        data = base64.b64decode(model_image_url.split(",", 1)[1])
        person = Image.open(io.BytesIO(data)).convert("RGB").resize((1024, 1280))
        buf = io.BytesIO()
        person.save(buf, format="PNG")
        return TryOnOutput(image_bytes=buf.getvalue(), content_type="image/png", latency_ms=1)


class NeverFashn:
    name, model = "fashn", "tryon-max"

    async def credits_available(self):
        raise AssertionError("FASHN must not be asked about a one-call look")

    async def generate(self, *_a, **_kw):  # noqa: ANN002, ANN003
        raise AssertionError("FASHN must not be called for a one-call look")


async def _job(client, db, monkeypatch, n: int = 2):  # noqa: ANN001
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    images, layers = {}, []
    for i in range(n):
        url = f"https://shop.example/p{i}.jpg"
        product = await seed_product(db, name=f"Product {i}", image_url=url)
        images[url] = image_bytes(
            (1000, 1000), (255, 255, 255), rect=(130, 130, 870, 870), rect_color=(10 * i, 60, 200), fmt="JPEG"
        )
        layers.append(SimpleNamespace(name=f"Product {i}", product_id=product.id, image_url=url, slot=OutfitSlot.ACCESSORY))

    async def fetch(url):  # noqa: ANN001
        return images[url]

    monkeypatch.setattr(tryon_tasks, "fetch_product_image", fetch)
    job = TryOnJob(
        user_id=user_id,
        user_photo_id=photo_id,
        provider="fashn",
        provider_model="tryon-max",
        status=tryon_tasks.JobStatus.QUEUED,
        credit_cost=8,
    )
    db.add(job)
    await db.commit()
    loaded = (
        await db.execute(select(TryOnJob).where(TryOnJob.id == job.id).options(selectinload(TryOnJob.user_photo)))
    ).scalar_one()
    return loaded, layers


async def _reload(db, job_id):  # noqa: ANN001
    db.expire_all()
    return (
        await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.result)))
    ).scalar_one()


def _use_gemini(monkeypatch, direct, **kw):  # noqa: ANN001
    FakeGemini.instances.clear()
    monkeypatch.setattr(direct, "TRYON_MULTI_ENGINE", "gemini_single")
    monkeypatch.setattr(direct, "GEMINI_API_KEY", "g-test-not-real")
    monkeypatch.setattr(tryon_tasks, "GeminiImageTryOnProvider", lambda **a: FakeGemini(**a, **kw))


async def test_two_products_are_drawn_in_one_gemini_call_and_never_through_fashn(client, db, direct, monkeypatch):  # noqa: F811
    _use_gemini(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=2)

    await tryon_tasks._run_direct_job(db, job, NeverFashn(), layers)

    gemini = FakeGemini.instances[0]
    assert len(gemini.calls) == 1  # one generation for the whole look
    assert [p.name for p in gemini.calls[0][1]] == ["Product 0", "Product 1"]  # every product, one request
    done = await _reload(db, job.id)
    assert done.status == tryon_tasks.JobStatus.COMPLETED and done.provider == "gemini"
    raw = get_storage().read(done.steps[0]["raw_key"])
    assert get_storage().read(done.result.storage_key) == raw  # delivered exactly as generated
    # the vision check is off here, so nothing is claimed as confirmed
    assert [p["drawn"] for p in done.result.placements] == [False, False]
    assert all("not_checked" in s["failed_checks"] for s in done.steps)


async def test_the_vision_check_confirms_each_product_it_can_see(client, db, direct, monkeypatch):  # noqa: F811
    _use_gemini(monkeypatch, direct)
    monkeypatch.setattr(direct, "TRYON_DIRECT_VLM_QC", True)
    monkeypatch.setattr(direct, "OPENAI_API_KEY", "sk-test-not-real")

    async def vlm(original, final, images, names):  # noqa: ANN001
        ok = {"present": True, "color_correct": True, "details_preserved": True, "placement_correct": True}
        return {"enabled": True, "same_person": True, "products": [{"index": 0, **ok}, {"index": 1, **ok, "present": False}]}

    monkeypatch.setattr(tryon_tasks, "vlm_final_check", vlm)
    job, layers = await _job(client, db, monkeypatch, n=2)
    await tryon_tasks._run_direct_job(db, job, NeverFashn(), layers)

    done = await _reload(db, job.id)
    assert done.status == tryon_tasks.JobStatus.COMPLETED
    assert [p["drawn"] for p in done.result.placements] == [True, False]
    assert done.result.placements[1]["verification"] == "REVIEW_REQUIRED"


async def test_a_different_person_is_held_and_not_shown(client, db, direct, monkeypatch):  # noqa: F811
    _use_gemini(monkeypatch, direct)
    monkeypatch.setattr(direct, "TRYON_DIRECT_VLM_QC", True)
    monkeypatch.setattr(direct, "OPENAI_API_KEY", "sk-test-not-real")

    async def vlm(original, final, images, names):  # noqa: ANN001
        return {"enabled": True, "same_person": False, "products": []}

    monkeypatch.setattr(tryon_tasks, "vlm_final_check", vlm)
    job, layers = await _job(client, db, monkeypatch, n=2)
    await tryon_tasks._run_direct_job(db, job, NeverFashn(), layers)

    held = await _reload(db, job.id)
    assert held.status == tryon_tasks.JobStatus.FAILED and held.result is None
    assert held.review_state == "pending" and held.provider == "gemini"
    assert get_storage().read(held.review_payload["storage_key"])  # kept for a reviewer


async def test_a_gemini_failure_refunds_and_shows_why(client, db, direct, monkeypatch):  # noqa: F811
    _use_gemini(monkeypatch, direct, fail=True)
    job, layers = await _job(client, db, monkeypatch, n=2)
    await tryon_tasks._run_direct_job(db, job, NeverFashn(), layers)

    failed = await _reload(db, job.id)
    assert failed.status == tryon_tasks.JobStatus.FAILED
    assert "could not draw this look" in failed.error_message


async def test_more_products_than_one_call_can_carry_is_refused_before_any_call(client, db, direct, monkeypatch):  # noqa: F811
    _use_gemini(monkeypatch, direct)
    monkeypatch.setattr(direct, "TRYON_DIRECT_MAX_PRODUCTS", 20)
    job, layers = await _job(client, db, monkeypatch, n=16)
    await tryon_tasks._run_direct_job(db, job, NeverFashn(), layers)

    refused = await _reload(db, job.id)
    assert refused.status == tryon_tasks.JobStatus.FAILED
    assert "at most 15 products" in refused.error_message
    assert not FakeGemini.instances or not FakeGemini.instances[0].calls


async def test_a_single_product_still_goes_to_fashn(client, db, direct, monkeypatch):  # noqa: F811
    _use_gemini(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=1)

    class OneFashn(NeverFashn):
        calls = 0

        async def credits_available(self):
            return 100

        async def generate(self, payload, *, on_submitted=None, purpose=""):  # noqa: ANN001
            OneFashn.calls += 1
            raise TryOnProviderError("stop here")

    await tryon_tasks._run_direct_job(db, job, OneFashn(), layers)
    assert OneFashn.calls == 1 and not FakeGemini.instances


def test_the_vision_checks_answer_decides_identity_over_the_pixel_comparison():
    """Live: all five products verified, vision check "same person: true", and
    the look was held because the pixel face score was 0.50 behind sunglasses."""
    assert tryon_tasks._identity_ok(["face_changed"], {"same_person": True}, ["Gucci Oversized Sunglasses"])
    assert not tryon_tasks._identity_ok([], {"same_person": False}, ["Linen Shirt"])


def test_without_a_vision_answer_eyewear_does_not_count_as_a_changed_face():
    assert tryon_tasks._identity_ok(["face_changed"], {"enabled": False}, ["Square Sunglasses", "Jeans"])
    assert not tryon_tasks._identity_ok(["face_changed"], {"enabled": False}, ["Linen Shirt", "Jeans"])
