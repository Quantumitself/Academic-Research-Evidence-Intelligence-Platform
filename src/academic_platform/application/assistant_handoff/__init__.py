"""Reader → research assistant handoff.

This subpackage packages a document and its current reading position
into a payload the research assistant will consume once the assistant
is implemented:

- ``AssistantHandoff`` — an immutable payload describing the document,
  its extracted metadata, the current page, and an optional excerpt.
- ``HandoffOptions`` — the user-selectable inclusion options.
- ``HandoffStore`` — a lightweight in-process store that holds the most
  recent handoff per document.
- ``AssistantHandoffService`` — the application service that composes
  a payload from a document and stores it.
- ``AssistantHandoffError`` and subclasses — typed errors.

The subpackage never imports Qt. It reads metadata and chunks through
the repository layer and the in-document search service.
"""

from academic_platform.application.assistant_handoff.errors import (
    AssistantHandoffError,
    AssistantHandoffNotFoundError,
)
from academic_platform.application.assistant_handoff.model import (
    AssistantHandoff,
    HandoffOptions,
)
from academic_platform.application.assistant_handoff.service import (
    AssistantHandoffService,
)
from academic_platform.application.assistant_handoff.store import (
    HandoffStore,
    default_handoff_store,
)

__all__ = [
    "AssistantHandoff",
    "AssistantHandoffError",
    "AssistantHandoffNotFoundError",
    "AssistantHandoffService",
    "HandoffOptions",
    "HandoffStore",
    "default_handoff_store",
]