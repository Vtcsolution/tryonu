"""Which commit this process is running.

"Is the fix deployed?" has cost more time in this project than most bugs:
a pull without a restart, a restart without a pull, and a symptom that
looks identical either way. The running code can answer it itself.

Read from the checkout's git metadata, not a subprocess — no shelling
out on a health check, and nothing to go wrong if git isn't installed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def running_commit() -> str | None:
    """The short sha this process was started from, if it can be read."""
    git = _repo_root() / ".git"
    try:
        head = (git / "HEAD").read_text().strip()
        if not head.startswith("ref: "):
            return head[:7]  # detached head
        ref = head[5:]
        direct = git / ref
        if direct.exists():
            return direct.read_text().strip()[:7]
        # a packed ref, which is what a fresh clone usually has
        for line in (git / "packed-refs").read_text().splitlines():
            if line.endswith(f" {ref}"):
                return line.split()[0][:7]
    except Exception:  # noqa: BLE001 — never let a health check fail on this
        return None
    return None
