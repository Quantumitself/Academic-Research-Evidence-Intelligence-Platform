"""Collection application service.

This subpackage owns the lifecycle of collections and their items:

- ``CollectionKind`` — the closed set of collection kinds.
- ``CollectionView`` — an immutable summary of a collection.
- ``CollectionItemView`` — an immutable summary of a collection item.
- ``CollectionService`` — the application service that creates, reads,
  updates, deletes, and lists collections and manages their items.
- ``CollectionError`` and subclasses — typed errors.

The service never imports Qt. It reads and writes through the
collection, collection-item, and project repositories, and writes audit
events through the audit repository.
"""

from academic_platform.application.collections.errors import (
    CollectionError,
    CollectionNotFoundError,
    CollectionValidationError,
)
from academic_platform.application.collections.model import (
    CollectionItemView,
    CollectionKind,
    CollectionView,
)
from academic_platform.application.collections.service import CollectionService

__all__ = [
    "CollectionError",
    "CollectionItemView",
    "CollectionKind",
    "CollectionNotFoundError",
    "CollectionService",
    "CollectionValidationError",
    "CollectionView",
]