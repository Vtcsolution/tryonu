"""A try-on that never starts must not hold a customer's credits.

Live: a job sat at "Queued — waiting for a worker" for four minutes and
would have sat there forever — nothing in the system moves a queued job
when no worker picks it up.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.enums import JobStatus
from app.models.tryon import TryOnJob
from app.services.stuck_jobs import sweep_stuck_jobs
from tests.conftest import credit_balance, register_and_login, seed_product


async def _queued_job(db, client, *, age_minutes: int, status=JobStatus.QUEUED, cost: int = 8) -> TryOnJob:
    from tests.test_tryon import _upload_front_photo

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    await db.rollback()
    product = await seed_product(db, name="Stuck Test Kurta")

    when = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    job = TryOnJob(
        user_id=user_id,
        user_photo_id=photo_id,
        product_id=product.id,
        provider="openai",
        provider_model="gpt-image-2",
        status=status,
        credit_cost=cost,
        queued_at=when,
        started_at=when if status == JobStatus.PROCESSING else None,
    )
    db.add(job)
    await db.flush()
    # the credits a real job reserves when it is created: without the debit
    # there is nothing to give back, and refund() rightly declines
    from app.models.enums import CreditReason
    from app.services import credit_service

    await credit_service.debit(
        db,
        user_id=user_id,
        amount=cost,
        reason=CreditReason.TRYON_DEBIT,
        reference_type="tryon_job",
        reference_id=job.id,
    )
    await db.commit()
    await db.refresh(job)
    await db.commit()
    return job


async def test_a_job_that_never_started_is_failed_and_refunded(client, db):
    job = await _queued_job(db, client, age_minutes=9)
    user_id, cost = job.user_id, job.credit_cost  # read before the session expires them
    before = await credit_balance(db, user_id)

    assert await sweep_stuck_jobs() == 1
    body = (await client.get(f"/api/v1/tryon/{job.id}")).json()
    assert body["status"] == "failed"
    assert "never started" in body["error_message"]

    db.expire_all()
    assert await credit_balance(db, user_id) == before + cost


async def test_a_job_still_within_its_time_is_left_alone(client, db):
    job = await _queued_job(db, client, age_minutes=1)
    assert await sweep_stuck_jobs() == 0
    body = (await client.get(f"/api/v1/tryon/{job.id}")).json()
    assert body["status"] == "queued"  # a busy worker is normal, not a fault


async def test_a_render_that_stalled_for_twenty_minutes_is_given_up_on(client, db):
    job = await _queued_job(db, client, age_minutes=25, status=JobStatus.PROCESSING)
    user_id, cost = job.user_id, job.credit_cost
    before = await credit_balance(db, user_id)

    assert await sweep_stuck_jobs() == 1
    body = (await client.get(f"/api/v1/tryon/{job.id}")).json()
    assert body["status"] == "failed"
    assert "took too long" in body["error_message"]

    db.expire_all()
    assert await credit_balance(db, user_id) == before + cost


async def test_a_long_but_living_render_is_not_interrupted(client, db):
    job = await _queued_job(db, client, age_minutes=4, status=JobStatus.PROCESSING)
    assert await sweep_stuck_jobs() == 0
    body = (await client.get(f"/api/v1/tryon/{job.id}")).json()
    assert body["status"] == "processing"  # multi-item looks really do take minutes


async def test_credits_are_refunded_once_however_often_it_is_polled(client, db):
    job = await _queued_job(db, client, age_minutes=9)
    user_id, cost, job_id = job.user_id, job.credit_cost, job.id
    before = await credit_balance(db, user_id)

    for _ in range(3):
        await sweep_stuck_jobs()  # a sweep every minute must not refund twice
        assert (await client.get(f"/api/v1/tryon/{job_id}")).json()["status"] == "failed"

    db.expire_all()
    assert await credit_balance(db, user_id) == before + cost
