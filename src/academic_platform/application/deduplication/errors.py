"""Typed errors for the duplicate detection subsystem."""

from __future__ import annotations


class DuplicateDetectionError(RuntimeError):
    """Base class for duplicate detection failures."""