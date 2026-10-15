"""Database engine, session management, and migrations.

This subpackage owns the SQLAlchemy engine, the session factory, the
transactional context manager, and the Alembic migration runner used
throughout the application.
"""

from academic_platform.infrastructure.database.config import DatabaseConfiguration
from academic_platform.infrastructure.database.engine import Database
from academic_platform.infrastructure.database.errors import (
    DatabaseConfigurationError,
    DatabaseError,
)
from academic_platform.infrastructure.database.migrations import (
    DatabaseMigrationError,
    MigrationResult,
    current_revision,
    declared_head_revision,
    downgrade,
    head_revision,
    upgrade_to_head,
)

__all__ = [
    "Database",
    "DatabaseConfiguration",
    "DatabaseConfigurationError",
    "DatabaseError",
    "DatabaseMigrationError",
    "MigrationResult",
    "current_revision",
    "declared_head_revision",
    "downgrade",
    "head_revision",
    "upgrade_to_head",
]
