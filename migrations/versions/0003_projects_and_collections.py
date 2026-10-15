"""Add research_project, research_question, collection, and collection_item tables.

Revision ID: 0003_projects_and_collections
Revises: 0002_user_profile_settings_audit
Create Date: 2024-01-15

This revision introduces the four tables that support research projects
and collections:

- ``research_project`` — a project under development.
- ``research_question`` — a question belonging to a project.
- ``collection`` — a grouping of research materials.
- ``collection_item`` — an association between a collection and a resource.

The migration is fully reversible. Downgrading drops the four tables and
their indexes in reverse dependency order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_projects_and_collections"
down_revision: str | None = "0002_user_profile_settings_audit"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "research_project",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("topic", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="idea"),
        sa.Column("project_metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_research_project_key"),
        sa.CheckConstraint(
            "stage IN ('idea','design','collection','analysis','writing','complete','archived')",
            name="ck_research_project_stage_valid",
        ),
    )
    op.create_index("ix_research_project_key", "research_project", ["key"])
    op.create_index("ix_research_project_stage", "research_project", ["stage"])
    op.create_index("ix_research_project_updated_at", "research_project", ["updated_at"])

    op.create_table(
        "research_question",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_research_question_project_id_research_project",
            ),
            nullable=False,
        ),
        sa.Column("text", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="main"),
        sa.Column("is_primary", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "kind IN ('main','sub','exploratory','hypothesis')",
            name="ck_research_question_kind_valid",
        ),
    )
    op.create_index(
        "ix_research_question_project_position",
        "research_question",
        ["project_id", "position"],
    )

    op.create_table(
        "collection",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=4096), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_collection_project_id_research_project",
            ),
            nullable=True,
        ),
        sa.Column("filter_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_collection_key"),
        sa.CheckConstraint(
            "kind IN ('manual','topic','project','saved_search','smart')",
            name="ck_collection_kind_valid",
        ),
        sa.CheckConstraint(
            "(kind = 'project' AND project_id IS NOT NULL) OR "
            "(kind <> 'project' AND project_id IS NULL)",
            name="ck_collection_project_link_valid",
        ),
    )
    op.create_index("ix_collection_key", "collection", ["key"])
    op.create_index("ix_collection_kind", "collection", ["kind"])
    op.create_index("ix_collection_project_id", "collection", ["project_id"])

    op.create_table(
        "collection_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey(
                "collection.id",
                ondelete="CASCADE",
                name="fk_collection_item_collection_id_collection",
            ),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("item_identifier", sa.String(length=128), nullable=False),
        sa.Column("note", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "collection_id",
            "item_type",
            "item_identifier",
            name="uq_collection_item_target",
        ),
        sa.CheckConstraint(
            "item_type IN ('publication','document','evidence','note')",
            name="ck_collection_item_item_type_valid",
        ),
    )
    op.create_index(
        "ix_collection_item_collection_position",
        "collection_item",
        ["collection_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_item_collection_position", table_name="collection_item")
    op.drop_table("collection_item")

    op.drop_index("ix_collection_project_id", table_name="collection")
    op.drop_index("ix_collection_kind", table_name="collection")
    op.drop_index("ix_collection_key", table_name="collection")
    op.drop_table("collection")

    op.drop_index(
        "ix_research_question_project_position",
        table_name="research_question",
    )
    op.drop_table("research_question")

    op.drop_index("ix_research_project_updated_at", table_name="research_project")
    op.drop_index("ix_research_project_stage", table_name="research_project")
    op.drop_index("ix_research_project_key", table_name="research_project")
    op.drop_table("research_project")