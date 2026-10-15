"""Typed errors for the publication normalization subsystem."""

from __future__ import annotations


class PublicationNormalizationError(RuntimeError):
    """Base class for publication normalization failures."""


class PublicationKeyError(PublicationNormalizationError):
    """Raised when a search hit cannot produce a stable publication key."""


class PublicationPersistenceError(PublicationNormalizationError):
    """Raised when a normalized publication cannot be persisted."""