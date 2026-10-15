"""Add publication, search_source, saved_search_query, search_session, and search_result tables.

Revision ID: 0005_search_and_publications
Revises: 0004_document_assets
Create Date: 2024-01-15

This revision introduces the five tables that support academic search:

- ``publication`` — a normalized scholarly work.
- ``search_source`` — a configurable academic search provider.
- ``saved_search_query`` — a reusable search definition.
- ``search_session`` — a single execution of a search.
- ``search_result`` — a result returned by a search session.

The migration is fully reversible. Downgrading drops the five tables and
their indexes in reverse dependency order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005_search_and_publications"
down_revision: str | None = "0004_document_assets"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "publication",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("authors_json", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.String(length=512), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("is_open_access", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column(
            "source_providers_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_publication_key"),
        sa.UniqueConstraint("doi", name="uq_publication_doi"),
    )
    op.create_index("ix_publication_key", "publication", ["key"])
    op.create_index("ix_publication_year", "publication", ["year"])
    op.create_index("ix_publication_title", "publication", ["title"])

    op.create_table(
        "search_source",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("http_method", sa.String(length=16), nullable=False, server_default="GET"),
        sa.Column("parameter_map_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("capabilities_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("rate_limit_json", sa.Text(), nullable=True),
        sa.Column("auth_type", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("credential_reference", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("result_limit", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("last_tested_at", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_search_source_key"),
        sa.UniqueConstraint("provider_key", name="uq_search_source_provider_key"),
        sa.CheckConstraint(
            "source_type IN ('builtin','user_defined')",
            name="ck_search_source_source_type_valid",
        ),
        sa.CheckConstraint(
            "auth_type IN ('none','api_key','bearer_token')",
            name="ck_search_source_auth_type_valid",
        ),
    )
    op.create_index("ix_search_source_key", "search_source", ["key"])
    op.create_index("ix_search_source_enabled", "search_source", ["enabled"])

    op.create_table(
        "saved_search_query",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("query_text", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="all"),
        sa.Column("filter_json", sa.Text(), nullable=True),
        sa.Column("source_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("last_executed_at", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_saved_search_query_key"),
        sa.CheckConstraint(
            "scope IN ('all','local','remote')",
            name="ck_saved_search_query_scope_valid",
        ),
    )
    op.create_index("ix_saved_search_query_key", "saved_search_query", ["key"])
    op.create_index("ix_saved_search_query_scope", "saved_search_query", ["scope"])

    op.create_table(
        "search_session",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "query_id",
            sa.Integer(),
            sa.ForeignKey(
                "saved_search_query.id",
                ondelete="SET NULL",
                name="fk_search_session_query_id_saved_search_query",
            ),
            nullable=True,
        ),
        sa.Column("query_text", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="all"),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
        sa.Column("source_reports_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("partial", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "scope IN ('all','local','remote')",
            name="ck_search_session_scope_valid",
        ),
    )
    op.create_index(
        "ix_search_session_executed_at", "search_session", ["executed_at"]
    )
    op.create_index(
        "ix_search_session_query_key", "search_session", ["query_id"]
    )

    op.create_table(
        "search_result",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey(
                "search_session.id",
                ondelete="CASCADE",
                name="fk_search_result_session_id_search_session",
            ),
            nullable=False,
        ),
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey(
                "publication.id",
                ondelete="CASCADE",
                name="fk_search_result_publication_id_publication",
            ),
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "publication_id",
            name="uq_search_result_session_publication",
        ),
    )
    op.create_index(
        "ix_search_result_session_rank", "search_result", ["session_id", "rank"]
    )


def downgrade() -> None:
    op.drop_index("ix_search_result_session_rank", table_name="search_result")
    op.drop_table("search_result")

    op.drop_index("ix_search_session_query_key", table_name="search_session")
    op.drop_index("ix_search_session_executed_at", table_name="search_session")
    op.drop_table("search_session")

    op.drop_index("ix_saved_search_query_scope", table_name="saved_search_query")
    op.drop_index("ix_saved_search_query_key", table_name="saved_search_query")
    op.drop_table("saved_search_query")

    op.drop_index("ix_search_source_enabled", table_name="search_source")
    op.drop_index("ix_search_source_key", table_name="search_source")
    op.drop_table("search_source")

    op.drop_index("ix_publication_title", table_name="publication")
    op.drop_index("ix_publication_year", table_name="publication")
    op.drop_index("ix_publication_key", table_name="publication")
    op.drop_table("publication")