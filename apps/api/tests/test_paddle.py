"""Paddle checkout (card, PayPal, Apple Pay, Google Pay) against a fake Paddle.
Offline: no real Paddle call."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest

from app.payments.paddle_provider import PaddlePaymentProvider, verify_signature
from tests.conftest import credit_balance, register_and_login, seed_credit_package

SECRET = "pdl_ntfset_test_secret_not_real"


class FakePaddle:
    """Answers the two Paddle calls the provider makes: create and read a transaction."""

    def __init__(self, *, paid_total: int | None = None, status: str = "completed") -> None:
        self.paid_total = paid_total
        self.status = status
        self.transactions: dict[str, dict] = {}
        self.seen_auth: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen_auth.append(request.headers.get("Authorization", ""))
        path = request.url.path
        if request.method == "POST" and path == "/transactions":
            body = json.loads(request.content)
            txn = f"txn_{uuid.uuid4().hex[:20]}"  # unique, like Paddle's
            self.transactions[txn] = body
            return httpx.Response(
                201, json={"data": {"id": txn, "status": "ready", "checkout": {"url": f"{body['checkout']['url']}&_ptxn={txn}"}}}
            )
        if request.method == "GET" and path.startswith("/transactions/"):
            txn = path.rsplit("/", 1)[-1]
            body = self.transactions.get(txn)
            if body is None:
                return httpx.Response(404, json={"error": {"code": "entity_not_found"}})
            price = body["items"][0]["price"]["unit_price"]
            total = self.paid_total if self.paid_total is not None else int(price["amount"])
            return httpx.Response(
                200,
                json={"data": {"id": txn, "status": self.status, "currency_code": price["currency_code"],
                               "details": {"totals": {"total": str(total), "grand_total": str(total)}}}},
            )
        return httpx.Response(404, json={"error": {"code": "not_found"}})


@pytest.fixture
def paddle(monkeypatch):  # noqa: ANN001, ANN201
    def use(fake: FakePaddle) -> PaddlePaymentProvider:
        provider = PaddlePaymentProvider(
            api_key="pdl_sdbx_apikey_not_real", mode="sandbox", pay_url="https://tryonu.test/pay",
            webhook_secret=SECRET, transport=httpx.MockTransport(fake),
        )
        monkeypatch.setattr("app.api.v1.endpoints.credits.get_payment_provider", lambda: provider)
        monkeypatch.setattr("app.services.payment_settlement.get_payment_provider", lambda: provider)
        monkeypatch.setattr("app.api.v1.endpoints.webhooks.get_payment_provider", lambda: provider)
        return provider

    return use


async def _buy(client, db):  # noqa: ANN001, ANN202
    await register_and_login(client)
    me = (await client.get("/api/v1/auth/me")).json()
    package = await seed_credit_package(db, name="Starter Pack", credits=50, price_cents=499)
    resp = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert resp.status_code == 200, resp.text
    return me, resp.json()


async def test_a_package_bought_through_paddle_adds_its_credits_once(client, db, paddle):  # noqa: ANN001
    fake = FakePaddle()
    paddle(fake)
    me, started = await _buy(client, db)
    before = await credit_balance(db, me["id"])

    # sent to our /pay page, which opens Paddle's checkout; nothing granted yet
    assert started["status"] == "requires_action"
    assert started["checkout_url"].startswith(f"https://tryonu.test/pay?payment_id={started['payment_id']}")
    body = next(iter(fake.transactions.values()))
    price = body["items"][0]["price"]
    assert price["unit_price"] == {"amount": "499", "currency_code": "USD"} and price["tax_mode"] == "internal"
    assert body["custom_data"]["payment_id"] == started["payment_id"]
    assert fake.seen_auth[0] == "Bearer pdl_sdbx_apikey_not_real"
    assert await credit_balance(db, me["id"]) == before

    done = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert done.json()["status"] == "succeeded" and done.json()["credits_granted"] == 50
    again = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")  # reload / double click
    assert again.json()["status"] == "succeeded"
    assert await credit_balance(db, me["id"]) == before + 50


async def test_an_unpaid_checkout_stays_pending_and_a_wrong_amount_grants_nothing(client, db, paddle):  # noqa: ANN001
    fake = FakePaddle(status="ready")  # the customer hasn't paid yet
    paddle(fake)
    me, started = await _buy(client, db)
    before = await credit_balance(db, me["id"])
    waiting = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert waiting.json()["status"] == "pending"

    fake.status, fake.paid_total = "completed", 100  # paid, but not this price
    wrong = await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert wrong.json()["status"] == "failed"
    assert await credit_balance(db, me["id"]) == before


async def test_paddles_signed_webhook_finishes_a_payment_the_customer_left(client, db, paddle):  # noqa: ANN001
    fake = FakePaddle()
    paddle(fake)
    me, started = await _buy(client, db)
    before = await credit_balance(db, me["id"])
    txn = next(iter(fake.transactions))
    event = json.dumps({"event_type": "transaction.completed", "data": {"id": txn}}).encode()

    unsigned = await client.post("/api/v1/webhooks/paddle", content=event)
    assert unsigned.json()["detail"] == "ignored" and await credit_balance(db, me["id"]) == before

    ts = str(int(time.time()))
    h1 = hmac.new(SECRET.encode(), f"{ts}:".encode() + event, hashlib.sha256).hexdigest()
    signed = await client.post("/api/v1/webhooks/paddle", content=event, headers={"Paddle-Signature": f"ts={ts};h1={h1}"})
    assert signed.json()["detail"] == "ok"
    assert await credit_balance(db, me["id"]) == before + 50


def test_signatures_must_match_and_be_fresh():
    body = b'{"event_type":"transaction.completed"}'
    ts = 1_800_000_000
    h1 = hmac.new(SECRET.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    assert verify_signature(body, f"ts={ts};h1={h1}", SECRET, now=ts + 10)
    assert not verify_signature(body, f"ts={ts};h1={h1}", SECRET, now=ts + 3600)  # replayed later
    assert not verify_signature(body + b" ", f"ts={ts};h1={h1}", SECRET, now=ts)  # changed body
    assert not verify_signature(body, f"ts={ts};h1={h1}", "other-secret", now=ts)
    assert not verify_signature(body, None, SECRET)


async def test_the_website_learns_which_checkout_to_open(client, monkeypatch):  # noqa: ANN001
    from app.core.config import get_settings

    provider = PaddlePaymentProvider(api_key="x", mode="sandbox", pay_url="https://tryonu.test/pay")
    monkeypatch.setattr("app.api.v1.endpoints.credits.get_payment_provider", lambda: provider)
    monkeypatch.setattr(get_settings(), "PADDLE_MODE", "sandbox")
    monkeypatch.setattr(get_settings(), "PADDLE_SANDBOX_CLIENT_TOKEN", "test_not_real")
    cfg = (await client.get("/api/v1/credits/checkout-config")).json()
    assert cfg == {"provider": "paddle", "paddle": {"token": "test_not_real", "environment": "sandbox"}}


async def test_an_admin_sees_why_paddle_refused_and_a_customer_sees_the_plain_message(client, db, paddle):  # noqa: ANN001
    from tests.conftest import make_admin

    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "transaction_default_checkout_url_not_set"}})

    paddle(refuse)  # type: ignore[arg-type]
    await register_and_login(client)
    package = await seed_credit_package(db, name="Starter Pack", credits=50, price_cents=499)
    customer = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert customer.status_code == 502 and "Admin" not in customer.json()["detail"]

    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    seen = await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})
    assert "Default payment link" in seen.json()["detail"] and "pdl_" not in seen.json()["detail"]
