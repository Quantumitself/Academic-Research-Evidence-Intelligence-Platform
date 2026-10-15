"""Tests for the pagination primitives."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.repositories.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
    PageRequest,
)


def test_default_page_request() -> None:
    request = PageRequest()
    assert request.page == 1
    assert request.size == DEFAULT_PAGE_SIZE


def test_page_request_offset_and_limit() -> None:
    request = PageRequest(page=3, size=20)
    assert request.offset == 40
    assert request.limit == 20


def test_page_request_rejects_bad_values() -> None:
    with pytest.raises(ValueError):
        PageRequest(page=0)
    with pytest.raises(ValueError):
        PageRequest(size=0)
    with pytest.raises(ValueError):
        PageRequest(size=MAX_PAGE_SIZE + 1)


def test_page_total_pages() -> None:
    page = Page(items=[1, 2, 3], request=PageRequest(page=1, size=2), total=5)
    assert page.total_pages == 3


def test_page_next_and_previous_requests() -> None:
    first = Page(items=[], request=PageRequest(page=1, size=10), total=25)
    assert first.has_next
    assert not first.has_previous
    assert first.next_request() == PageRequest(page=2, size=10)
    assert first.previous_request() is None

    last = Page(items=[], request=PageRequest(page=3, size=10), total=25)
    assert not last.has_next
    assert last.has_previous
    assert last.next_request() is None
    assert last.previous_request() == PageRequest(page=2, size=10)


def test_page_total_pages_zero_when_empty() -> None:
    page = Page(items=[], request=PageRequest(), total=0)
    assert page.total_pages == 0