"""Several real products, one person: each product drawn by its own FASHN call.

FASHN's try-on takes one product per call, so an outfit is built in order:
person -> product 1 -> verify -> product 2 -> verify -> ... -> final. Each
call's output becomes the next call's input, and every raw output is handed
to the caller before anything else happens to it. Nothing is re-rendered,
merged or restored here. A product that does not verify stops the chain: no
later product is drawn on top of an unverified one, and nothing is skipped
silently.

The module never calls FASHN itself. The caller passes `render`, so the whole
sequence can be tested with fakes and the credit cap is enforced before the
first call.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.ai.providers.base import TryOnOutput
from app.services.tryon_direct.qc import qc_gate, run_qc

# FASHN's documented credit cost per image (tryon-max): mode -> resolution -> credits
FASHN_CREDITS = {
    "fast": {"1k": 1, "2k": 2, "4k": 3},
    "balanced": {"1k": 2, "2k": 3, "4k": 4},
    "quality": {"1k": 3, "2k": 4, "4k": 5},
}
_IDENTITY_FLAGS = {"face_changed", "head_changed"}


class OrchestrationRefused(Exception):
    """A plan that must not start: nothing has been sent to FASHN yet."""


def credits_per_render(resolution: str, mode: str) -> int:
    return FASHN_CREDITS[mode][resolution]


@dataclass(frozen=True)
class ProductInput:
    name: str
    product_id: str | None
    image_url: str
    image: bytes


@dataclass(frozen=True)
class StepVerdict:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    edit_report: dict = field(default_factory=dict)
    identity_report: dict = field(default_factory=dict)


@dataclass
class SequenceResult:
    passed: bool
    image: bytes
    steps: list[dict]
    output: TryOnOutput | None


def check_plan(products: list[ProductInput], *, max_products: int, cost_per_render: int, max_credits: int) -> None:
    if not products:
        raise OrchestrationRefused("no products were selected")
    if len(products) > max_products:
        raise OrchestrationRefused(f"at most {max_products} products can be applied in one try-on")
    keys = [p.product_id or p.image_url for p in products]
    if len(set(keys)) != len(keys):
        raise OrchestrationRefused("the same product was selected more than once")
    digests = {hashlib.sha256(p.image).hexdigest() for p in products}
    if len(digests) != len(products):
        raise OrchestrationRefused("two selected products share one photo; they cannot both be drawn")
    if len(products) * cost_per_render > max_credits:
        raise OrchestrationRefused(
            f"this look would use {len(products) * cost_per_render} FASHN credits, above the limit of {max_credits}"
        )


def _qc_summary(verdict: StepVerdict) -> dict:
    """The measurements that decided one product, kept with its step."""
    res = verdict.edit_report.get("resolution") or {}
    diff = verdict.edit_report.get("difference") or {}
    product = verdict.edit_report.get("product") or {}
    face = verdict.identity_report.get("face") or {}
    return {
        "output_width": res.get("output_width"),
        "output_height": res.get("output_height"),
        "edited_fraction": diff.get("edited_fraction"),
        "product_match_score": product.get("product_match_score"),
        "face_similarity": face.get("face_similarity"),
    }


async def verify_step(
    original: bytes, previous: bytes, result: bytes, product: ProductInput
) -> StepVerdict:
    """Did this product actually get drawn, and is the person still the person?

    The edit check compares the result with the image it was drawn onto, so
    it measures this product alone. The identity check compares the result
    with the customer's original photo, so earlier products don't count as
    a face change."""
    edit = await run_qc(previous, product.image, result, product_name=product.name, product_url=product.image_url)
    failed = list(qc_gate(edit)["failed_checks"])
    identity = await run_qc(original, product.image, result, product_name=product.name, product_url=product.image_url)
    failed += [f"identity:{flag}" for flag in identity.get("flags", []) if flag in _IDENTITY_FLAGS]
    return StepVerdict(passed=not failed, failed_checks=failed, edit_report=edit, identity_report=identity)


Render = Callable[[bytes, ProductInput, Callable[[str], Awaitable[None]]], Awaitable[TryOnOutput]]
Verify = Callable[[bytes, bytes, bytes, ProductInput], Awaitable[StepVerdict]]
OnStep = Callable[[list[dict]], Awaitable[None]]
OnRaw = Callable[[dict, bytes], Awaitable[None]]


async def run_sequence(
    person: bytes,
    products: list[ProductInput],
    *,
    render: Render,
    verify: Verify,
    on_step: OnStep,
    on_raw: OnRaw,
) -> SequenceResult:
    steps = [
        {
            "index": i,
            "name": p.name,
            "product_id": p.product_id,
            "image_url": p.image_url,
            "status": "selected",
            "provider_job_id": None,
            "raw_key": None,
            "verified": False,
            "failed_checks": [],
        }
        for i, p in enumerate(products)
    ]
    await on_step(steps)

    current = person
    last: TryOnOutput | None = None
    for step, product in zip(steps, products):
        step["status"] = "sent"
        await on_step(steps)

        async def submitted(provider_job_id: str, step: dict = step) -> None:
            step["provider_job_id"] = provider_job_id
            await on_step(steps)

        output = await render(current, product, submitted)
        last = output
        step["status"] = "generated"
        await on_raw(step, output.image_bytes)
        await on_step(steps)

        verdict = await verify(person, current, output.image_bytes, product)
        step["verified"] = verdict.passed
        step["failed_checks"] = verdict.failed_checks
        step["qc"] = _qc_summary(verdict)
        if not verdict.passed:
            step["status"] = "failed"
            await on_step(steps)
            return SequenceResult(passed=False, image=output.image_bytes, steps=steps, output=output)

        step["status"] = "verified"
        await on_step(steps)
        current = output.image_bytes

    return SequenceResult(passed=True, image=current, steps=steps, output=last)
