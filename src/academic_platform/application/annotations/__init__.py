"""Annotation application service.

This subpackage owns the lifecycle of user-authored annotations
(notes, highlights, and bookmarks) on documents:

- ``AnnotationKind`` — the set of supported annotation kinds.
- ``AnnotationColor`` — the set of supported highlight colors.
- ``AnnotationView`` — an immutable value object describing an
  annotation for the presentation layer.
- ``AnnotationService`` — the application service that creates, updates,
  lists, deletes, and exports annotations.
- ``AnnotationError`` and subclasses — typed errors.

The service never imports Qt. It reads and writes through the
``annotation`` repository and keeps the FTS5 note index in sync.
"""

from academic_platform.application.annotations.errors import (
    AnnotationError,
    AnnotationNotFoundError,
)
from academic_platform.application.annotations.model import (
    AnnotationColor,
    AnnotationKind,
    AnnotationView,
)
from academic_platform.application.annotations.service import (
    AnnotationService,
)

__all__ = [
    "AnnotationColor",
    "AnnotationError",
    "AnnotationKind",
    "AnnotationNotFoundError",
    "AnnotationService",
    "AnnotationView",
]