"""Simple in-memory rate limiter for sensitive endpoints.

Used by the pairing flow (``/api/marketplace/pair/code`` and
``/api/bridge/pair/complete``) to make brute-forcing the 6-char pairing code
provably infeasible. The code space is ~887M; a 10/min cap on completion
attempts means even a sustained online attack manages ~5.3M attempts/year —
nowhere near the space.

This is intentionally minimal: a sliding-window counter keyed by client IP.
For a local-first tool that binds to 127.0.0.1, the only realistic attacker
is the browser (one origin), so per-IP is the right granularity. It is NOT a
general-purpose rate limiter — no Redis, no distributed coordination.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class _Bucket:
    """A sliding window of request timestamps for one key."""

    timestamps: list[float] = field(default_factory=list)

    def hit(self, now: float, window: float, limit: int) -> bool:
        """Record a hit. Returns True if allowed, False if over the limit."""
        # Drop timestamps outside the window.
        cutoff = now - window
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= limit:
            return False
        self.timestamps.append(now)
        return True


class RateLimiter:
    """Sliding-window rate limiter. Thread-safe, in-memory, per-key."""

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for ``key``. True if within the limit, False if over."""
        now = time.monotonic()
        with self._lock:
            return self._buckets[key].hit(now, self._window, self._limit)

    def reset(self) -> None:
        """Clear all buckets (used by tests)."""
        with self._lock:
            self._buckets.clear()


# ---- module-level limiter for the pairing flow ----
#
# 10 pairing attempts per minute from one origin. The code lives 10 minutes
# and is single-use; the legitimate user enters it once. An attacker guessing
# gets at most 10 tries per window — the 887M codespace is unreachable.
_pairing_limiter: RateLimiter | None = None


def get_pairing_limiter() -> RateLimiter:
    global _pairing_limiter
    if _pairing_limiter is None:
        _pairing_limiter = RateLimiter(limit=10, window_seconds=60.0)
    return _pairing_limiter


def set_pairing_limiter(limiter: RateLimiter | None) -> None:
    """Override the singleton (tests inject a fresh one)."""
    global _pairing_limiter
    _pairing_limiter = limiter
