"""Infrastructure adapters.

The infrastructure layer contains concrete implementations of the ports the
application and domain layers depend on. Adapters here may import from
third-party libraries (SQLAlchemy, httpx, PyMuPDF, statsmodels, and so on);
the domain and application layers must not.

This package is the only place in the codebase where database engines,
sessions, and migrations are constructed. The presentation layer never
imports from this package.
"""

from academic_platform.infrastructure.database import (
    Database,
    DatabaseConfiguration,
    DatabaseConfigurationError,
    DatabaseError,
)

__all__ = [
    "Database",
    "DatabaseConfiguration",
    "DatabaseConfigurationError",
    "DatabaseError",
]