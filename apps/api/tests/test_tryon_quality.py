"""The try-on quality pipeline: keep the person, take only the product,
inspect, retry or refuse. Offline — renders, vision and downloads are faked;
the merge itself runs for real on synthetic images."""

from __future__ import annotations

import asyncio

import cv2
import numpy as np
import pytest

from app.core.config import get_settings
from app.models.enums import OutfitSlot
from app.services.tryon_quality import pipeline
from app.services.tryon_quality.compose import Region, encode_jpeg, merge_product
from app.services.tryon_quality.judge import Verdict

H, W = 600, 400
ITEM = (250, 300, 330, 360)  # y0, x0, y1, x1 of the "watch" in the base image
FACE = (40, 150, 140, 250)


def _person() -> np.ndarray:
    """Photo-like: full tonal range, smooth areas and edges."""
    rng = np.random.default_rng(7)
    texture = cv2.GaussianBlur(rng.integers(0, 255, (H, W, 3), dtype=np.uint8), (0, 0), 3).astype(np.float32)
    texture = (texture - texture.mean()) * 4
    ramp = np.linspace(40, 215, W, dtype=np.float32)[None, :, None] + np.linspace(-20, 20, H, dtype=np.float32)[:, None, None]
    img = np.clip(ramp + texture, 0, 255).astype(np.uint8)
    cv2.rectangle(img, (60, 180), (340, 560), (90, 110, 150), -1)  # a body
    cv2.circle(img, (200, 90), 55, (120, 150, 190), -1)  # a head
    return img


def _render(base: np.ndarray, *, item: bool = True, colour=(200, 60, 20)) -> np.ndarray:
    """What FASHN hands back: bigger, globally re-toned, the face subtly
    redrawn — and (usually) the product added."""
    out = base.astype(np.float32) * 1.08 + 6  # global colour/contrast drift
    y0, x0, y1, x1 = FACE
    out[y0:y1, x0:x1] += np.random.default_rng(3).normal(0, 6, (y1 - y0, x1 - x0, 3))  # face drift
    if item:
        y0, x0, y1, x1 = ITEM
        out[y0:y1, x0:x1] = colour  # the product
    out = np.clip(out, 0, 255).astype(np.uint8)
    return cv2.resize(out, (int(W * 1.6), int(H * 1.6)), interpolation=cv2.INTER_CUBIC)


def _item_region() -> Region:
    y0, x0, y1, x1 = ITEM
    return Region(x0 / W, y0 / H, x1 / W, y1 / H)


def test_merge_takes_the_product_and_keeps_everything_else():
    base = _person()
    merged = merge_product(base, _render(base), _item_region())

    y0, x0, y1, x1 = ITEM
    product = merged.image[y0 + 8 : y1 - 8, x0 + 8 : x1 - 8].astype(int)
    assert np.abs(product - (200, 60, 20)).mean() < 25  # the product is there

    keep = np.ones((H, W), bool)
    keep[y0 - 20 : y1 + 20, x0 - 20 : x1 + 20] = False
    # the face and everything else: the person's own pixels, not the render's
    assert np.abs(merged.image[keep].astype(int) - base[keep]).mean() < 1.0
    fy0, fx0, fy1, fx1 = FACE
    assert np.array_equal(merged.image[fy0:fy1, fx0:fx1], base[fy0:fy1, fx0:fx1])


def test_merge_never_takes_a_protected_face():
    base = _person()
    render = _render(base)
    fy0, fx0, fy1, fx1 = FACE
    # even if the product region were over the face
    merged = merge_product(base, render, Region(0, 0, 1, 1), protect=[(fx0, fy0, fx1, fy1)])
    assert np.array_equal(merged.image[fy0:fy1, fx0:fx1], base[fy0:fy1, fx0:fx1])


@pytest.fixture
def fake_vision(monkeypatch):
    """No network: product download, description and location are faked;
    the test sets the inspector's verdicts."""
    verdicts: list[Verdict] = []

    async def download(url):  # noqa: ARG001
        return np.full((200, 200, 3), (200, 60, 20), np.uint8)

    async def describe(image, url, name):  # noqa: ARG001
        return f"{name} (described)"

    async def choose(marked, product, description, numbers):  # noqa: ARG001
        return numbers  # every changed area is the product in these synthetic renders

    async def judge(product, before, after, region, description, small_item=False):  # noqa: ARG001
        return verdicts.pop(0)

    monkeypatch.setattr(pipeline, "_download", download)
    monkeypatch.setattr(pipeline, "describe_product", describe)
    monkeypatch.setattr(pipeline, "choose", choose)
    monkeypatch.setattr(pipeline, "judge", judge)
    return verdicts


def _renderer(calls: list[tuple[str, int]], *, draws: bool = True):
    async def render(base_jpeg: bytes, item, hint) -> bytes:
        calls.append((hint.fix, hint.seed))
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base, item=draws), 97)

    return render


GOOD = Verdict(9, 9, 8)
BAD = Verdict(4, 5, 6, ["wrong strap colour"], "make the bracelet silver steel like the reference")
ITEMS = [pipeline.LookItem("https://img.example/watch.jpg", OutfitSlot.WATCH, "Bulova Blue Dial Watch")]


async def test_a_good_render_is_accepted_first_time(fake_vision):
    fake_vision.append(GOOD)
    calls: list = []
    image, reports = await pipeline.render_look(encode_jpeg(_person(), 97), ITEMS, _renderer(calls), retries=1)
    assert len(calls) == 1 and reports[0].attempts == 1
    assert image[:2] == b"\xff\xd8"


async def test_a_failed_inspection_is_retried_with_the_fix_and_a_new_seed(fake_vision):
    fake_vision.extend([BAD, GOOD])
    calls: list = []
    _, reports = await pipeline.render_look(encode_jpeg(_person(), 97), ITEMS, _renderer(calls), retries=1)
    assert len(calls) == 2
    assert calls[0][0] == "" and calls[1][0] == BAD.fix  # the inspector's correction goes to the model
    assert calls[0][1] != calls[1][1]  # a genuinely different render
    assert reports[0].verdict == GOOD


async def test_a_look_that_never_passes_is_refused_not_returned(fake_vision):
    fake_vision.extend([BAD, BAD])
    with pytest.raises(pipeline.QualityFailure) as exc:
        await pipeline.render_look(encode_jpeg(_person(), 97), ITEMS, _renderer([]), retries=1)
    assert exc.value.item == "Bulova Blue Dial Watch"
    assert "wrong strap colour" in exc.value.issues


async def test_a_render_without_the_product_fails_without_asking_the_inspector(fake_vision):
    calls: list = []
    with pytest.raises(pipeline.QualityFailure) as exc:
        await pipeline.render_look(
            encode_jpeg(_person(), 97), ITEMS, _renderer(calls, draws=False), retries=1
        )
    assert "not drawn" in exc.value.issues[0]
    assert len(calls) == 2 and not fake_vision  # judge never consulted


async def test_the_second_item_is_drawn_on_the_merged_image_not_the_raw_render(fake_vision):
    """Chaining raw renders compounds the model's redraw of the face; the
    pipeline feeds its merged result forward instead."""
    fake_vision.extend([GOOD, GOOD])
    person = _person()
    seen_bases: list[np.ndarray] = []

    async def render(base_jpeg, item, hint):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        seen_bases.append(base)
        colour = (200, 60, 20) if len(seen_bases) == 1 else (30, 180, 60)  # a second, different item
        return encode_jpeg(_render(base, colour=colour), 97)

    items = ITEMS * 2
    await pipeline.render_look(encode_jpeg(person, 97), items, render, retries=0)
    # the pipeline works at 2048px; map the face box onto that
    scale = seen_bases[0].shape[0] / H
    fy0, fx0, fy1, fx1 = (int(v * scale) for v in FACE)
    # the face the second render starts from is still the original one the
    # first render got — not the first render's redrawn face (up to JPEG)
    first, second = seen_bases[0][fy0:fy1, fx0:fx1].astype(int), seen_bases[1][fy0:fy1, fx0:fx1].astype(int)
    assert np.abs(second - first).mean() < 3


async def test_a_refused_look_fails_the_job_and_refunds(client, db, monkeypatch, fake_vision):
    """End to end through the worker with a real (non-mock) provider class:
    a render that never passes inspection is not returned as a success."""
    from app.ai.providers.base import TryOnOutput
    from app.ai.providers.fashn import FASHNTryOnProvider
    from tests.conftest import credit_balance, register_and_login, seed_product
    from tests.test_tryon import _poll_until_terminal, _upload_front_photo

    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-max")

    async def fake_generate(self, payload):  # noqa: ARG001
        base = _person()
        return TryOnOutput(image_bytes=encode_jpeg(_render(base), 95))

    monkeypatch.setattr(FASHNTryOnProvider, "generate", fake_generate)
    monkeypatch.setattr("app.workers.tasks.tryon_tasks.get_tryon_provider", lambda: provider)
    monkeypatch.setattr("app.ai.providers.registry.get_tryon_provider", lambda: provider)
    fake_vision.extend([BAD] * (get_settings().TRYON_QUALITY_RETRIES + 1))  # every attempt fails

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    before = await credit_balance(db, user_id)
    await db.rollback()  # release SQLite's read lock so the worker can write the job's outcome
    product = await seed_product(db, name="Bulova Blue Dial Watch")
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    assert resp.status_code == 201, resp.text
    # wait on a fresh session: under load, polling the API against the SQLite
    # test database kept returning a stale "processing" snapshot while the
    # worker had already committed the failure (verified by reading the row)
    import asyncio

    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    job_id = resp.json()["id"]
    for _ in range(600):
        async with AsyncSessionLocal() as fresh:
            status = (await fresh.execute(text("select status from tryon_jobs where id = :i"), {"i": job_id})).scalar()
        if status in ("FAILED", "COMPLETED", "failed", "completed"):
            break
        await asyncio.sleep(0.1)
    finished = await _poll_until_terminal(client, job_id, attempts=240, delay=0.25)

    assert finished["status"] == "failed"
    assert "couldn't draw" in finished["error_message"] and "wrong strap colour" in finished["error_message"]
    db.expire_all()
    assert await credit_balance(db, user_id) == before  # refunded


async def test_a_failed_small_item_is_retried_as_a_close_up_of_where_it_goes(fake_vision):
    """Live: a GMT watch's red-and-blue bezel came out wrong twice at full-body
    scale (~40px wide) and the try-on was refused. The retry renders a
    close-up of the wrist instead, where the watch is many times larger."""
    fake_vision.extend([BAD, GOOD])
    sizes: list[tuple[int, int]] = []

    async def render(base_jpeg, item, hint):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        sizes.append(base.shape[:2])
        out = base.astype(np.float32) * 1.05
        y0, x0, y1, x1 = (int(v * base.shape[0] / H) if i % 2 == 0 else int(v * base.shape[1] / W)
                          for i, v in enumerate(ITEM))
        if len(sizes) == 1:
            out[y0:y1, x0:x1] = (200, 60, 20)
        else:  # the close-up: paint the middle, where the item is
            ch, cw = base.shape[:2]
            out[ch // 3 : 2 * ch // 3, cw // 3 : 2 * cw // 3] = (200, 60, 20)
        return encode_jpeg(np.clip(out, 0, 255).astype(np.uint8), 97)

    _, reports = await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, render, retries=1, zoom_small=True
    )
    assert reports[0].attempts == 2
    full, close_up = sizes
    assert full[0] > close_up[0] or full[1] > close_up[1] or close_up != full  # a different, zoomed input
    assert max(close_up) >= 1000  # enlarged for the model


async def test_the_whole_look_is_one_render_and_only_failures_get_their_own(fake_vision):
    """OpenAI can draw several products in one edit: measured 39s for a
    4-item outfit against 101s item by item. Items that pass inspection keep
    that render; a failing item is rendered again on its own."""
    fake_vision.extend([GOOD, BAD, GOOD])  # item A passes, item B fails, then passes alone
    own_renders: list[str] = []
    whole_calls: list[int] = []

    async def render_all(base_jpeg: bytes, items, descriptions) -> bytes:
        assert descriptions and all(descriptions)  # the first pass knows what each product is
        whole_calls.append(len(items))
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    async def render_one(base_jpeg, item, hint):  # noqa: ARG001
        own_renders.append(item.name)
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base, colour=(30, 180, 60)), 97)

    items = [
        pipeline.LookItem("https://img.example/a.jpg", OutfitSlot.WATCH, "Item A"),
        pipeline.LookItem("https://img.example/b.jpg", OutfitSlot.SHOES, "Item B"),
    ]
    _, reports = await pipeline.render_look(
        encode_jpeg(_person(), 97), items, render_one, render_all=render_all, retries=1
    )
    assert whole_calls == [2]  # one render for both items
    assert own_renders == ["Item B"]  # only the one that failed
    assert reports[0].verdict == GOOD and reports[1].verdict == GOOD
    assert "whole look" in reports[0].history[0]


async def test_a_whole_look_render_that_fails_falls_back_to_item_by_item(fake_vision):
    fake_vision.extend([GOOD])

    async def render_all(base_jpeg, items, descriptions):  # noqa: ARG001
        raise RuntimeError("the model refused the request")

    calls: list = []
    _, reports = await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, _renderer(calls), render_all=render_all, retries=0
    )
    assert len(calls) == 1 and reports[0].verdict == GOOD


async def test_small_items_are_judged_at_the_size_they_are_actually_seen(monkeypatch):
    """Live: a Hamilton and a Seiko were refused for dial numerals and
    stitching that are unresolvable when the watch is ~40px wide — the
    customer can't see them either. Colour, shape and placement still count."""
    from app.services.tryon_quality import judge as judge_module

    asked: list[str] = []

    async def fake_ask(instructions, content, **kwargs):  # noqa: ARG001
        asked.append(instructions)
        return {"product_match": 8, "worn_correctly": 9, "realism": 8, "issues": [], "fix": ""}

    monkeypatch.setattr(judge_module, "ask_json", fake_ask)
    product = np.full((100, 100, 3), 40, np.uint8)
    person = _person()
    await judge_module.judge(product, person, person, _item_region(), "a watch", small_item=True)
    await judge_module.judge(product, person, person, _item_region(), "a shirt", small_item=False)

    assert "cannot see those either" in asked[0]
    assert "silhouette/shape or the placement are wrong" in asked[0]  # still fails a wrong product
    assert "cannot see those either" not in asked[1]  # a shirt is judged in full


def test_tiny_items_know_which_body_part_they_go_on():
    """A ring is ~15px across on a full-body photo, so it's rendered on a
    close-up of the hand — the model often didn't draw it at all otherwise
    ("the product was not drawn on the photo", a real refusal)."""
    part_of = pipeline._body_part_of
    hands = pipeline.LookItem("u", OutfitSlot.ACCESSORY, "US Army Military Ring Stainless Steel Eagle")
    ears = pipeline.LookItem("u", OutfitSlot.ACCESSORY, "Gold Plated Pearl Jhumka Earrings")
    neck = pipeline.LookItem("u", OutfitSlot.ACCESSORY, "Silver Pendant Necklace")
    shirt = pipeline.LookItem("u", OutfitSlot.TOP, "Cotton Shirt")
    assert "hands" in part_of(hands)
    assert "ears" in part_of(ears)
    assert "neck" in part_of(neck)
    assert part_of(shirt) is None  # a shirt is rendered on the whole photo


def test_a_tiny_item_is_held_to_a_slightly_lower_product_bar():
    """Filigree on a jhumka earring cannot survive at 30px; refusing the
    whole try-on over it helps nobody. Bigger items keep the full bar."""
    earring = pipeline.LookItem("u", OutfitSlot.ACCESSORY, "Jhumka Earrings")
    shirt = pipeline.LookItem("u", OutfitSlot.TOP, "Cotton Shirt")
    assert pipeline._min_product_for(earring, 7.0) == 6.0
    assert pipeline._min_product_for(shirt, 7.0) == 7.0
    assert pipeline._min_product_for(earring, 5.0) == 5.0  # never below the floor


async def test_a_rejected_item_is_re_rendered_at_the_detailed_setting(fake_vision):
    """Live: an ivory Pakistani maxi dress came back pink with its gold
    embroidery "too faint and sparse", and the try-on was refused. That is
    what the fast render setting costs; a second attempt is worth the extra
    seconds rather than refunding the customer."""
    fake_vision.extend([BAD, GOOD])
    hints: list = []

    async def render(base_jpeg, item, hint):  # noqa: ARG001
        hints.append(hint)
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    await pipeline.render_look(encode_jpeg(_person(), 97), ITEMS, render, retries=1)
    assert [h.detail for h in hints] == [False, True]  # fast first, detailed once it failed
    assert hints[1].fix == BAD.fix


async def test_what_the_product_is_goes_to_the_model_in_words_too(fake_vision):
    """The product photo alone kept losing colour and fine detail, so the
    description read off that photo is sent with it."""
    fake_vision.append(GOOD)
    hints: list = []

    async def render(base_jpeg, item, hint):  # noqa: ARG001
        hints.append(hint)
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    await pipeline.render_look(encode_jpeg(_person(), 97), ITEMS, render, retries=0)
    assert hints[0].description == "Bulova Blue Dial Watch (described)"  # from the product photo


async def test_an_item_the_whole_look_got_wrong_is_re_rendered_knowing_why(fake_vision):
    """The whole-look inspector already said what was wrong ("the dress is
    pink, it should be ivory"). Starting the item's own render without that
    invited the same mistake — and its first own attempt is detailed."""
    fake_vision.extend([BAD, GOOD])  # fails in the whole-look pass, passes on its own

    async def render_all(base_jpeg, items, descriptions):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    hints: list = []

    async def render_one(base_jpeg, item, hint):  # noqa: ARG001
        hints.append(hint)
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base, colour=(30, 180, 60)), 97)

    await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, render_one, render_all=render_all, retries=1
    )
    assert len(hints) == 1
    assert hints[0].fix == BAD.fix and hints[0].detail is True


async def test_items_that_dont_layer_are_re_rendered_at_the_same_time(fake_vision):
    """Live: a 3-item outfit sat on the spinner for 141s because every item
    that needed its own render waited for the one before it. Shoes, bags and
    jewellery don't layer onto each other, so they go together."""
    fake_vision.extend([GOOD, GOOD])
    both_started = asyncio.Event()
    started = 0

    async def render(base_jpeg, item, hint):  # noqa: ARG001
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=5)  # deadlocks if they're sequential
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    items = [
        pipeline.LookItem("https://img.example/shoes.jpg", OutfitSlot.SHOES, "Leather Boots"),
        pipeline.LookItem("https://img.example/watch.jpg", OutfitSlot.WATCH, "Bulova Watch"),
    ]
    _, reports = await pipeline.render_look(encode_jpeg(_person(), 97), items, render, retries=0)
    assert [r.verdict for r in reports] == [GOOD, GOOD]


async def test_clothes_are_still_drawn_one_on_top_of_the_other(fake_vision):
    """A jacket has to be rendered onto the shirt that went on before it —
    clothing can't be drawn side by side like a watch and shoes can."""
    fake_vision.extend([GOOD, GOOD])
    bases: list[np.ndarray] = []

    async def render(base_jpeg, item, hint):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        bases.append(base)
        return encode_jpeg(_render(base, colour=(200, 60, 20) if len(bases) == 1 else (30, 180, 60)), 97)

    items = [
        pipeline.LookItem("https://img.example/shirt.jpg", OutfitSlot.TOP, "Linen Shirt"),
        pipeline.LookItem("https://img.example/jacket.jpg", OutfitSlot.OUTERWEAR, "Denim Jacket"),
    ]
    await pipeline.render_look(encode_jpeg(_person(), 97), items, render, retries=0)
    assert len(bases) == 2
    y0, x0, y1, x1 = ITEM  # where _render paints, in the working image's own pixels
    # the jacket render starts from the photo with the shirt already on it
    assert not np.array_equal(bases[0][y0:y1, x0:x1], bases[1][y0:y1, x0:x1])


async def test_past_the_budget_the_best_attempt_ships_rather_than_nothing(fake_vision):
    """A shopper who has waited a minute wants their photo, not a refund
    and an apology. Inside the budget a poor render is still refused —
    see the test below — but past it the best one goes out."""
    fake_vision.extend([BAD, BAD, BAD])
    calls: list = []

    image, reports = await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, _renderer(calls), retries=5, budget_seconds=0.0
    )
    assert image.startswith(b"\xff\xd8")  # they got their photo
    assert len(calls) == 1  # and no second attempt was bought
    assert "out of time" in reports[0].history[-1]


async def test_inside_the_budget_a_poor_render_is_still_refused(fake_vision):
    """The time limit is a deadline, not a lowering of the bar."""
    fake_vision.extend([BAD, BAD])
    with pytest.raises(pipeline.QualityFailure):
        await pipeline.render_look(
            encode_jpeg(_person(), 97), ITEMS, _renderer([]), retries=1, budget_seconds=600
        )


async def test_the_report_says_where_each_item_ended_up(fake_vision):
    """The result view labels items on the photo, so the pipeline has to
    hand back the box it put each one in — not just a pass/fail."""
    fake_vision.append(GOOD)
    calls: list = []
    _, reports = await pipeline.render_look(encode_jpeg(_person(), 97), ITEMS, _renderer(calls), retries=0)
    box = reports[0].box
    assert box is not None
    assert 0 <= box.x0 < box.x1 <= 1 and 0 <= box.y0 < box.y1 <= 1
    # ITEM sits at x 300-360 of 400, y 250-330 of 600 — the box must land there
    assert 0.7 < box.x0 < 0.8 and 0.85 < box.x1 <= 0.95
    assert 0.35 < box.y0 < 0.45 and 0.5 < box.y1 < 0.6


async def test_an_item_the_whole_look_drew_is_boxed_without_its_own_render(fake_vision):
    fake_vision.append(GOOD)

    async def render_all(base_jpeg, items, descriptions):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    async def render_one(base_jpeg, item, hint):  # pragma: no cover — nothing should fail
        raise AssertionError("the whole-look render passed; no item needs its own")

    _, reports = await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, render_one, render_all=render_all, retries=0
    )
    assert reports[0].box is not None


async def test_the_job_is_told_what_the_render_is_doing(fake_vision):
    """A multi-item look can take a minute of real render time; a silent
    timer reads as stuck, so each stage says what it is doing."""
    fake_vision.extend([BAD, GOOD])
    said: list[str] = []

    async def render_all(base_jpeg, items, descriptions):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base), 97)

    async def render_one(base_jpeg, item, hint):  # noqa: ARG001
        base = cv2.imdecode(np.frombuffer(base_jpeg, np.uint8), cv2.IMREAD_COLOR)
        return encode_jpeg(_render(base, colour=(30, 180, 60)), 97)

    await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, render_one, render_all=render_all, retries=1,
        on_progress=lambda message: _remember(said, message),
    )
    assert any("Drawing" in m for m in said)
    assert any("Checking every item" in m for m in said)
    assert any("Redrawing" in m for m in said)
    assert said[-1] == "Finishing the photo"


async def _remember(into: list[str], message: str) -> None:
    into.append(message)


async def test_a_broken_progress_callback_never_fails_the_render(fake_vision):
    fake_vision.append(GOOD)

    async def explode(message: str) -> None:  # noqa: ARG001
        raise RuntimeError("the status write failed")

    image, _ = await pipeline.render_look(
        encode_jpeg(_person(), 97), ITEMS, _renderer([]), retries=0, on_progress=explode
    )
    assert image[:2] == b"\xff\xd8"  # the customer still gets their photo


def test_a_marker_cannot_land_somewhere_the_item_could_never_be():
    """Live: jhumka earrings were labelled onto the chandelier above the
    bride's head — the render had nudged the ceiling lights and the
    vision model picked that blob. Earrings are on ears."""
    from app.services.face_restore import Box

    # the bride stands in the room, her face a quarter of the way down;
    # the ceiling lights are well above her hair
    face = Box(x=400, y=380, w=200, h=260)
    shape = (1536, 1024)

    earrings = pipeline.LookItem("https://img/x.jpg", OutfitSlot.ACCESSORY, "Kundan Pearl Jhumka Earrings")
    area = pipeline._plausible_area(earrings, face, shape)
    assert area is not None
    chandelier = pipeline.Region(0.35, 0.02, 0.65, 0.12)  # far above the head
    assert pipeline._settle(chandelier, area) == area  # nothing of it survives
    on_the_ear = pipeline.Region(0.37, 0.30, 0.42, 0.37)
    assert pipeline._settle(on_the_ear, area) == on_the_ear  # left exactly as it is


def test_a_necklace_belongs_below_the_face_not_above_it():
    from app.services.face_restore import Box

    face = Box(x=400, y=100, w=200, h=260)
    necklace = pipeline.LookItem("https://img/x.jpg", OutfitSlot.ACCESSORY, "14k Gold Rope Chain Necklace")
    area = pipeline._plausible_area(necklace, face, (1536, 1024))
    assert area is not None
    collarbone = pipeline.Region(0.44, 0.22, 0.56, 0.26)
    assert pipeline._settle(collarbone, area) == collarbone
    assert pipeline._settle(pipeline.Region(0.44, 0.03, 0.56, 0.07), area) == area  # in the ceiling


def test_items_with_no_fixed_place_are_left_alone():
    """A dress or a bag can be almost anywhere in frame; only things with
    an anatomical home are second-guessed."""
    from app.services.face_restore import Box

    dress = pipeline.LookItem("https://img/x.jpg", OutfitSlot.DRESS, "Bridal Red Lehenga Choli")
    assert pipeline._plausible_area(dress, Box(x=400, y=100, w=200, h=260), (1536, 1024)) is None


def test_shoes_cannot_be_recorded_as_the_whole_standing_body():
    """Live: a pair of derby shoes came back with a box of x 0.08-0.71,
    y 0.04-1.00 — the render changed the dress and the shoes together, so
    the shoes took the whole figure, and their card beside the photo was
    another copy of the photo."""
    from app.services.face_restore import Box

    shoes = pipeline.LookItem("https://img/x.jpg", OutfitSlot.SHOES, "George Men's Tan Leather Derby Shoes")
    area = pipeline._plausible_area(shoes, Box(x=400, y=380, w=200, h=260), (1536, 1024))
    assert area is not None

    whole_body = pipeline.Region(0.077, 0.042, 0.711, 1.0)
    settled = pipeline._settle(whole_body, area)
    # the render still knew which side of the frame they were on
    assert (settled.x0, settled.x1) == (0.077, 0.711)
    assert settled.y0 >= 0.6 and settled.y1 == 1.0


def test_a_box_with_nothing_plausible_left_falls_back_to_the_area():
    area = pipeline.Region(0.2, 0.6, 0.8, 1.0)
    in_the_ceiling = pipeline.Region(0.3, 0.02, 0.5, 0.1)
    assert pipeline._settle(in_the_ceiling, area) == area


def test_a_shoes_box_that_is_already_at_the_feet_is_left_alone():
    from app.services.face_restore import Box

    shoes = pipeline.LookItem("https://img/x.jpg", OutfitSlot.SHOES, "Suede Ankle Boots")
    area = pipeline._plausible_area(shoes, Box(x=400, y=380, w=200, h=260), (1536, 1024))
    at_the_feet = pipeline.Region(0.423, 0.931, 0.671, 1.0)
    assert area is not None and pipeline._settle(at_the_feet, area) == at_the_feet


def test_a_dress_is_never_second_guessed():
    """A garment legitimately covers most of a full-body photo."""
    from app.services.face_restore import Box

    dress = pipeline.LookItem("https://img/x.jpg", OutfitSlot.DRESS, "Pakistani Salwar Kameez 3 PC")
    assert pipeline._plausible_area(dress, Box(x=400, y=380, w=200, h=260), (1536, 1024)) is None


def test_embroidery_the_colour_of_what_it_replaced_still_counts_as_a_change():
    """Live, on a Pakistani lawn suit: the customer wore a plain white
    T-shirt and the kameez's chest panel is dense white embroidery on
    pink. White thread on white cotton is almost no colour difference, so
    the merge kept the T-shirt and the embroidery dissolved into a cream
    smear. Texture says what colour cannot."""
    from app.services.tryon_quality.compose import detail_diff

    import cv2

    flat = np.full((160, 160, 3), 232, np.uint8)  # a plain white T-shirt
    embroidered = flat.copy()
    for y in range(4, 160, 8):  # raised white thread on white cloth
        embroidered[y : y + 3, :] = 255

    by_colour = np.linalg.norm(
        cv2.cvtColor(flat, cv2.COLOR_BGR2LAB).astype(np.float32)
        - cv2.cvtColor(embroidered, cv2.COLOR_BGR2LAB).astype(np.float32),
        axis=2,
    ).mean()
    by_texture = detail_diff(flat, embroidered)[40:120, 40:120].mean()

    assert by_colour < 14.0  # colour alone never sees it: below "changed"
    assert by_texture > 14.0  # texture does
    assert detail_diff(flat, flat).max() < 1.0  # and is silent when nothing changed


def test_the_head_is_protected_without_leaving_an_edge_on_the_chest():
    """Two live failures, one on each side of this.

    A filled rectangle left its own outline: the kameez stopped along a
    straight horizontal line across the collarbone. An oval drawn inside
    that rectangle then stopped covering its corners — which is where the
    hair is — and the render's smeared background was taken over her
    head. It has to cover the corners above and leave the ones below."""
    from app.services.tryon_quality.compose import _blocked

    blocked = _blocked((400, 400), [(100, 100, 300, 300)])
    assert blocked[200, 200]  # the face itself
    assert blocked[105, 105] and blocked[105, 295]  # the hair, at the top corners
    assert blocked[150, 102] and blocked[150, 298]  # and down the sides of the head

    assert not blocked[295, 105] and not blocked[295, 295]  # the shoulders are free
    assert not blocked[298, 200]  # ...and so is the collarbone
    # nothing straight anywhere along the bottom for an edge to show
    assert blocked[298, :].sum() == 0


def test_a_box_that_is_in_the_right_place_but_far_too_big_is_still_trimmed():
    """Live: the tote's box was centred on her hands — the right place —
    and still covered 42% of the photo, because the whole-look render
    changed the outfit around the bag as well as the bag."""
    hands = pipeline.Region(0.303, 0.025, 0.848, 0.653)
    swallowed_the_body = pipeline.Region(0.205, 0.164, 0.712, 1.0)
    tote = pipeline.LookItem("https://img/x.jpg", OutfitSlot.BAG, "Leather Tote Bag")

    assert pipeline._too_big_to_be(tote, swallowed_the_body)
    trimmed = pipeline._settle(swallowed_the_body, hands)
    assert not pipeline._too_big_to_be(tote, trimmed)


def test_an_item_with_no_believable_place_stops_claiming_one():
    """A dot on the middle of someone's chest calling itself a handbag is
    worse than no dot. The item still appears in the list of what was put
    on; it just doesn't point anywhere."""
    tote = pipeline.LookItem("https://img/x.jpg", OutfitSlot.BAG, "Leather Tote Bag")
    assert pipeline._too_big_to_be(tote, pipeline.Region(0.2, 0.16, 0.71, 1.0))
    # ...while a dress really is most of a full-body photo
    dress = pipeline.LookItem("https://img/x.jpg", OutfitSlot.DRESS, "Salwar Kameez")
    assert not pipeline._too_big_to_be(dress, pipeline.Region(0.0, 0.16, 1.0, 1.0))


def test_texture_rescues_inside_the_garment_and_never_outside_it():
    """Live, on a wedding hall: the whole room — chandeliers, flowers,
    tables, floor — came back spattered with fragments of a blue blouse.
    An image model redraws a blurred background differently every time,
    and a blurred background is nothing but local contrast, so counting
    texture as change anywhere made everywhere change.

    Inside the garment the same signal is what rescues white embroidery
    on a white T-shirt. Both at once, on one mask."""
    from app.services.tryon_quality.compose import _mask_from

    shape = (400, 400)
    garment = (slice(100, 300), slice(150, 250))
    core = np.zeros(shape, np.uint8)
    core[garment] = 1
    core[180:220, 170:230] = 0  # a band of it the same colour as what it replaced

    weak = np.zeros(shape, np.int32)
    weak[garment] = 1

    colour = np.full(shape, 5.0, np.float32)  # nothing differs by colour...
    colour[core.astype(bool)] = 50.0  # ...except the garment around that band
    texture = np.full(shape, 50.0, np.float32)  # ...and everything differs by texture

    mask = _mask_from(core, weak, np.zeros(shape, bool), 0.03, colour, detail=texture)

    assert mask[190:210, 180:220].mean() > 0.9  # the band is rescued
    outside = np.ones(shape, bool)
    outside[60:340, 110:290] = False  # the garment and a wide margin round it
    assert mask[outside].mean() < 0.01  # the room is left alone


def test_nothing_off_the_body_can_be_taken_for_the_product():
    """Live, on a wedding hall: a pale blue blouse came back spattered
    across the whole room — the ceiling, the flowers, the tables. An
    image model rebuilds a blurred background from scratch every time, so
    a great deal of it 'changes', and anything that changes can be
    mistaken for the product. Nobody wears a blouse on the ceiling."""
    from app.services.face_restore import Box

    face = Box(x=460, y=180, w=110, h=140)
    area = pipeline._body_area(face, (1536, 1024))
    assert area is not None

    assert area[700, 515]  # her torso
    assert area[1400, 300] and area[1400, 730]  # the sweep of a long hem
    assert area[250, 470]  # her head

    assert not area[100, 900]  # a chandelier in the corner of the ceiling
    assert not area[300, 60]  # a flower arch at the far left
    assert not area[1450, 990]  # a table leg at the far right


def test_a_photo_with_no_face_found_is_left_entirely_alone():
    """Better to trust the render everywhere than to cut a body out of
    the wrong place."""
    assert pipeline._body_area(None, (1536, 1024)) is None
