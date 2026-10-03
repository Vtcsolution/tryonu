"""The FASHN provider's money rules and the direct engine's QC, offline.

Every FASHN/CDN call goes to tests/fashn_fakes.FakeFashn — an in-memory
stand-in that records what it was sent. Nothing reaches the network.
"""

from __future__ import annotations

import base64
import hashlib

import numpy as np
import pytest

from app.ai.providers.base import TryOnInput, TryOnProviderError
from app.ai.providers.fashn import FASHNTryOnProvider
from app.services.face_restore import Box
from app.services.tryon_direct import qc
from app.services.tryon_direct.inputs import DirectInputError, sniff_mime, to_data_uri
from tests.fashn_fakes import FakeFashn, image_bytes

OUTPUT = image_bytes((1200, 1800), (120, 140, 160), rect=(300, 500, 900, 1300))
PAYLOAD = TryOnInput(model_image_url="data:image/jpeg;base64,AAAA", garment_image_url="data:image/jpeg;base64,BBBB")


def _provider(**kwargs) -> FASHNTryOnProvider:
    return FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-max", **kwargs)


# --- request payload -----------------------------------------------------


async def test_tryon_max_payload_is_one_product_one_image_with_configured_options(monkeypatch):
    fake = FakeFashn(output=OUTPUT)
    fake.install(monkeypatch)

    out = await _provider(resolution="4k", generation_mode="balanced", output_format="jpeg").generate(PAYLOAD)

    assert fake.run_count == 1
    body = fake.run_bodies[0]
    assert body["model_name"] == "tryon-max"
    inputs = body["inputs"]
    assert inputs["model_image"] == PAYLOAD.model_image_url
    assert inputs["product_image"] == PAYLOAD.garment_image_url  # passed through untouched
    assert inputs["resolution"] == "4k"
    assert inputs["generation_mode"] == "balanced"
    assert inputs["output_format"] == "jpeg"
    assert inputs["num_images"] == 1
    assert "garment_image" not in inputs and "category" not in inputs
    assert "prompt" not in inputs and "seed" not in inputs  # not sent unless configured
    assert out.meta["resolution"] == "4k" and out.meta["generation_mode"] == "balanced"
    assert fake.unexpected == []


async def test_defaults_are_2k_quality_png(monkeypatch):
    fake = FakeFashn(output=OUTPUT)
    fake.install(monkeypatch)
    await _provider().generate(PAYLOAD)
    inputs = fake.run_bodies[0]["inputs"]
    assert (inputs["resolution"], inputs["generation_mode"], inputs["output_format"]) == ("2k", "quality", "png")


async def test_prompt_and_seed_are_sent_when_given(monkeypatch):
    fake = FakeFashn(output=OUTPUT)
    fake.install(monkeypatch)
    await _provider().generate(TryOnInput(model_image_url="m", garment_image_url="p", prompt="keep the shoes", seed=7))
    assert fake.run_bodies[0]["inputs"]["prompt"] == "keep the shoes"
    assert fake.run_bodies[0]["inputs"]["seed"] == 7


# --- raw output ----------------------------------------------------------


async def test_output_bytes_come_back_exactly_as_fashn_sent_them(monkeypatch):
    fake = FakeFashn(output=OUTPUT)
    fake.install(monkeypatch)
    out = await _provider().generate(PAYLOAD)
    assert out.image_bytes == OUTPUT
    assert out.content_type == "image/png"
    assert out.provider_job_id == "job_test_1"
    assert out.meta["output_sha256"] == hashlib.sha256(OUTPUT).hexdigest()
    for stamp in ("submitted_at", "fashn_completed_at", "downloaded_at"):
        assert out.meta[stamp]
    assert out.meta["provider_job_id"] == "job_test_1"


# --- polling: never a second paid job --------------------------------------


async def test_a_poll_timeout_never_submits_a_second_job(monkeypatch):
    fake = FakeFashn(output=OUTPUT, statuses=["processing"], job_id="job_slow")
    fake.install(monkeypatch)

    with pytest.raises(TryOnProviderError) as exc:
        await _provider(poll_timeout=0.2).generate(PAYLOAD)

    assert fake.run_count == 1
    assert exc.value.retryable is False  # the worker must not requeue it either
    assert exc.value.provider_job_id == "job_slow"
    assert "NOT resubmitted" in str(exc.value)
    assert len(fake.status_paths) >= 1 and all(p.endswith("/status/job_slow") for p in fake.status_paths)


async def test_transient_poll_trouble_keeps_polling_the_same_job(monkeypatch):
    fake = FakeFashn(
        output=OUTPUT,
        statuses=["connect-error", ("http", 503), ("http", 429), "processing", "completed"],
        job_id="job_flaky",
    )
    fake.install(monkeypatch)

    out = await _provider().generate(PAYLOAD)

    assert fake.run_count == 1
    assert len(fake.status_paths) == 5 and set(fake.status_paths) == {"/v1/status/job_flaky"}
    assert out.image_bytes == OUTPUT
    assert out.meta["poll_transient_errors"] == 3 and out.meta["poll_count"] == 5


async def test_a_hard_poll_error_stops_without_resubmitting(monkeypatch):
    fake = FakeFashn(output=OUTPUT, statuses=[("http", 404)], job_id="job_gone")
    fake.install(monkeypatch)
    with pytest.raises(TryOnProviderError) as exc:
        await _provider().generate(PAYLOAD)
    assert fake.run_count == 1 and exc.value.retryable is False and exc.value.provider_job_id == "job_gone"


@pytest.mark.parametrize("error, expected", [("face not detected", "face not detected"), ({"name": "PoseError", "message": "no person found"}, "no person found")])
async def test_a_failed_job_reports_fashns_reason_and_is_not_retried(monkeypatch, error, expected):
    fake = FakeFashn(output=OUTPUT, statuses=["failed"], failed_error=error)
    fake.install(monkeypatch)
    with pytest.raises(TryOnProviderError, match=expected) as exc:
        await _provider().generate(PAYLOAD)
    assert fake.run_count == 1 and exc.value.retryable is False


# --- submit: retry only what provably never reached billing ----------------


async def test_a_connection_that_never_opened_is_retried_then_succeeds(monkeypatch):
    fake = FakeFashn(output=OUTPUT, submit_script=["connect-error", 503, None])
    fake.install(monkeypatch)
    out = await _provider().generate(PAYLOAD)
    assert fake.run_count == 3 and out.image_bytes == OUTPUT


async def test_a_timeout_after_the_request_was_sent_is_not_retried(monkeypatch):
    """The job may already exist at FASHN; sending again could pay twice."""
    fake = FakeFashn(output=OUTPUT, submit_script=["read-timeout"])
    fake.install(monkeypatch)
    with pytest.raises(TryOnProviderError, match="not resubmitting") as exc:
        await _provider().generate(PAYLOAD)
    assert fake.run_count == 1 and exc.value.retryable is False


async def test_submit_gives_up_after_three_attempts(monkeypatch):
    fake = FakeFashn(output=OUTPUT, submit_script=[503, 503, 503, 503])
    fake.install(monkeypatch)
    with pytest.raises(TryOnProviderError) as exc:
        await _provider().generate(PAYLOAD)
    assert fake.run_count == 3 and exc.value.retryable is True


async def test_out_of_credits_is_not_retried(monkeypatch):
    fake = FakeFashn(output=OUTPUT, submit_script=["out-of-credits"])
    fake.install(monkeypatch)
    with pytest.raises(TryOnProviderError, match="out of credits") as exc:
        await _provider().generate(PAYLOAD)
    assert fake.run_count == 1 and exc.value.retryable is False


# --- download --------------------------------------------------------------


async def test_a_failed_download_retries_the_fetch_but_never_the_job(monkeypatch):
    fake = FakeFashn(output=OUTPUT, output_statuses=[500, 500, 200])
    fake.install(monkeypatch)
    out = await _provider().generate(PAYLOAD)
    assert fake.run_count == 1 and fake.output_fetches == 3 and out.image_bytes == OUTPUT


async def test_a_download_that_never_works_is_a_non_retryable_error_carrying_the_job_id(monkeypatch):
    fake = FakeFashn(output=OUTPUT, output_statuses=[500], job_id="job_paid")
    fake.install(monkeypatch)
    with pytest.raises(TryOnProviderError) as exc:
        await _provider().generate(PAYLOAD)
    assert fake.run_count == 1 and fake.output_fetches == 3
    assert exc.value.retryable is False and exc.value.provider_job_id == "job_paid"


# --- direct-engine input handling -------------------------------------------


def test_inputs_are_sent_as_their_original_bytes():
    jpeg = image_bytes((40, 60), (10, 20, 30), fmt="JPEG")
    uri = to_data_uri(jpeg)
    assert uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == jpeg


def test_a_non_image_is_refused_before_anything_is_sent():
    with pytest.raises(DirectInputError):
        to_data_uri(b"<html>not an image</html>")
    assert sniff_mime(image_bytes((8, 8), (0, 0, 0), fmt="PNG")) == "image/png"


# --- QC: report-only ---------------------------------------------------------

PERSON = image_bytes((600, 900), (90, 120, 150), fmt="JPEG")
RED_PRODUCT = image_bytes((300, 300), (255, 255, 255), rect=(40, 40, 260, 260), rect_color=(200, 30, 40), fmt="JPEG")
GREEN_PRODUCT = image_bytes((300, 300), (255, 255, 255), rect=(40, 40, 260, 260), rect_color=(30, 180, 60), fmt="JPEG")
EDITED = image_bytes((1200, 1800), (90, 120, 150), rect=(300, 700, 900, 1500), rect_color=(200, 30, 40))  # 2x the photo, red garment


def test_qc_reports_resolution_and_where_the_edit_is():
    report = qc.measure(PERSON, RED_PRODUCT, EDITED)
    res = report["resolution"]
    assert (res["output_width"], res["output_height"]) == (1200, 1800)
    assert res["scale_vs_input"] == 2.0 and res["aspect_difference"] == 0
    diff = report["difference"]
    assert 0.2 < diff["edited_fraction"] < 0.4  # the rectangle is ~29% of the frame
    x0, y0, x1, y1 = diff["changed_bbox"]
    assert abs(x0 - 0.25) < 0.03 and abs(y0 - 0.389) < 0.03 and abs(x1 - 0.75) < 0.03 and abs(y1 - 0.833) < 0.03
    assert diff["border_changed_fraction"] == 0
    assert report["report_only"] is True


def test_qc_product_match_is_high_for_the_right_colour_and_low_for_the_wrong_one():
    right = qc.measure(PERSON, RED_PRODUCT, EDITED)
    wrong = qc.measure(PERSON, GREEN_PRODUCT, EDITED)
    assert right["product"]["product_match_score"] > 0.8
    assert "low_product_colour_match" not in right["flags"]
    assert wrong["product"]["product_match_score"] < qc.THRESHOLDS["min_product_match"]
    assert "low_product_colour_match" in wrong["flags"]


def test_qc_flags_a_result_that_is_just_the_photo_back():
    same = image_bytes((1200, 1800), (90, 120, 150))
    report = qc.measure(PERSON, RED_PRODUCT, same)
    assert report["difference"]["edited_fraction"] == 0
    assert "no_visible_edit" in report["flags"]
    assert report["product"]["product_match_score"] is None


def test_qc_notes_a_changed_aspect_ratio_and_skips_the_pixel_comparison():
    square = image_bytes((1000, 1000), (90, 120, 150))
    report = qc.measure(PERSON, RED_PRODUCT, square)
    assert "aspect_ratio_changed" in report["flags"] and "skipped" in report["difference"]


def test_qc_flags_a_low_resolution_result():
    small = image_bytes((400, 600), (90, 120, 150))
    assert "low_resolution" in qc.measure(PERSON, RED_PRODUCT, small)["flags"]


def _textured(size, seed):
    rng = np.random.default_rng(seed)
    import io

    from PIL import Image

    img = Image.new("RGB", size, (90, 120, 150))
    face = Image.fromarray(rng.integers(40, 220, (180, 150, 3), dtype=np.uint8))
    img.paste(face, (int(size[0] * 0.35), int(size[1] * 0.08)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fake_face(monkeypatch):
    def detect(img):
        h, w = img.shape[:2]
        return Box(int(w * 0.35), int(h * 0.08), int(w * 0.25), int(h * 0.2))

    monkeypatch.setattr(qc, "detect_face", detect)


def test_qc_face_similarity_is_high_when_the_face_is_untouched(monkeypatch):
    _fake_face(monkeypatch)
    person = _textured((600, 900), seed=1)
    face = qc.measure(person, RED_PRODUCT, person)["face"]
    assert face["face_found_in_photo"] and face["face_similarity"] > 0.95
    assert face["face_changed_fraction"] == 0


def test_qc_flags_a_changed_face(monkeypatch):
    _fake_face(monkeypatch)
    report = qc.measure(_textured((600, 900), seed=1), RED_PRODUCT, _textured((600, 900), seed=2))
    assert report["face"]["face_similarity"] < qc.THRESHOLDS["min_face_similarity"]
    assert "face_changed" in report["flags"]


def test_qc_says_so_when_there_is_no_face_to_compare():
    face = qc.measure(PERSON, RED_PRODUCT, EDITED)["face"]
    assert face["face_found_in_photo"] is False and face["face_similarity"] is None


async def test_qc_never_raises_and_never_touches_the_image():
    result = bytearray(EDITED)
    before = hashlib.sha256(result).hexdigest()
    report = await qc.run_qc(PERSON, RED_PRODUCT, bytes(result))
    assert hashlib.sha256(result).hexdigest() == before
    assert report["vlm"] == {"enabled": False}

    broken = await qc.run_qc(PERSON, RED_PRODUCT, b"not an image")
    assert "qc_unreadable_image" in broken["flags"]


async def test_the_paid_vlm_score_runs_only_when_asked(monkeypatch):
    import app.services.tryon_quality.judge as judge_module

    async def must_not_run(*_a, **_kw):
        raise AssertionError("the OpenAI vision inspector ran without being enabled")

    monkeypatch.setattr(judge_module, "judge", must_not_run)
    assert (await qc.run_qc(PERSON, RED_PRODUCT, EDITED, with_vlm=False))["vlm"] == {"enabled": False}

    async def fake_vlm(*_a, **_kw):
        return {"enabled": True, "product_match": 8.0, "scale": "0-10"}

    monkeypatch.setattr(qc, "_vlm_report", fake_vlm)
    assert (await qc.run_qc(PERSON, RED_PRODUCT, EDITED, with_vlm=True))["vlm"]["product_match"] == 8.0

    async def vlm_down(*_a, **_kw):
        raise RuntimeError("vision unavailable")

    monkeypatch.setattr(qc, "_vlm_report", vlm_down)
    report = await qc.run_qc(PERSON, RED_PRODUCT, EDITED, with_vlm=True)
    assert "error" in report["vlm"] and report["flags"] is not None  # an optional score never fails QC
