"""Typed errors for the annotation service."""

from __future__ import annotations


class AnnotationError(RuntimeError):
    """Base class for annotation service failures."""


class AnnotationNotFoundError(AnnotationError):
    """Raised when an annotation cannot be found by its identifier."""