"""Add ai_provider, ai_model, ai_task_routing, and ai_invocation tables.

Revision ID: 0006_ai_providers_and_models
Revises: 0005_search_and_publications
Create Date: 2024-01-15

This revision introduces the four tables that support the AI subsystem:

- ``ai_provider`` — a configured AI provider (local or remote).
- ``ai_model`` — a model exposed by a provider.
- ``ai_task_routing`` — mapping from task to provider and model.
- ``ai_invocation`` — an append-only log of provider invocations.

The migration is fully reversible. Downgrading drops the four tables and
their indexes in reverse dependency order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ai_providers_and_models"
down_revision: str | None = "0005_search_and_publications"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_provider",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("endpoint_url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("model_file_path", sa.String(length=2048), nullable=True),
        sa.Column("auth_type", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("credential_reference", sa.String(length=128), nullable=True),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column(
            "request_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "health_state",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("last_tested_at", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "default_for_tasks_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("runtime_info_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_ai_provider_key"),
        sa.CheckConstraint(
            "provider_kind IN ('local_gguf','openai_compatible','anthropic','other')",
            name="ck_ai_provider_provider_kind_valid",
        ),
        sa.CheckConstraint(
            "auth_type IN ('none','api_key','bearer_token')",
            name="ck_ai_provider_auth_type_valid",
        ),
        sa.CheckConstraint(
            "health_state IN ('unknown','ok','failed','disabled')",
            name="ck_ai_provider_health_state_valid",
        ),
    )
    op.create_index("ix_ai_provider_key", "ai_provider", ["key"])
    op.create_index("ix_ai_provider_enabled", "ai_provider", ["enabled"])
    op.create_index("ix_ai_provider_kind", "ai_provider", ["provider_kind"])

    op.create_table(
        "ai_model",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_provider.id",
                ondelete="CASCADE",
                name="fk_ai_model_provider_id_ai_provider",
            ),
            nullable=False,
        ),
        sa.Column("model_identifier", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("capabilities_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "health_state",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("last_tested_at", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "default_for_tasks_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "provider_id",
            "model_identifier",
            name="uq_ai_model_provider_identifier",
        ),
        sa.CheckConstraint(
            "health_state IN ('unknown','ok','failed','disabled')",
            name="ck_ai_model_health_state_valid",
        ),
    )
    op.create_index(
        "ix_ai_model_provider_enabled", "ai_model", ["provider_id", "enabled"]
    )

    op.create_table(
        "ai_task_routing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_key", sa.String(length=64), nullable=False),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_provider.id",
                ondelete="SET NULL",
                name="fk_ai_task_routing_provider_id_ai_provider",
            ),
            nullable=True,
        ),
        sa.Column(
            "model_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_model.id",
                ondelete="SET NULL",
                name="fk_ai_task_routing_model_id_ai_model",
            ),
            nullable=True,
        ),
        sa.Column(
            "fallback_provider_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_provider.id",
                ondelete="SET NULL",
                name="fk_ai_task_routing_fallback_provider_id_ai_provider",
            ),
            nullable=True,
        ),
        sa.Column(
            "fallback_model_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_model.id",
                ondelete="SET NULL",
                name="fk_ai_task_routing_fallback_model_id_ai_model",
            ),
            nullable=True,
        ),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("parameters_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("task_key", name="uq_ai_task_routing_task_key"),
    )
    op.create_index("ix_ai_task_routing_task_key", "ai_task_routing", ["task_key"])

    op.create_table(
        "ai_invocation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_key", sa.String(length=64), nullable=False),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_provider.id",
                ondelete="SET NULL",
                name="fk_ai_invocation_provider_id_ai_provider",
            ),
            nullable=True,
        ),
        sa.Column(
            "model_id",
            sa.Integer(),
            sa.ForeignKey(
                "ai_model.id",
                ondelete="SET NULL",
                name="fk_ai_invocation_model_id_ai_model",
            ),
            nullable=True,
        ),
        sa.Column(
            "provider_key_snapshot",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "model_identifier_snapshot",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "prompt_template_version",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_size_bytes", sa.Integer(), nullable=True),
        sa.Column("output_size_bytes", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('ok','failed','cancelled')",
            name="ck_ai_invocation_status_valid",
        ),
    )
    op.create_index("ix_ai_invocation_started_at", "ai_invocation", ["started_at"])
    op.create_index(
        "ix_ai_invocation_task_started", "ai_invocation", ["task_key", "started_at"]
    )
    op.create_index(
        "ix_ai_invocation_provider_started",
        "ai_invocation",
        ["provider_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_invocation_provider_started", table_name="ai_invocation")
    op.drop_index("ix_ai_invocation_task_started", table_name="ai_invocation")
    op.drop_index("ix_ai_invocation_started_at", table_name="ai_invocation")
    op.drop_table("ai_invocation")

    op.drop_index("ix_ai_task_routing_task_key", table_name="ai_task_routing")
    op.drop_table("ai_task_routing")

    op.drop_index("ix_ai_model_provider_enabled", table_name="ai_model")
    op.drop_table("ai_model")

    op.drop_index("ix_ai_provider_kind", table_name="ai_provider")
    op.drop_index("ix_ai_provider_enabled", table_name="ai_provider")
    op.drop_index("ix_ai_provider_key", table_name="ai_provider")
    op.drop_table("ai_provider")