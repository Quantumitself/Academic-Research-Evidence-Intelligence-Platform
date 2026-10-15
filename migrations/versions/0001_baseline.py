"""Baseline revision.

Revision ID: 0001_baseline
Revises:
Create Date: 2024-01-15

This revision establishes the Alembic version table and marks the baseline
state of the schema. It creates no application tables. Subsequent phases
add tables through new revisions whose ``down_revision`` refers to this
baseline.

The downgrade is a no-op: reverting the baseline leaves the database in
the same state it was before the baseline was applied, which is an empty
database that has never been migrated.
"""

from __future__ import annotations

from alembic import op  # noqa: F401  # imported for uniformity across revisions

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Apply the baseline.

    The baseline intentionally performs no schema changes. Its purpose is
    to record the initial revision identifier so that later revisions have
    a stable parent.
    """


def downgrade() -> None:
    """Revert the baseline.

    Reverting the baseline performs no schema changes for the same reason
    as the upgrade.
    """