"""Global search interface.

The global search page presents two result surfaces:

- ``Local`` — results drawn from the user's own library, projects,
  collections, notes, and extracted evidence.
- ``Remote`` — results drawn from the enabled academic search sources.

Both surfaces are presented through a shared result list component so that
the visual rhythm is consistent and so that result entries can be rendered
uniformly regardless of origin. The page never claims a source succeeded
when it did not; per-source status is reported explicitly.

The page is presentation-only. It emits search requests and renders the
result payloads supplied by a controller. The controller is responsible
for reaching repositories, HTTP clients, or any other data source.
"""

from academic_platform.ui.pages.search.search_page import GlobalSearchPage
from academic_platform.ui.pages.search.result_list import (
    SearchResultEntry,
    SearchResultList,
    SearchResultOrigin,
)

__all__ = [
    "GlobalSearchPage",
    "SearchResultEntry",
    "SearchResultList",
    "SearchResultOrigin",
]