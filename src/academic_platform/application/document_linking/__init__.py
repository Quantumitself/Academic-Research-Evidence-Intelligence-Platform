"""Document linking application service.

This subpackage exposes operations that associate documents with
collections and projects. It provides:

- ``LinkTarget`` — an enum describing the two association kinds.
- ``CollectionOption`` and ``ProjectOption`` — immutable value objects
  describing a link target available to the user.
- ``LinkingResult`` — the outcome of a link operation.
- ``DocumentLinkingService`` — the application service that lists link
  targets and adds or removes documents from them.
- ``LinkingError`` and subclasses — typed errors.

The service never imports Qt. It reuses the collection and project
repositories from the persistence layer.
"""

from academic_platform.application.document_linking.errors import (
    LinkingError,
    LinkingTargetNotFoundError,
)
from academic_platform.application.document_linking.model import (
    CollectionOption,
    LinkTarget,
    LinkingResult,
    ProjectOption,
)
from academic_platform.application.document_linking.service import (
    DocumentLinkingService,
)

__all__ = [
    "CollectionOption",
    "DocumentLinkingService",
    "LinkTarget",
    "LinkingError",
    "LinkingResult",
    "LinkingTargetNotFoundError",
    "ProjectOption",
]