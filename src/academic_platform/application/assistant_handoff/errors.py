"""Typed errors for the reader → assistant handoff."""

from __future__ import annotations


class AssistantHandoffError(RuntimeError):
    """Base class for handoff failures."""


class AssistantHandoffNotFoundError(AssistantHandoffError):
    """Raised when the requested document cannot be found for handoff."""