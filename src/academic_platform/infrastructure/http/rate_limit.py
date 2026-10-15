"""Host-scoped token-bucket rate limiter.

The limiter enforces an average rate and a burst capacity for a single
host. It is constructed per client and is intended to be shared across
threads that issue requests to the same host.

Design decisions
----------------
- The limiter is process-local. It does not coordinate across processes;
  the desktop application is single-process.
- The limiter blocks when the bucket is empty. Callers that must not
  block use ``try_acquire`` and handle the rejection.
- The limiter is deliberately simple: a token bucket with a monotonic
  clock. It does not attempt to model sliding windows or distributed
  coordination.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """A token-bucket rate limiter."""

    def __init__(self, *, rate_per_second: float, burst: int) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        self._rate = float(rate_per_second)
        self._burst = int(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    @property
    def rate_per_second(self) -> float:
        return self._rate

    @property
    def burst(self) -> int:
        return self._burst

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def try_acquire(self) -> bool:
        """Attempt to consume one token.

        Returns True when a token was consumed and False when the bucket
        is empty. Does not block.
        """
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def acquire(self, *, timeout_seconds: float | None = None) -> bool:
        """Block until a token is available or the timeout elapses.

        Returns True when a token was consumed and False when the timeout
        elapsed. Passing ``None`` waits indefinitely.
        """
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                else:
                    remaining = None
            # Sleep outside the lock so other threads can proceed.
            wait_for = 1.0 / self._rate
            if remaining is not None and remaining < wait_for:
                wait_for = remaining
            if wait_for <= 0:
                wait_for = 0.01
            time.sleep(wait_for)

    def retry_after_seconds(self) -> float:
        """Return the delay before a token is expected to be available."""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                return 0.0
            missing = 1.0 - self._tokens
            return missing / self._rate