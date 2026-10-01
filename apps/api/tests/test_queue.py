"""The in-process job queue fallback (no REDIS_URL): enqueue_tryon_job
fires an asyncio task directly on this process's event loop rather than
handing it to a real worker. wait_for_inprocess_jobs() is what lets a
test wait for that task deterministically instead of polling the HTTP
API against a wall-clock sleep and hoping the scheduler was fast enough —
a real, repeatedly observed source of flakiness under CPU load."""

from __future__ import annotations

import asyncio

from app.services import queue


async def test_waiting_for_no_tasks_is_a_no_op():
    assert queue._inprocess_tasks == set()
    await queue.wait_for_inprocess_jobs()  # must not hang or raise on an empty set


async def test_it_actually_waits_for_a_real_in_flight_task():
    ran = False

    async def slow():
        nonlocal ran
        await asyncio.sleep(0.05)
        ran = True

    task = asyncio.create_task(slow())
    queue._inprocess_tasks.add(task)
    task.add_done_callback(queue._inprocess_tasks.discard)

    await queue.wait_for_inprocess_jobs()
    assert ran  # not just "returned" — the task's own body actually completed


async def test_it_waits_for_every_tracked_task_not_just_the_first():
    finished = []

    async def slow(n: int, delay: float):
        await asyncio.sleep(delay)
        finished.append(n)

    tasks = [asyncio.create_task(slow(n, delay)) for n, delay in enumerate([0.08, 0.02, 0.05])]
    for t in tasks:
        queue._inprocess_tasks.add(t)
        t.add_done_callback(queue._inprocess_tasks.discard)

    await queue.wait_for_inprocess_jobs()
    assert sorted(finished) == [0, 1, 2]


async def test_a_failing_task_does_not_stop_the_wait_or_raise():
    async def boom():
        raise RuntimeError("a job task failing must never break the wait for the others")

    task = asyncio.create_task(boom())
    queue._inprocess_tasks.add(task)
    task.add_done_callback(queue._inprocess_tasks.discard)

    await queue.wait_for_inprocess_jobs()  # return_exceptions=True: must not propagate
    assert queue._inprocess_tasks == set()
