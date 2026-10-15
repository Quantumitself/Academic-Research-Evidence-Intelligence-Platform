"""Typed exceptions for the database subpackage.

The subpackage raises only these exceptions outward. SQLAlchemy exceptions
are caught at the boundary and translated so that callers do not depend on
the persistence library's exception hierarchy.
"""

from __future__ import annotations


class DatabaseError(RuntimeError):
    """Raised when a database operation fails at runtime."""


class DatabaseConfigurationError(DatabaseError):
    """Raised when the database is misconfigured or cannot be initialized."""