"""The credit purchase flow: instant-success (mock provider, used in dev),
and — the important regression — the real-Stripe "requires_action" path,
where the backend must hand back client_secret rather than silently
discarding it (a real bug found while wiring the frontend: the endpoint
previously 402'd with only a text detail, so the client_secret Stripe.js
needs to confirm the payment never reached the frontend)."""

from __future__ import annotations

from app.payments.base import CheckoutResult
from app.payments.mock import MockPaymentProvider
from app.models.enums import PaymentStatus
from app.models.subscription import Payment
from tests.conftest import register_and_login, seed_credit_package


async def test_list_packages(client, db):
    await seed_credit_package(db, name="Starter", credits=50, price_cents=499)
    resp = await client.get("/api/v1/credits/packages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Starter" in names


async def test_purchase_unknown_package_is_404(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": "does-not-exist"})
    assert resp.status_code == 404


async def test_purchase_with_mock_provider_succeeds_instantly_and_grants_credits(client, db):
    package = await seed_credit_package(db, name="Instant Pack", credits=50, price_cents=499)
    data = await register_and_login(client)

    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["credits_granted"] == 50
    assert body["new_balance"] == data["user"]["credits_balance"] + 50
    assert body["client_secret"] is None

    balance = await client.get("/api/v1/credits/balance")
    assert balance.json()["balance"] == data["user"]["credits_balance"] + 50


async def test_purchase_requires_action_returns_client_secret_without_granting_credits(client, db, monkeypatch):
    """Regression test: a real Stripe PaymentIntent always comes back
    requires_action for automatic_payment_methods — the endpoint must
    return client_secret (not discard it), and must NOT grant credits
    until the webhook confirms it."""

    async def fake_create_checkout(self, **kwargs):  # noqa: ARG001
        return CheckoutResult(
            external_payment_id="pi_fake_123",
            status="requires_action",
            client_secret="pi_fake_123_secret_abc",
        )

    monkeypatch.setattr(MockPaymentProvider, "create_checkout", fake_create_checkout)

    package = await seed_credit_package(db, name="3DS Pack", credits=100, price_cents=999)
    data = await register_and_login(client)
    starting_balance = data["user"]["credits_balance"]

    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "requires_action"
    assert body["client_secret"] == "pi_fake_123_secret_abc"
    assert body["credits_granted"] is None

    # credits are NOT granted yet — only the webhook can do that
    balance = await client.get("/api/v1/credits/balance")
    assert balance.json()["balance"] == starting_balance

    # polling the payment reflects "pending" until the webhook fires
    status_resp = await client.get(f"/api/v1/credits/purchase/{body['payment_id']}")
    assert status_resp.json()["status"] == "pending"


async def test_purchase_status_is_scoped_to_the_owning_user(client, db):
    package = await seed_credit_package(db)
    await register_and_login(client)
    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    payment_id = resp.json()["payment_id"]

    await register_and_login(client)  # a different user
    resp = await client.get(f"/api/v1/credits/purchase/{payment_id}")
    assert resp.status_code == 404


async def test_purchase_status_reflects_webhook_confirmed_success(client, db, monkeypatch):
    async def fake_create_checkout(self, **kwargs):  # noqa: ARG001
        return CheckoutResult(external_payment_id="pi_fake_456", status="requires_action", client_secret="secret")

    monkeypatch.setattr(MockPaymentProvider, "create_checkout", fake_create_checkout)

    package = await seed_credit_package(db, credits=30)
    await register_and_login(client)
    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    payment_id = resp.json()["payment_id"]

    # simulate what the webhook does once Stripe confirms the charge
    payment = await db.get(Payment, payment_id)
    payment.status = PaymentStatus.SUCCEEDED
    await db.commit()

    resp = await client.get(f"/api/v1/credits/purchase/{payment_id}")
    assert resp.json()["status"] == "succeeded"
