"""Add evidence, extraction run, analysis run, input, and synthesis report tables.

Revision ID: 0007_evidence_and_analysis
Revises: 0006_ai_providers_and_models
Create Date: 2024-01-15

This revision introduces the six tables that support the evidence and
analysis subsystem:

- ``evidence_extraction_run`` — a single execution of the extraction
  pipeline over a document.
- ``evidence_record`` — a structured fact extracted from a document.
- ``analysis_run`` — a single execution of the statistical engine.
- ``analysis_input`` — an input value consumed by an analysis run.
- ``synthesis_report`` — a source-linked synthesis report.

The migration is fully reversible. Downgrading drops the tables in
reverse dependency order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007_evidence_and_analysis"
down_revision: str | None = "0006_ai_providers_and_models"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_extraction_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey(
                "document_asset.id",
                ondelete="CASCADE",
                name="fk_evidence_extraction_run_document_id_document_asset",
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("pipeline_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("ai_provider_snapshot", sa.String(length=64), nullable=True),
        sa.Column("ai_model_snapshot", sa.String(length=255), nullable=True),
        sa.Column("parameters_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','cancelled')",
            name="ck_evidence_extraction_run_status_valid",
        ),
        sa.CheckConstraint(
            "method IN ('rule_based','ai_assisted','hybrid')",
            name="ck_evidence_extraction_run_method_valid",
        ),
    )
    op.create_index(
        "ix_evidence_extraction_run_document",
        "evidence_extraction_run",
        ["document_id"],
    )
    op.create_index(
        "ix_evidence_extraction_run_started_at",
        "evidence_extraction_run",
        ["started_at"],
    )

    op.create_table(
        "evidence_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey(
                "document_asset.id",
                ondelete="CASCADE",
                name="fk_evidence_record_document_id_document_asset",
            ),
            nullable=False,
        ),
        sa.Column(
            "extraction_run_id",
            sa.Integer(),
            sa.ForeignKey(
                "evidence_extraction_run.id",
                ondelete="SET NULL",
                name="fk_evidence_record_extraction_run_id_evidence_extraction_run",
            ),
            nullable=True,
        ),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("reported_value_json", sa.Text(), nullable=True),
        sa.Column("normalized_value_json", sa.Text(), nullable=True),
        sa.Column("units", sa.String(length=64), nullable=True),
        sa.Column("raw_source_text", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=512), nullable=True),
        sa.Column("table_reference", sa.String(length=64), nullable=True),
        sa.Column("figure_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "extraction_method",
            sa.String(length=32),
            nullable=False,
            server_default="rule_based",
        ),
        sa.Column(
            "verification_status",
            sa.String(length=32),
            nullable=False,
            server_default="ai_proposed",
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_correction_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "evidence_type IN ("
            "'study_design','population','sample_size','measurement',"
            "'group_statistic','effect_estimate','p_value','confidence_interval',"
            "'covariate','limitation','outcome_definition','other')",
            name="ck_evidence_record_evidence_type_valid",
        ),
        sa.CheckConstraint(
            "verification_status IN ("
            "'ai_proposed','auto_parsed','user_verified','uncertain',"
            "'rejected','missing')",
            name="ck_evidence_record_verification_status_valid",
        ),
        sa.CheckConstraint(
            "extraction_method IN ('rule_based','ai_assisted','user_entered')",
            name="ck_evidence_record_extraction_method_valid",
        ),
    )
    op.create_index("ix_evidence_record_document", "evidence_record", ["document_id"])
    op.create_index(
        "ix_evidence_record_document_type",
        "evidence_record",
        ["document_id", "evidence_type"],
    )
    op.create_index(
        "ix_evidence_record_verification",
        "evidence_record",
        ["verification_status"],
    )
    op.create_index(
        "ix_evidence_record_run", "evidence_record", ["extraction_run_id"]
    )

    op.create_table(
        "analysis_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("engine_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("library_versions_json", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("warnings_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("inputs_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','cancelled')",
            name="ck_analysis_run_status_valid",
        ),
        sa.CheckConstraint(
            "analysis_type IN ("
            "'descriptive','t_test','correlation','regression',"
            "'effect_size','meta_analysis','reliability','other')",
            name="ck_analysis_run_analysis_type_valid",
        ),
    )
    op.create_index(
        "ix_analysis_run_analysis_type", "analysis_run", ["analysis_type"]
    )
    op.create_index("ix_analysis_run_started_at", "analysis_run", ["started_at"])

    op.create_table(
        "analysis_input",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "analysis_run_id",
            sa.Integer(),
            sa.ForeignKey(
                "analysis_run.id",
                ondelete="CASCADE",
                name="fk_analysis_input_analysis_run_id_analysis_run",
            ),
            nullable=False,
        ),
        sa.Column("input_key", sa.String(length=128), nullable=False),
        sa.Column("value_kind", sa.String(length=32), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column(
            "source_evidence_id",
            sa.Integer(),
            sa.ForeignKey(
                "evidence_record.id",
                ondelete="SET NULL",
                name="fk_analysis_input_source_evidence_id_evidence_record",
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_analysis_input_run", "analysis_input", ["analysis_run_id"])

    op.create_table(
        "synthesis_report",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey(
                "collection.id",
                ondelete="CASCADE",
                name="fk_synthesis_report_collection_id_collection",
            ),
            nullable=True,
        ),
        sa.Column("report_kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("narrative", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "contributing_run_ids_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "included_evidence_ids_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "excluded_evidence_ids_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("exclusion_reasons_json", sa.Text(), nullable=True),
        sa.Column("limitations_json", sa.Text(), nullable=True),
        sa.Column("reproducibility_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "report_kind IN ('narrative','meta_analysis','mixed')",
            name="ck_synthesis_report_report_kind_valid",
        ),
    )
    op.create_index(
        "ix_synthesis_report_collection", "synthesis_report", ["collection_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_synthesis_report_collection", table_name="synthesis_report")
    op.drop_table("synthesis_report")

    op.drop_index("ix_analysis_input_run", table_name="analysis_input")
    op.drop_table("analysis_input")

    op.drop_index("ix_analysis_run_started_at", table_name="analysis_run")
    op.drop_index("ix_analysis_run_analysis_type", table_name="analysis_run")
    op.drop_table("analysis_run")

    op.drop_index("ix_evidence_record_run", table_name="evidence_record")
    op.drop_index("ix_evidence_record_verification", table_name="evidence_record")
    op.drop_index("ix_evidence_record_document_type", table_name="evidence_record")
    op.drop_index("ix_evidence_record_document", table_name="evidence_record")
    op.drop_table("evidence_record")

    op.drop_index(
        "ix_evidence_extraction_run_started_at", table_name="evidence_extraction_run"
    )
    op.drop_index(
        "ix_evidence_extraction_run_document", table_name="evidence_extraction_run"
    )
    op.drop_table("evidence_extraction_run")