"""PayPal credit-package checkout, against a fake PayPal. Offline: no real PayPal call."""

from __future__ import annotations

import json

import httpx
import pytest

from app.payments.paypal_provider import PayPalPaymentProvider
from app.payments.registry import UnavailablePaymentProvider
from tests.conftest import credit_balance, register_and_login, seed_credit_package


class FakePayPal:
    """Answers the three PayPal calls the provider makes."""

    def __init__(self, *, captured_value: str | None = None, capture_status: str = "COMPLETED", approved: bool = True) -> None:
        self.captured_value = captured_value
        self.capture_status = capture_status
        self.approved = approved
        self.orders: dict[str, dict] = {}
        self.captures = 0
        self.seen_auth: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 3600})
        self.seen_auth.append(request.headers.get("Authorization", ""))
        if path == "/v2/checkout/orders":
            unit = json.loads(request.content)["purchase_units"][0]
            order_id = f"ORDER-{len(self.orders) + 1}"
            self.orders[order_id] = unit
            return httpx.Response(
                201,
                json={"id": order_id, "status": "PAYER_ACTION_REQUIRED",
                      "links": [{"rel": "payer-action", "href": f"https://paypal.test/checkoutnow?token={order_id}"}]},
            )
        if path.endswith("/capture"):
            if not self.approved:
                return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_NOT_APPROVED"}]})
            self.captures += 1
            order_id = path.split("/")[-2]
            amount = dict(self.orders[order_id]["amount"])
            if self.captured_value:
                amount["value"] = self.captured_value
            return httpx.Response(
                201,
                json={"id": order_id, "status": "COMPLETED",
                      "purchase_units": [{"payments": {"captures": [{"id": "CAP-1", "status": self.capture_status, "amount": amount}]}}]},
            )
        return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND"})


@pytest.fixture
def paypal(monkeypatch):  # noqa: ANN001, ANN201
    def use(fake: FakePayPal) -> PayPalPaymentProvider:
        provider = PayPalPaymentProvider(
            client_id="sandbox-id-not-real",
            client_secret="sandbox-secret-not-real",
            mode="sandbox",
            return_url="https://tryonu.test/credits/paypal",
            cancel_url="https://tryonu.test/credits/paypal",
            transport=httpx.MockTransport(fake),
        )
        monkeypatch.setattr("app.api.v1.endpoints.credits.get_payment_provider", lambda: provider)
        return provider

    return use


async def _me(client):  # noqa: ANN001, ANN202
    await register_and_login(client)
    return (await client.get("/api/v1/auth/me")).json()


async def _buy(client, db):  # noqa: ANN001, ANN202
    me = await _me(client)
    package = await seed_credit_package(db, name="Starter Pack", credits=50, price_cents=499)
    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert resp.status_code == 200, resp.text
    return me, resp.json()


async def test_a_package_bought_with_paypal_adds_its_credits_once(client, db, paypal):  # noqa: ANN001
    fake = FakePayPal()
    paypal(fake)
    me, started = await _buy(client, db)
    before = await credit_balance(db, me["id"])

    # sent to PayPal, nothing granted yet
    assert started["status"] == "requires_action" and started["checkout_url"].startswith("https://paypal.test/")
    unit = next(iter(fake.orders.values()))
    assert unit["amount"] == {"currency_code": "USD", "value": "4.99"} and unit["custom_id"] == started["payment_id"]
    assert await credit_balance(db, me["id"]) == before

    done = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert done.json()["status"] == "succeeded" and done.json()["credits_granted"] == 50
    assert await credit_balance(db, me["id"]) == before + 50

    again = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")  # reload / double click
    assert again.json()["status"] == "succeeded" and fake.captures == 1
    assert await credit_balance(db, me["id"]) == before + 50


async def test_a_capture_for_a_different_amount_grants_nothing(client, db, paypal):  # noqa: ANN001
    paypal(FakePayPal(captured_value="0.01"))
    me, started = await _buy(client, db)
    before = await credit_balance(db, me["id"])

    done = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert done.json()["status"] == "failed"
    assert await credit_balance(db, me["id"]) == before


async def test_a_shopper_who_never_approved_stays_pending(client, db, paypal):  # noqa: ANN001
    paypal(FakePayPal(approved=False))
    me, started = await _buy(client, db)
    before = await credit_balance(db, me["id"])

    done = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert done.json()["status"] == "pending"
    assert await credit_balance(db, me["id"]) == before


async def test_nobody_can_capture_someone_elses_payment(client, db, paypal):  # noqa: ANN001
    paypal(FakePayPal())
    _, started = await _buy(client, db)
    await register_and_login(client)  # a different shopper
    resp = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert resp.status_code == 404


async def test_production_without_a_real_payment_provider_sells_nothing(client, db, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr("app.api.v1.endpoints.credits.get_payment_provider", lambda: UnavailablePaymentProvider())
    me = await _me(client)
    package = await seed_credit_package(db)
    before = await credit_balance(db, me["id"])

    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert resp.status_code == 503 and "Nothing was charged" in resp.json()["detail"]
    assert await credit_balance(db, me["id"]) == before


async def test_missing_paypal_keys_refuse_instead_of_failing_open(client, db, monkeypatch):  # noqa: ANN001
    provider = PayPalPaymentProvider(
        client_id=None, client_secret=None, mode="live", return_url="https://x/r", cancel_url="https://x/c"
    )
    monkeypatch.setattr("app.api.v1.endpoints.credits.get_payment_provider", lambda: provider)
    me = await _me(client)
    package = await seed_credit_package(db)
    before = await credit_balance(db, me["id"])

    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert resp.status_code == 503
    assert await credit_balance(db, me["id"]) == before
