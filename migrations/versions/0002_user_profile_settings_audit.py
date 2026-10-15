"""Add user_profile, app_settings, and audit_event tables.

Revision ID: 0002_user_profile_settings_audit
Revises: 0001_baseline
Create Date: 2024-01-15

This revision introduces the first application tables:

- ``user_profile`` — one row per user profile.
- ``app_settings`` — a singleton row holding installation-level values.
- ``audit_event`` — an append-only audit trail.

The migration is fully reversible. Downgrading drops the three tables and
the indexes defined in this revision.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_profile_settings_audit"
down_revision: str | None = "0001_baseline"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the three tables."""
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("preferred_language", sa.String(length=16), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=4096), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_user_profile_key"),
    )
    op.create_index("ix_user_profile_key", "user_profile", ["key"], unique=False)

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("active_user_key", sa.String(length=64), nullable=True),
        sa.Column(
            "settings_schema_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_app_settings_single_row"),
    )

    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_identifier", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_event_occurred_at", "audit_event", ["occurred_at"])
    op.create_index(
        "ix_audit_event_actor_occurred_at",
        "audit_event",
        ["actor", "occurred_at"],
    )


def downgrade() -> None:
    """Drop the three tables."""
    op.drop_index("ix_audit_event_actor_occurred_at", table_name="audit_event")
    op.drop_index("ix_audit_event_occurred_at", table_name="audit_event")
    op.drop_table("audit_event")

    op.drop_table("app_settings")

    op.drop_index("ix_user_profile_key", table_name="user_profile")
    op.drop_table("user_profile")