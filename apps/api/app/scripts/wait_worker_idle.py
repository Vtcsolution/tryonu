"""Wait until no try-on is being drawn, so an update can restart the worker
without cutting a picture off halfway (once FASHN has the picture, a cut-off
job can only be held for review). Gives up waiting after --max seconds.

    python -m app.scripts.wait_worker_idle --max 240

Read-only: looks at the queue, changes nothing.
"""

from __future__ import annotations

import argparse
import sys
import time

from app.services.queue import queue_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=240, help="the longest to wait, in seconds")
    args = parser.parse_args()
    deadline = time.monotonic() + args.max
    said = False
    while True:
        state = queue_state()
        busy = state.get("busy", 0)
        if not busy:
            print("   No try-on is being drawn: the worker can restart.")
            return 0
        if time.monotonic() > deadline:
            print(f"   Still drawing after {args.max}s: restarting anyway (a cut-off try-on starts again by itself).")
            return 0
        if not said:
            print("   A try-on is being drawn: waiting for it to finish before restarting the worker...")
            said = True
        time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
