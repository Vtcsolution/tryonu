"""The completion gate and the review path for paid FASHN renders.

Every FASHN call goes to tests/fashn_fakes.FakeFashn. No credit can be spent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.enums import CreditReason, JobStatus
from app.models.tryon import TryOnJob
from app.services import credit_service
from app.services.storage_service import get_storage
from app.services.tryon_direct.qc import qc_gate
from tests.conftest import credit_balance, make_admin, register_and_login, seed_product
from tests.fashn_fakes import FakeFashn, image_bytes
from tests.test_direct_fashn_job import OUTPUT, PRODUCT, PRODUCT_URL, _row, _setup, direct  # noqa: F401 — fixture
from tests.test_tryon import _poll_until_terminal, _upload_front_photo, _was_refunded

UNCHANGED = image_bytes((400, 500), (180, 160, 140))


# --- the gate itself --------------------------------------------------------


def test_a_clean_report_passes_the_gate():
    assert qc_gate({"flags": []}) == {"passed": True, "failed_checks": [], "advisory": []}


def test_a_margin_change_alone_is_advisory_and_does_not_block():
    gate = qc_gate({"flags": ["frame_margins_changed"]})
    assert gate["passed"] is True
    assert gate["advisory"] == ["frame_margins_changed"]


def test_every_failed_check_is_named():
    gate = qc_gate({"flags": ["no_visible_edit", "face_changed", "frame_margins_changed"]})
    assert gate["passed"] is False
    assert gate["failed_checks"] == ["no_visible_edit", "face_changed"]
    assert gate["advisory"] == ["frame_margins_changed"]


def test_an_unreadable_report_fails_the_gate():
    gate = qc_gate({"error": "could not read an image", "flags": ["qc_unreadable_image"]})
    assert gate["passed"] is False
    assert gate["failed_checks"] == ["qc_unreadable_image"]


def test_a_qc_crash_with_no_flags_still_fails_the_gate():
    gate = qc_gate({"error": "boom"})
    assert gate["passed"] is False
    assert gate["failed_checks"] == ["qc_failed"]


# --- helpers ----------------------------------------------------------------


async def _admin_client(client, db) -> str:
    await register_and_login(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    await make_admin(db, user_id)
    return user_id


async def _held_job(client, db, monkeypatch, direct_fixture) -> str:  # noqa: ANN001
    fake = FakeFashn(output=UNCHANGED, product=PRODUCT)
    fake.install(monkeypatch)
    photo_id, product, _ = await _setup(client, db)
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    await _poll_until_terminal(client, resp.json()["id"])
    return resp.json()["id"]


async def _stalled_paid_job(client, db, provider_job_id: str) -> tuple[str, str]:
    """A paid job FASHN accepted whose worker never came back. Returns (job id, user id)."""
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    await db.rollback()
    product = await seed_product(db, name="Red Test Top", image_url=PRODUCT_URL)
    when = datetime.now(timezone.utc) - timedelta(minutes=45)
    job = TryOnJob(
        user_id=user_id,
        user_photo_id=photo_id,
        product_id=product.id,
        provider="fashn",
        provider_model="tryon-max",
        provider_job_id=provider_job_id,
        status=JobStatus.PROCESSING,
        credit_cost=5,
        queued_at=when,
        started_at=when,
    )
    db.add(job)
    await db.flush()
    await credit_service.debit(
        db, user_id=user_id, amount=5, reason=CreditReason.TRYON_DEBIT, reference_type="tryon_job", reference_id=job.id
    )
    await db.commit()
    job_id = job.id
    await db.refresh(job)
    await db.commit()
    from app.services.stuck_jobs import sweep_stuck_jobs

    assert await sweep_stuck_jobs() == 1  # the sweeper holds it for review, as it does in production
    db.expire_all()
    return job_id, user_id


# --- reviewer actions -------------------------------------------------------


async def test_the_review_queue_is_admin_only(client, db, direct, monkeypatch):  # noqa: F811
    await register_and_login(client)
    assert (await client.get("/api/v1/admin/tryon-reviews")).status_code == 403


async def test_a_held_render_lists_for_review_with_its_failed_checks(client, db, direct, monkeypatch):  # noqa: F811
    job_id = await _held_job(client, db, monkeypatch, direct)
    await _admin_client(client, db)
    rows = (await client.get("/api/v1/admin/tryon-reviews")).json()
    row = next(r for r in rows if r["id"] == job_id)
    assert row["review_state"] == "pending"
    assert "no_visible_edit" in row["review_reason"]


async def test_a_multi_product_hold_cannot_be_delivered_as_a_finished_look(client, db, direct, monkeypatch):  # noqa: F811
    """Nothing verified was stored as a deliverable render, so approving it is refused."""
    job_id = await _held_job(client, db, monkeypatch, direct)
    await _admin_client(client, db)

    refused = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/approve")
    assert refused.status_code == 409
    job, result = await _row(job_id)
    assert result is None and job.review_state == "pending"


async def test_refunding_returns_the_credits_once_and_never_twice(client, db, direct, monkeypatch):  # noqa: F811
    job_id = await _held_job(client, db, monkeypatch, direct)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    before = await credit_balance(db, user_id)
    await _admin_client(client, db)

    resp = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/refund", json={"note": "render not as ordered"})
    assert resp.status_code == 200 and resp.json()["review_state"] == "refunded"
    db.expire_all()
    assert await credit_balance(db, user_id) == before + 5

    second = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/refund", json={"note": "again"})
    assert second.status_code == 409
    db.expire_all()
    assert await credit_balance(db, user_id) == before + 5


async def test_a_refund_needs_a_reason(client, db, direct, monkeypatch):  # noqa: F811
    job_id = await _held_job(client, db, monkeypatch, direct)
    await _admin_client(client, db)
    resp = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/refund", json={})
    assert resp.status_code == 422


# --- reconciling a stalled paid job against FASHN --------------------------


async def test_reconcile_delivers_a_stalled_render_FASHN_completed(client, db, monkeypatch):
    job_id, _ = await _stalled_paid_job(client, db, provider_job_id="job_test_1")
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, statuses=["completed"])
    fake.install(monkeypatch)
    await _admin_client(client, db)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_tryon_provider", _fashn_provider)

    resp = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/reconcile")
    assert resp.status_code == 200, resp.text
    assert resp.json()["outcome"] == "delivered"
    assert fake.run_count == 0  # reconciliation never creates a job
    job, result = await _row(job_id)
    assert job.status == JobStatus.COMPLETED and result is not None
    assert job.review_state == "resolved"


async def test_reconcile_holds_a_completed_render_that_fails_verification(client, db, monkeypatch):
    job_id, _ = await _stalled_paid_job(client, db, provider_job_id="job_test_5")
    fake = FakeFashn(output=UNCHANGED, product=PRODUCT, statuses=["completed"])
    fake.install(monkeypatch)
    await _admin_client(client, db)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_tryon_provider", _fashn_provider)

    resp = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/reconcile")
    assert resp.json()["outcome"] == "held"
    job, result = await _row(job_id)
    assert result is None  # never shown to the customer as a result
    assert job.review_state == "pending"
    assert "no_visible_edit" in job.review_reason


async def test_reconcile_refunds_once_when_FASHN_says_the_job_failed(client, db, monkeypatch):
    job_id, user_id = await _stalled_paid_job(client, db, provider_job_id="job_test_2")
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, statuses=["failed"], failed_error="content policy")
    fake.install(monkeypatch)
    await _admin_client(client, db)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_tryon_provider", _fashn_provider)
    before = await credit_balance(db, user_id)

    resp = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/reconcile")
    assert resp.json()["outcome"] == "refunded"
    db.expire_all()
    assert await credit_balance(db, user_id) == before + 5

    again = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/reconcile")
    assert again.status_code == 409
    db.expire_all()
    assert await credit_balance(db, user_id) == before + 5


async def test_reconcile_leaves_a_still_running_job_alone(client, db, monkeypatch):
    job_id, user_id = await _stalled_paid_job(client, db, provider_job_id="job_test_3")
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, statuses=["processing"])
    fake.install(monkeypatch)
    await _admin_client(client, db)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_tryon_provider", _fashn_provider)
    before = await credit_balance(db, user_id)

    resp = await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/reconcile")
    assert resp.json()["outcome"] == "still_running"
    db.expire_all()
    assert await credit_balance(db, user_id) == before
    assert (await _row(job_id))[0].review_state == "pending"


async def test_reconcile_never_refunds_a_job_FASHN_is_still_rendering(client, db, monkeypatch):
    """The sweeper's own rule, checked from the reviewer side as well."""
    job_id, user_id = await _stalled_paid_job(client, db, provider_job_id="job_test_4")
    fake = FakeFashn(output=OUTPUT, product=PRODUCT, statuses=["processing"])
    fake.install(monkeypatch)
    await _admin_client(client, db)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_tryon_provider", _fashn_provider)
    await client.post(f"/api/v1/admin/tryon-reviews/{job_id}/reconcile")
    assert not await _was_refunded(job_id)


def _fashn_provider():
    from app.ai.providers.fashn import FASHNTryOnProvider

    return FASHNTryOnProvider(
        api_key="fa-test-not-real",
        base_url="https://api.fashn.ai/v1",
        model="tryon-max",
        poll_interval=0.0,
        poll_timeout=5,
    )
