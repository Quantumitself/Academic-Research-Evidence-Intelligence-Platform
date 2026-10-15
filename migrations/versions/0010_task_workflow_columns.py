"""Add workflow columns to research_task.

Revision ID: 0010_task_workflow_columns
Revises: 0009_fts5_index
Create Date: 2024-01-15

This revision extends the ``research_task`` table with the columns the
task workflow service relies on:

- ``status`` — workflow status.
- ``priority`` — priority level.
- ``is_milestone`` — milestone marker.
- ``notes`` — free-form notes.
- ``completed_at`` — completion timestamp.

The migration is fully reversible. Downgrading drops the columns and
the indexes introduced by this revision.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0010_task_workflow_columns"
down_revision: str | None = "0009_fts5_index"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "research_task",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="open",
        ),
    )
    op.add_column(
        "research_task",
        sa.Column(
            "priority",
            sa.String(length=16),
            nullable=False,
            server_default="normal",
        ),
    )
    op.add_column(
        "research_task",
        sa.Column(
            "is_milestone",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "research_task",
        sa.Column(
            "notes",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "research_task",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_research_task_status", "research_task", ["status"]
    )
    op.create_index(
        "ix_research_task_is_milestone", "research_task", ["is_milestone"]
    )

    # Backfill the status column from the legacy ``completed`` flag so
    # that existing rows reflect their actual state.
    op.execute(
        "UPDATE research_task SET status = 'done' WHERE completed = 1"
    )
    op.execute(
        "UPDATE research_task SET status = 'open' WHERE completed = 0"
    )


def downgrade() -> None:
    op.drop_index("ix_research_task_is_milestone", table_name="research_task")
    op.drop_index("ix_research_task_status", table_name="research_task")
    op.drop_column("research_task", "completed_at")
    op.drop_column("research_task", "notes")
    op.drop_column("research_task", "is_milestone")
    op.drop_column("research_task", "priority")
    op.drop_column("research_task", "status")