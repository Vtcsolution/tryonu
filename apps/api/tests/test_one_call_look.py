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

    async def describe(image, url, name):  # noqa: ANN001 — never the real (paid) vision call
        return f"exact details of {name}"

    monkeypatch.setattr(tryon_tasks, "describe_product", describe)


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
    sent = FakeGemini.instances[0].calls[0][1]
    assert [p.description for p in sent] == ["exact details of Product 0", "exact details of Product 1"]
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


class PaintingFashn:
    """FASHN stand-in: returns the photo it was given at a 1k size with the
    garment painted on, and records how much budget it was asked for."""

    name, model = "fashn", "tryon-max"

    def __init__(self, available: int = 100) -> None:
        self.calls: list[str] = []
        self.available = available
        self.outputs: list[bytes] = []

    async def credits_available(self) -> int:
        return self.available

    async def generate(self, payload, *, on_submitted=None, purpose=""):  # noqa: ANN001
        from PIL import ImageDraw

        self.calls.append(purpose)
        if on_submitted is not None:
            await on_submitted(f"fashn_{len(self.calls)}")
        data = base64.b64decode(payload.model_image_url.split(",", 1)[1])
        img = Image.open(io.BytesIO(data)).convert("RGB").resize((1024, 1280))
        ImageDraw.Draw(img).rectangle([300, 400, 720, 1100], fill=(120, 20, 40))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.outputs.append(buf.getvalue())
        return TryOnOutput(image_bytes=buf.getvalue(), content_type="image/png", provider_job_id=f"fashn_{len(self.calls)}", latency_ms=1)


def _use_hybrid(monkeypatch, direct):  # noqa: ANN001
    _use_gemini(monkeypatch, direct)
    monkeypatch.setattr(direct, "TRYON_MULTI_ENGINE", "hybrid")


async def test_a_hybrid_look_draws_the_garment_with_fashn_and_the_rest_in_one_gemini_call(client, db, direct, monkeypatch):  # noqa: F811
    _use_hybrid(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=3)
    layers[1].slot = OutfitSlot.DRESS  # the lehenga, picked second, is drawn first
    fashn = PaintingFashn(available=4)  # 2k quality in tests = 4 credits: exactly one garment

    await tryon_tasks._run_direct_job(db, job, fashn, layers)

    assert len(fashn.calls) == 1  # only the garment through FASHN
    gemini = FakeGemini.instances[0]
    assert len(gemini.calls) == 1  # every other product in one call
    base_sent, pieces = gemini.calls[0]
    assert [p.name for p in pieces] == ["Product 0", "Product 2"]
    assert base64.b64decode(base_sent.split(",", 1)[1]) == fashn.outputs[0]  # drawn on FASHN's image
    done = await _reload(db, job.id)
    assert done.status == tryon_tasks.JobStatus.COMPLETED
    assert done.provider == "fashn+gemini"
    assert [s["name"] for s in done.steps] == ["Product 1", "Product 0", "Product 2"]
    assert done.steps[0]["provider_job_id"] == "fashn_1"
    assert [p["name"] for p in done.result.placements] == ["Product 1", "Product 0", "Product 2"]


async def test_a_hybrid_look_needs_fashn_credits_only_for_the_garments(client, db, direct, monkeypatch):  # noqa: F811
    _use_hybrid(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=4)
    layers[0].slot = OutfitSlot.DRESS
    fashn = PaintingFashn(available=3)  # less than one garment's 4 credits

    await tryon_tasks._run_direct_job(db, job, fashn, layers)

    refused = await _reload(db, job.id)
    assert refused.status == tryon_tasks.JobStatus.FAILED
    assert refused.error_message == tryon_tasks.PAUSED_MESSAGE
    assert fashn.calls == [] and not FakeGemini.instances


async def test_a_hybrid_look_with_no_garment_is_one_gemini_call(client, db, direct, monkeypatch):  # noqa: F811
    _use_hybrid(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=3)  # all accessories
    fashn = PaintingFashn()

    await tryon_tasks._run_direct_job(db, job, fashn, layers)

    assert fashn.calls == []
    assert len(FakeGemini.instances[0].calls) == 1


class RecordingFashn(PaintingFashn):
    def __init__(self, available: int = 100) -> None:
        super().__init__(available)
        self.payloads = []

    async def generate(self, payload, *, on_submitted=None, purpose=""):  # noqa: ANN001
        self.payloads.append(payload)
        return await super().generate(payload, on_submitted=on_submitted, purpose=purpose)


def _use_board(monkeypatch, direct):  # noqa: ANN001
    _use_gemini(monkeypatch, direct)
    monkeypatch.setattr(direct, "TRYON_MULTI_ENGINE", "fashn_board")

    def no_cutout(*_a, **_kw):  # noqa: ANN002, ANN003 — the board keeps the plain photo
        raise RuntimeError("cutout disabled in tests")

    monkeypatch.setattr("app.services.tryon_quality.cutout.product_cutout_mask", no_cutout)


async def test_a_board_look_is_one_fashn_call_with_every_product_in_one_image(client, db, direct, monkeypatch):  # noqa: F811
    _use_board(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=4)
    layers[0].slot = OutfitSlot.DRESS
    layers[0].name = "Pink Bridal Dress"
    layers[1].name = "Gold Jhumka Earrings"
    fashn = RecordingFashn(available=4)  # exactly one 2k-quality render in tests

    await tryon_tasks._run_direct_job(db, job, fashn, layers)

    assert len(fashn.calls) == 1 and not FakeGemini.instances  # one FASHN call, no Gemini
    payload = fashn.payloads[0]
    board = Image.open(io.BytesIO(base64.b64decode(payload.garment_image_url.split(",", 1)[1])))
    assert board.size == (1536, 2048)  # the composed look, not one product photo
    assert "Earrings" in payload.prompt and "Outfit" in payload.prompt
    done = await _reload(db, job.id)
    assert done.status == tryon_tasks.JobStatus.COMPLETED and done.provider == "fashn"
    assert len(done.result.placements) == 4
    assert all(s["board_key"] and s["provider_job_id"] == "fashn_1" for s in done.steps)


async def test_a_board_look_the_authorization_cannot_cover_is_refused_before_any_call(client, db, direct, monkeypatch):  # noqa: F811
    _use_board(monkeypatch, direct)
    job, layers = await _job(client, db, monkeypatch, n=3)
    fashn = RecordingFashn(available=3)  # one render costs 4 here

    await tryon_tasks._run_direct_job(db, job, fashn, layers)

    refused = await _reload(db, job.id)
    assert refused.status == tryon_tasks.JobStatus.FAILED and refused.error_message == tryon_tasks.PAUSED_MESSAGE
    assert fashn.calls == []


async def test_small_jewellery_on_a_board_is_also_described_in_words(client, db, direct, monkeypatch):  # noqa: F811
    # Live: a plain nose hoop photographed on a nose came out as a nath on a chain.
    _use_board(monkeypatch, direct)
    monkeypatch.setattr(direct, "OPENAI_API_KEY", "sk-test-not-real")

    async def describe(image, url, name):  # noqa: ANN001 — never the real (paid) vision call
        return "thin plain gold hoop nose ring, no chain" if "Nose" in name else f"details of {name}"

    monkeypatch.setattr(tryon_tasks, "describe_product", describe)
    job, layers = await _job(client, db, monkeypatch, n=2)
    layers[0].slot, layers[0].name = OutfitSlot.DRESS, "Pink Bridal Lehenga"
    layers[1].name = "14k Gold Nose Hoop Ring"
    fashn = RecordingFashn(available=4)

    await tryon_tasks._run_direct_job(db, job, fashn, layers)

    prompt = fashn.payloads[0].prompt
    assert "Nose ring: thin plain gold hoop nose ring, no chain." in prompt
    assert "Pink Bridal Lehenga" not in prompt  # clothing is not described, only the small pieces
