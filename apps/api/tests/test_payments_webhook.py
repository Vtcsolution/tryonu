"""Stripe webhook signature verification — the real HMAC logic, exercised
directly (no network, no real Stripe account needed). This is what stops
someone from POSTing a fake "payment succeeded" event to grant themselves
credits."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi import HTTPException

from app.payments.stripe_provider import StripePaymentProvider

SECRET = "whsec_test_secret"


def _sign(payload: bytes, secret: str, timestamp: int) -> str:
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _payload(event_type: str, payment_intent_id: str = "pi_123") -> bytes:
    return json.dumps({"type": event_type, "data": {"object": {"id": payment_intent_id}}}).encode()


def test_valid_signature_is_accepted():
    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret=SECRET)
    payload = _payload("payment_intent.succeeded")
    header = _sign(payload, SECRET, int(time.time()))

    event = provider.verify_webhook(payload, header)
    assert event.status == "succeeded"
    assert event.external_payment_id == "pi_123"


def test_tampered_payload_is_rejected():
    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret=SECRET)
    payload = _payload("payment_intent.succeeded")
    header = _sign(payload, SECRET, int(time.time()))

    tampered = _payload("payment_intent.succeeded", payment_intent_id="pi_ATTACKER_CONTROLLED")
    with pytest.raises(HTTPException) as exc_info:
        provider.verify_webhook(tampered, header)
    assert exc_info.value.status_code == 400


def test_wrong_secret_is_rejected():
    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret=SECRET)
    payload = _payload("payment_intent.succeeded")
    header = _sign(payload, "whsec_totally_different", int(time.time()))

    with pytest.raises(HTTPException) as exc_info:
        provider.verify_webhook(payload, header)
    assert exc_info.value.status_code == 400


def test_stale_timestamp_is_rejected():
    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret=SECRET)
    payload = _payload("payment_intent.succeeded")
    old_timestamp = int(time.time()) - 3600  # 1 hour old
    header = _sign(payload, SECRET, old_timestamp)

    with pytest.raises(HTTPException) as exc_info:
        provider.verify_webhook(payload, header)
    assert exc_info.value.status_code == 400


def test_missing_signature_header_is_rejected():
    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret=SECRET)
    with pytest.raises(HTTPException):
        provider.verify_webhook(_payload("payment_intent.succeeded"), None)


def test_failed_payment_event_maps_to_failed_status():
    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret=SECRET)
    payload = _payload("payment_intent.payment_failed")
    header = _sign(payload, SECRET, int(time.time()))

    event = provider.verify_webhook(payload, header)
    assert event.status == "failed"
