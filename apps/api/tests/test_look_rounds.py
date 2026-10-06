"""Adding more products to a finished look, in rounds. Offline: FASHN is a fake."""

from __future__ import annotations

import base64

from app.models.enums import JobStatus, OutfitSlot
from app.models.tryon import TryOnJob, TryOnResult
from app.services.storage_service import get_storage
from app.workers.tasks import tryon_tasks
from tests.conftest import seed_product
from tests.fashn_fakes import image_bytes
from tests.test_direct_fashn_job import direct  # noqa: F401 — fixture
from tests.test_one_call_look import RecordingFashn, _job, _reload, _use_board

_OK = {"present": True, "color_correct": True, "details_preserved": True, "placement_correct": True}


def _vision(monkeypatch, direct, seen: list):  # noqa: ANN001
    monkeypatch.setattr(direct, "TRYON_DIRECT_VLM_QC", True)
    monkeypatch.setattr(direct, "OPENAI_API_KEY", "sk-test-not-real")

    async def vlm(original, final, images, names):  # noqa: ANN001
        seen.append({"original": original, "names": list(names)})
        return {"enabled": True, "same_person": True, "products": [{"index": i, **_OK} for i in range(len(names))]}

    monkeypatch.setattr(tryon_tasks, "vlm_final_check", vlm)


async def test_a_second_round_adds_to_the_finished_image_and_replaces_the_same_kind(client, db, direct, monkeypatch):  # noqa: F811
    _use_board(monkeypatch, direct)
    seen: list = []
    _vision(monkeypatch, direct, seen)
    first, layers = await _job(client, db, monkeypatch, n=4)
    layers[0].slot, layers[0].name = OutfitSlot.DRESS, "Pink Bridal Lehenga"
    layers[1].name = "Gold Jhumka Earrings"
    layers[2].name = "Kundan Stud Earrings"
    layers[3].slot, layers[3].name = OutfitSlot.WATCH, "Gold Bracelet Watch"

    await tryon_tasks._run_direct_job(db, first, RecordingFashn(available=4), layers[:2])
    first = await _reload(db, first.id)
    assert first.status == JobStatus.COMPLETED

    second = TryOnJob(
        user_id=first.user_id,
        user_photo_id=first.user_photo_id,
        provider="fashn",
        provider_model="tryon-max",
        status=JobStatus.QUEUED,
        credit_cost=8,
        base_job_id=first.id,
        look_round=2,
    )
    db.add(second)
    await db.commit()
    second = await tryon_tasks_job(db, second.id)
    fashn = RecordingFashn(available=4)
    original = get_storage().read(second.user_photo.storage_key)

    await tryon_tasks._run_direct_job(db, second, fashn, layers[2:])

    assert len(fashn.calls) == 1  # one FASHN call for the round
    payload = fashn.payloads[0]
    drawn_on = base64.b64decode(payload.model_image_url.split(",", 1)[1])
    assert drawn_on == get_storage().read(first.result.storage_key)  # the finished look, not the original photo
    assert "already dressed" in payload.prompt and "replaces" in payload.prompt
    done = await _reload(db, second.id)
    assert done.status == JobStatus.COMPLETED
    # the lehenga stays, the new earrings replace the jhumkas, the watch is added
    assert [p["name"] for p in done.result.placements] == ["Pink Bridal Lehenga", "Kundan Stud Earrings", "Gold Bracelet Watch"]
    assert done.result.qc_report["final_check"]["replaced"] == ["Gold Jhumka Earrings"]
    assert [s["round"] for s in done.steps] == [1, 2, 2]
    # every product in the look is checked again, against the ORIGINAL photo
    assert seen[-1]["names"] == ["Pink Bridal Lehenga", "Kundan Stud Earrings", "Gold Bracelet Watch"]
    assert seen[-1]["original"] == original


async def tryon_tasks_job(db, job_id):  # noqa: ANN001
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    return (
        await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(selectinload(TryOnJob.user_photo)))
    ).scalar_one()


async def _finished_look(db, job: TryOnJob, *, look_round: int = 1, status: JobStatus = JobStatus.COMPLETED) -> TryOnJob:  # noqa: ANN001
    job.status, job.look_round = status, look_round
    key = f"tryon/results/{job.user_id}/{job.id}.png"
    get_storage().put(key, image_bytes((600, 800), (200, 200, 200)), "image/png")
    db.add(TryOnResult(job_id=job.id, storage_key=key, image_url="https://example.test/r.png", placements=[]))
    await db.commit()
    return job


async def _add_round(client, base_id: str, product_id: str):  # noqa: ANN001
    photos = (await client.get("/api/v1/photos")).json()
    photo_id = (photos["items"] if isinstance(photos, dict) else photos)[0]["id"]
    return await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product_id, "base_job_id": base_id}
    )


async def test_a_round_is_added_only_to_a_finished_look_under_the_round_limit(client, db, direct, monkeypatch):  # noqa: F811
    monkeypatch.setattr(direct, "TRYON_MULTI_ENGINE", "fashn_board")
    monkeypatch.setattr(tryon_tasks_enqueue(), "enqueue_tryon_job", lambda _id: None)
    job, _ = await _job(client, db, monkeypatch, n=1)
    product = await seed_product(db, name="Gold Bracelet Watch", image_url="https://shop.example/w.jpg")

    running = await _add_round(client, job.id, product.id)
    assert running.status_code == 400 and "finished look" in running.json()["detail"]

    await _finished_look(db, job, look_round=3)
    full = await _add_round(client, job.id, product.id)
    assert full.status_code == 400 and "3 rounds" in full.json()["detail"]

    job.look_round = 1
    await db.commit()
    ok = await _add_round(client, job.id, product.id)
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["base_job_id"] == job.id and body["look_round"] == 2 and body["max_look_rounds"] == 3
    assert body["user_photo"]["id"] == job.user_photo_id  # same customer photo as the look


async def test_nobody_can_add_to_someone_elses_look(client, db, direct, monkeypatch):  # noqa: F811
    monkeypatch.setattr(direct, "TRYON_MULTI_ENGINE", "fashn_board")
    monkeypatch.setattr(tryon_tasks_enqueue(), "enqueue_tryon_job", lambda _id: None)
    job, _ = await _job(client, db, monkeypatch, n=1)
    await _finished_look(db, job)
    product = await seed_product(db, name="Gold Bracelet Watch", image_url="https://shop.example/w.jpg")

    from tests.conftest import register_and_login

    await register_and_login(client)  # a different shopper
    from tests.test_tryon import _upload_front_photo

    await _upload_front_photo(client)
    resp = await _add_round(client, job.id, product.id)
    assert resp.status_code == 404


def tryon_tasks_enqueue():
    from app.api.v1.endpoints import tryon as endpoint

    return endpoint
