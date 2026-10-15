"""Add document_asset, document_metadata, document_chunk, and annotation tables.

Revision ID: 0004_document_assets
Revises: 0003_projects_and_collections
Create Date: 2024-01-15

This revision introduces the four tables that support the personal
library:

- ``document_asset`` — a physical file the user imported or referenced.
- ``document_metadata`` — extracted metadata for a document.
- ``document_chunk`` — extracted text chunks for local search and reading.
- ``annotation`` — user-authored notes, highlights, and bookmarks.

The migration is fully reversible. Downgrading drops the four tables and
their indexes in reverse dependency order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004_document_assets"
down_revision: str | None = "0003_projects_and_collections"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "document_asset",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("original_filename", sa.String(length=512), nullable=False, server_default=""),
        sa.Column(
            "storage_mode",
            sa.String(length=32),
            nullable=False,
            server_default="managed_copy",
        ),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "processing_state",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("processing_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "ocr_state",
            sa.String(length=32),
            nullable=False,
            server_default="not_required",
        ),
        sa.Column(
            "indexing_state",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("missing", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_document_asset_key"),
        sa.CheckConstraint(
            "storage_mode IN ('managed_copy','referenced_file')",
            name="ck_document_asset_storage_mode_valid",
        ),
        sa.CheckConstraint(
            "processing_state IN ('pending','extracting','extracted','indexed','failed')",
            name="ck_document_asset_processing_state_valid",
        ),
        sa.CheckConstraint(
            "ocr_state IN ('not_required','pending','completed','failed')",
            name="ck_document_asset_ocr_state_valid",
        ),
    )
    op.create_index("ix_document_asset_key", "document_asset", ["key"])
    op.create_index(
        "ix_document_asset_checksum", "document_asset", ["checksum_sha256"]
    )
    op.create_index(
        "ix_document_asset_processing_state",
        "document_asset",
        ["processing_state"],
    )

    op.create_table(
        "document_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey(
                "document_asset.id",
                ondelete="CASCADE",
                name="fk_document_metadata_document_id_document_asset",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("authors_json", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.String(length=512), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column(
            "extraction_method",
            sa.String(length=64),
            nullable=False,
            server_default="pdf_heuristic",
        ),
        sa.Column("reviewed_by_user", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", name="uq_document_metadata_document_id"),
        sa.CheckConstraint(
            "extraction_confidence IS NULL OR "
            "(extraction_confidence >= 0.0 AND extraction_confidence <= 1.0)",
            name="ck_document_metadata_extraction_confidence_range",
        ),
    )

    op.create_table(
        "document_chunk",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey(
                "document_asset.id",
                ondelete="CASCADE",
                name="fk_document_chunk_document_id_document_asset",
            ),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_document_chunk_document_index",
        "document_chunk",
        ["document_id", "chunk_index"],
    )
    op.create_index(
        "ix_document_chunk_document_page",
        "document_chunk",
        ["document_id", "page_number"],
    )

    op.create_table(
        "annotation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey(
                "document_asset.id",
                ondelete="CASCADE",
                name="fk_annotation_document_id_document_asset",
            ),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text_excerpt", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("anchor", sa.String(length=255), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "kind IN ('note','highlight','bookmark')",
            name="ck_annotation_kind_valid",
        ),
        sa.CheckConstraint(
            "color IS NULL OR color IN ('yellow','green','blue','pink')",
            name="ck_annotation_color_valid",
        ),
    )
    op.create_index(
        "ix_annotation_document_page",
        "annotation",
        ["document_id", "page_number"],
    )
    op.create_index(
        "ix_annotation_document_kind",
        "annotation",
        ["document_id", "kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_annotation_document_kind", table_name="annotation")
    op.drop_index("ix_annotation_document_page", table_name="annotation")
    op.drop_table("annotation")

    op.drop_index("ix_document_chunk_document_page", table_name="document_chunk")
    op.drop_index("ix_document_chunk_document_index", table_name="document_chunk")
    op.drop_table("document_chunk")

    op.drop_table("document_metadata")

    op.drop_index(
        "ix_document_asset_processing_state", table_name="document_asset"
    )
    op.drop_index("ix_document_asset_checksum", table_name="document_asset")
    op.drop_index("ix_document_asset_key", table_name="document_asset")
    op.drop_table("document_asset")