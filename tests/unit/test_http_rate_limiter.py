"""Tests for the token-bucket rate limiter."""

from __future__ import annotations

import time

import pytest

from academic_platform.infrastructure.http.rate_limit import RateLimiter


def test_rejects_nonpositive_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate_per_second=0, burst=1)


def test_rejects_nonpositive_burst() -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate_per_second=1, burst=0)


def test_burst_allows_initial_requests() -> None:
    limiter = RateLimiter(rate_per_second=100, burst=5)
    for _ in range(5):
        assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False


def test_refill_over_time() -> None:
    limiter = RateLimiter(rate_per_second=50, burst=1)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
    time.sleep(0.05)
    assert limiter.try_acquire() is True


def test_acquire_blocks_until_token_available() -> None:
    limiter = RateLimiter(rate_per_second=100, burst=1)
    assert limiter.acquire() is True
    started = time.monotonic()
    assert limiter.acquire(timeout_seconds=1.0) is True
    elapsed = time.monotonic() - started
    assert elapsed >= 0.005


def test_acquire_returns_false_on_timeout() -> None:
    limiter = RateLimiter(rate_per_second=0.1, burst=1)
    assert limiter.acquire() is True
    assert limiter.acquire(timeout_seconds=0.01) is False


def test_retry_after_when_full() -> None:
    limiter = RateLimiter(rate_per_second=10, burst=1)
    limiter.try_acquire()
    delay = limiter.retry_after_seconds()
    assert delay > 0
    assert delay <= 0.2


def test_retry_after_when_empty_bucket() -> None:
    limiter = RateLimiter(rate_per_second=10, burst=5)
    assert limiter.retry_after_seconds() == 0.0