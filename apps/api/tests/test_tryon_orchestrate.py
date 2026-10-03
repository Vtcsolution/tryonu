"""Sequential multi-product FASHN orchestration, tested with fakes only.

No real FASHN call is possible from here: `render` is a local function that
returns bytes, and nothing in this file imports the HTTP provider.
"""

from __future__ import annotations

import pytest

from app.ai.providers.base import TryOnOutput
from app.services.tryon_direct import orchestrate
from app.services.tryon_direct.orchestrate import (
    OrchestrationRefused,
    ProductInput,
    StepVerdict,
    check_plan,
    credits_per_render,
    run_sequence,
    verify_step,
)
from tests.fashn_fakes import image_bytes

PERSON = image_bytes((300, 400), (150, 150, 150))


def _product(i: int, *, pid: str | None = None) -> ProductInput:
    return ProductInput(
        name=f"Product {i}",
        product_id=pid or f"p{i}",
        image_url=f"https://shop.example/{i}.jpg",
        image=image_bytes((200, 200), (10 * i, 20, 30 + i)),
    )


# --- the plan is checked before any call -----------------------------------


def test_credit_cost_follows_fashns_table():
    assert credits_per_render("1k", "balanced") == 2
    assert credits_per_render("2k", "quality") == 4
    assert credits_per_render("4k", "fast") == 3


def test_an_empty_look_is_refused():
    with pytest.raises(OrchestrationRefused, match="no products"):
        check_plan([], max_products=10, cost_per_render=2, max_credits=20)


def test_more_products_than_the_limit_is_refused():
    products = [_product(i) for i in range(4)]
    with pytest.raises(OrchestrationRefused, match="at most 3"):
        check_plan(products, max_products=3, cost_per_render=2, max_credits=100)


def test_the_same_product_twice_is_refused():
    with pytest.raises(OrchestrationRefused, match="more than once"):
        check_plan([_product(1, pid="same"), _product(2, pid="same")], max_products=10, cost_per_render=2, max_credits=100)


def test_two_products_sharing_one_photo_are_refused():
    a = ProductInput(name="A", product_id="a", image_url="u1", image=image_bytes((200, 200), (9, 9, 9)))
    b = ProductInput(name="B", product_id="b", image_url="u2", image=image_bytes((200, 200), (9, 9, 9)))
    with pytest.raises(OrchestrationRefused, match="share one photo"):
        check_plan([a, b], max_products=10, cost_per_render=2, max_credits=100)


def test_a_look_over_the_credit_cap_is_refused_before_anything_is_spent():
    products = [_product(i) for i in range(6)]  # 6 x 2 = 12 credits
    with pytest.raises(OrchestrationRefused, match="12 FASHN credits"):
        check_plan(products, max_products=10, cost_per_render=2, max_credits=10)


def test_a_look_within_limits_is_accepted():
    check_plan([_product(i) for i in range(5)], max_products=10, cost_per_render=2, max_credits=10)


# --- the sequence -----------------------------------------------------------


async def _always_verified(original, previous, result, product):  # noqa: ANN001
    return StepVerdict(passed=True)


async def test_each_product_is_drawn_on_the_previous_result_in_order():
    calls: list[tuple[str, bytes]] = []

    async def render(image, product, on_submitted):  # noqa: ANN001
        calls.append((product.name, image))
        await on_submitted(f"job-{product.name}")
        return TryOnOutput(image_bytes=image + product.name.encode(), content_type="image/png", provider_job_id=f"job-{product.name}")

    stored: list[dict] = []

    async def on_step(steps):  # noqa: ANN001
        stored.clear()
        stored.extend(dict(s) for s in steps)

    raw: dict[str, bytes] = {}

    async def on_raw(step, data):  # noqa: ANN001
        raw[step["name"]] = data

    products = [_product(1), _product(2), _product(3)]
    result = await run_sequence(PERSON, products, render=render, verify=_always_verified, on_step=on_step, on_raw=on_raw)

    assert result.passed is True
    assert [name for name, _ in calls] == ["Product 1", "Product 2", "Product 3"]
    assert calls[0][1] == PERSON  # the first call starts from the person
    assert calls[1][1] == raw["Product 1"]  # each later call starts from the previous FASHN output
    assert calls[2][1] == raw["Product 2"]
    assert result.image == raw["Product 3"]  # the final image is the last output, untouched
    assert all(step["status"] == "verified" and step["verified"] for step in stored)
    assert [step["provider_job_id"] for step in stored] == ["job-Product 1", "job-Product 2", "job-Product 3"]
    assert all(step["raw_key"] is None for step in stored)  # keys are set by the caller's storage, not here


async def test_the_chain_stops_at_the_first_product_that_does_not_verify():
    sent: list[str] = []

    async def render(image, product, on_submitted):  # noqa: ANN001
        sent.append(product.name)
        return TryOnOutput(image_bytes=image + b"x", content_type="image/png", provider_job_id=product.name)

    async def verify(original, previous, result, product):  # noqa: ANN001
        if product.name == "Product 2":
            return StepVerdict(passed=False, failed_checks=["no_visible_edit"])
        return StepVerdict(passed=True)

    products = [_product(1), _product(2), _product(3)]
    steps_seen: list[list[dict]] = []

    async def on_step(steps):  # noqa: ANN001
        steps_seen.append([dict(s) for s in steps])

    async def on_raw(step, data):  # noqa: ANN001
        return None

    result = await run_sequence(PERSON, products, render=render, verify=verify, on_step=on_step, on_raw=on_raw)

    assert result.passed is False
    assert sent == ["Product 1", "Product 2"]  # product 3 was never sent
    final = result.steps
    assert [s["status"] for s in final] == ["verified", "failed", "selected"]
    assert final[1]["failed_checks"] == ["no_visible_edit"]
    assert final[2]["provider_job_id"] is None  # nothing was ever sent for it


async def test_a_product_is_never_sent_twice():
    counts: dict[str, int] = {}

    async def render(image, product, on_submitted):  # noqa: ANN001
        counts[product.name] = counts.get(product.name, 0) + 1
        return TryOnOutput(image_bytes=image + b"x", content_type="image/png", provider_job_id=product.name)

    async def noop(*_a, **_kw):  # noqa: ANN001, ANN002
        return None

    await run_sequence(PERSON, [_product(1), _product(2)], render=render, verify=_always_verified, on_step=noop, on_raw=noop)
    assert counts == {"Product 1": 1, "Product 2": 1}


# --- what counts as "drawn" --------------------------------------------------


async def test_an_unchanged_result_fails_the_edit_check(monkeypatch):
    responses = [{"flags": ["no_visible_edit"], "difference": {"edited_fraction": 0.0}}, {"flags": []}]

    async def fake_qc(original, product, result, **kw):  # noqa: ANN001, ANN003
        return responses.pop(0)

    monkeypatch.setattr(orchestrate, "run_qc", fake_qc)
    verdict = await verify_step(PERSON, PERSON, PERSON, _product(1))
    assert verdict.passed is False
    assert verdict.failed_checks == ["no_visible_edit"]


async def test_a_changed_face_fails_even_when_the_product_is_drawn(monkeypatch):
    responses = [
        {"flags": []},  # edit check: the product is there
        {"flags": ["face_changed"], "face": {"face_similarity": 0.4}},  # identity check: the person is not
    ]

    async def fake_qc(original, product, result, **kw):  # noqa: ANN001, ANN003
        return responses.pop(0)

    monkeypatch.setattr(orchestrate, "run_qc", fake_qc)
    verdict = await verify_step(PERSON, PERSON, PERSON, _product(1))
    assert verdict.passed is False
    assert verdict.failed_checks == ["identity:face_changed"]


async def test_earlier_products_do_not_count_as_a_face_change(monkeypatch):
    """Identity is judged against the ORIGINAL photo, so a shirt drawn in an
    earlier step is not flagged here; only face and head changes are."""
    responses = [{"flags": []}, {"flags": ["frame_margins_changed"]}]

    async def fake_qc(original, product, result, **kw):  # noqa: ANN001, ANN003
        return responses.pop(0)

    monkeypatch.setattr(orchestrate, "run_qc", fake_qc)
    verdict = await verify_step(PERSON, PERSON, PERSON, _product(1))
    assert verdict.passed is True
