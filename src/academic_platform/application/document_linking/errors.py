"""Typed errors for the document linking service."""

from __future__ import annotations


class LinkingError(RuntimeError):
    """Base class for linking failures."""


class LinkingTargetNotFoundError(LinkingError):
    """Raised when the target collection or project does not exist."""