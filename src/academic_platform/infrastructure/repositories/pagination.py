"""Pagination primitives.

``PageRequest`` describes what slice of a result set to read. ``Page``
carries the slice together with the total count and the request that
produced it.

Design decisions
----------------
- ``PageRequest`` validates its values eagerly. A request with a page
  index below 1 or a size below 1 is rejected at construction.
- ``Page`` is generic over the item type so that callers retain type
  information.
- The total count is always computed. Callers that do not need a total
  can ignore the field; the count query is cheap on the indexed columns
  the application uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

ItemT = TypeVar("ItemT")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


@dataclass(frozen=True, slots=True)
class PageRequest:
    """A request for one page of results.

    Attributes
    ----------
    page:
        1-based page index.
    size:
        Number of items per page. Must be between 1 and ``MAX_PAGE_SIZE``.
    """

    page: int = 1
    size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be at least 1")
        if self.size < 1:
            raise ValueError("size must be at least 1")
        if self.size > MAX_PAGE_SIZE:
            raise ValueError(f"size must not exceed {MAX_PAGE_SIZE}")

    @property
    def offset(self) -> int:
        """Return the row offset corresponding to this request."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Return the row limit corresponding to this request."""
        return self.size


@dataclass(frozen=True, slots=True)
class Page(Generic[ItemT]):
    """A page of results together with pagination metadata."""

    items: Sequence[ItemT]
    request: PageRequest
    total: int

    @property
    def page(self) -> int:
        return self.request.page

    @property
    def size(self) -> int:
        return self.request.size

    @property
    def total_pages(self) -> int:
        if self.request.size <= 0:
            return 0
        return (self.total + self.request.size - 1) // self.request.size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    def next_request(self) -> PageRequest | None:
        """Return the request for the next page, or None when at the end."""
        if not self.has_next:
            return None
        return PageRequest(page=self.page + 1, size=self.size)

    def previous_request(self) -> PageRequest | None:
        """Return the request for the previous page, or None at the start."""
        if not self.has_previous:
            return None
        return PageRequest(page=self.page - 1, size=self.size)