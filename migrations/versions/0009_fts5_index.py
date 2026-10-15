"""Add FTS5 virtual tables for full-text search.

Revision ID: 0009_fts5_index
Revises: 0008_knowledge_guides_achievements_plans
Create Date: 2024-01-15

This revision introduces the FTS5 virtual tables that back local
full-text search:

- ``document_fts`` — indexed document chunk content and metadata.
- ``publication_fts`` — indexed publication metadata and abstracts.
- ``note_fts`` — indexed annotation notes and excerpts.

FTS5 tables are virtual tables. They are created and dropped with
``CREATE VIRTUAL TABLE`` and ``DROP TABLE``. The migration is fully
reversible.
"""

from __future__ import annotations

from alembic import op

from academic_platform.infrastructure.database.models.fts import (
    FTS_DOCUMENTS_COLUMNS,
    FTS_DOCUMENTS_TABLE,
    FTS_NOTES_COLUMNS,
    FTS_NOTES_TABLE,
    FTS_PUBLICATIONS_COLUMNS,
    FTS_PUBLICATIONS_TABLE,
)

revision: str = "0009_fts5_index"
down_revision: str | None = "0008_knowledge_guides_achievements_plans"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    connection = op.get_bind()
    for table_name, columns in (
        (FTS_DOCUMENTS_TABLE, FTS_DOCUMENTS_COLUMNS),
        (FTS_PUBLICATIONS_TABLE, FTS_PUBLICATIONS_COLUMNS),
        (FTS_NOTES_TABLE, FTS_NOTES_COLUMNS),
    ):
        column_definitions = ", ".join(f'"{column}"' for column in columns)
        connection.exec_driver_sql(
            f'CREATE VIRTUAL TABLE IF NOT EXISTS "{table_name}" '
            f"USING fts5({column_definitions});"
        )


def downgrade() -> None:
    connection = op.get_bind()
    for table_name in (
        FTS_NOTES_TABLE,
        FTS_PUBLICATIONS_TABLE,
        FTS_DOCUMENTS_TABLE,
    ):
        connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table_name}";')