"""FTS5 virtual table definitions.

FTS5 tables are declared with SQLAlchemy's ``Table`` construct using
``sqlite_virtual_table``. They are not part of the ORM's declarative
model because FTS5 tables do not have a primary key in the usual sense
and are not mapped to ORM classes.

The virtual tables are declared here so that Alembic's autogenerate can
see them and so that a single module owns the FTS5 schema. The indexer
and query service read the table names and column names from this
module rather than duplicating string literals.
"""

from __future__ import annotations

from sqlalchemy import Column, Index, MetaData, String, Table, text
from sqlalchemy.dialects.sqlite import TEXT as SQLITE_TEXT

from academic_platform.infrastructure.database.base import Base

#: Name of the FTS5 virtual table holding indexed document content.
FTS_DOCUMENTS_TABLE = "document_fts"

#: Column names of the FTS5 virtual table. The order matters because
#: FTS5 stores the column list in the table definition.
FTS_DOCUMENTS_COLUMNS = (
    "document_key",
    "chunk_index",
    "page_number",
    "title",
    "authors",
    "content",
)

#: Name of the FTS5 virtual table holding indexed publication content.
FTS_PUBLICATIONS_TABLE = "publication_fts"

#: Column names of the publications FTS5 virtual table.
FTS_PUBLICATIONS_COLUMNS = (
    "publication_key",
    "title",
    "authors",
    "abstract",
    "venue",
)

#: Name of the FTS5 virtual table holding indexed note and annotation
#: content.
FTS_NOTES_TABLE = "note_fts"

#: Column names of the notes FTS5 virtual table.
FTS_NOTES_COLUMNS = (
    "document_key",
    "annotation_id",
    "page_number",
    "content",
)


def create_fts_tables(connection) -> None:
    """Create every FTS5 virtual table on the given connection.

    The function is idempotent: each table is created only when it does
    not already exist. The function is invoked by Alembic migrations and
    by tests that construct a schema directly.

    Parameters
    ----------
    connection:
        A SQLAlchemy connection or a raw DBAPI connection. The function
        accepts either by executing through ``exec_driver_sql`` when a
        SQLAlchemy connection is provided.
    """
    for table_name, columns in (
        (FTS_DOCUMENTS_TABLE, FTS_DOCUMENTS_COLUMNS),
        (FTS_PUBLICATIONS_TABLE, FTS_PUBLICATIONS_COLUMNS),
        (FTS_NOTES_TABLE, FTS_NOTES_COLUMNS),
    ):
        column_definitions = ", ".join(f'"{column}"' for column in columns)
        statement = (
            f'CREATE VIRTUAL TABLE IF NOT EXISTS "{table_name}" '
            f"USING fts5({column_definitions});"
        )
        if hasattr(connection, "exec_driver_sql"):
            connection.exec_driver_sql(statement)
        else:
            connection.execute(statement)


def drop_fts_tables(connection) -> None:
    """Drop every FTS5 virtual table on the given connection.

    The function is idempotent and is used by migrations that revert the
    FTS5 schema.
    """
    for table_name in (
        FTS_NOTES_TABLE,
        FTS_PUBLICATIONS_TABLE,
        FTS_DOCUMENTS_TABLE,
    ):
        statement = f'DROP TABLE IF EXISTS "{table_name}";'
        if hasattr(connection, "exec_driver_sql"):
            connection.exec_driver_sql(statement)
        else:
            connection.execute(statement)