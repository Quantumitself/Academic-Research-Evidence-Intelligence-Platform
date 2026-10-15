"""Add knowledge, guide, achievement, and research-plan tables.

Revision ID: 0008_knowledge_guides_achievements_plans
Revises: 0007_evidence_and_analysis
Create Date: 2024-01-15

This revision introduces the tables that support the knowledge map, the
research guides, the achievement system, the user activity feed, and the
research plan output of the Research Design Assistant:

- ``knowledge_node`` and ``knowledge_relationship`` — the knowledge map.
- ``research_guide``, ``research_guide_section``, and ``citation_record``
  — the guide subsystem.
- ``achievement``, ``achievement_unlock``, and ``user_activity`` — the
  gamification and activity subsystem.
- ``research_plan``, ``research_task``, ``research_title_candidate``,
  ``methodology_proposal``, and ``analysis_recommendation`` — the
  research-plan subsystem.

The migration is fully reversible. Downgrading drops the tables in
reverse dependency order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008_knowledge_guides_achievements_plans"
down_revision: str | None = "0007_evidence_and_analysis"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_node",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("node_kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_knowledge_node_key"),
        sa.CheckConstraint(
            "node_kind IN ('topic','concept','theory','author','publication',"
            "'research_question','variable','instrument','project','collection')",
            name="ck_knowledge_node_node_kind_valid",
        ),
    )
    op.create_index("ix_knowledge_node_key", "knowledge_node", ["key"])
    op.create_index("ix_knowledge_node_kind", "knowledge_node", ["node_kind"])

    op.create_table(
        "knowledge_relationship",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_node_id",
            sa.Integer(),
            sa.ForeignKey(
                "knowledge_node.id",
                ondelete="CASCADE",
                name="fk_knowledge_relationship_source_node_id_knowledge_node",
            ),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            sa.Integer(),
            sa.ForeignKey(
                "knowledge_node.id",
                ondelete="CASCADE",
                name="fk_knowledge_relationship_target_node_id_knowledge_node",
            ),
            nullable=False,
        ),
        sa.Column("relationship_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "grounding",
            sa.String(length=32),
            nullable=False,
            server_default="metadata",
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_node_id",
            "target_node_id",
            "relationship_kind",
            name="uq_knowledge_relationship_edge",
        ),
        sa.CheckConstraint(
            "relationship_kind IN ("
            "'studies','extends','challenges','uses','measures',"
            "'cites','relates_to','contradicts','belongs_to')",
            name="ck_knowledge_relationship_relationship_kind_valid",
        ),
        sa.CheckConstraint(
            "grounding IN ('metadata','user_link','ai_proposed')",
            name="ck_knowledge_relationship_grounding_valid",
        ),
    )
    op.create_index(
        "ix_knowledge_relationship_source",
        "knowledge_relationship",
        ["source_node_id"],
    )
    op.create_index(
        "ix_knowledge_relationship_target",
        "knowledge_relationship",
        ["target_node_id"],
    )

    op.create_table(
        "research_guide",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("guide_kind", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="SET NULL",
                name="fk_research_guide_project_id_research_project",
            ),
            nullable=True,
        ),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey(
                "collection.id",
                ondelete="SET NULL",
                name="fk_research_guide_collection_id_collection",
            ),
            nullable=True,
        ),
        sa.Column("overview", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "generated_by",
            sa.String(length=32),
            nullable=False,
            server_default="user",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_research_guide_key"),
        sa.CheckConstraint(
            "guide_kind IN ('topic','project','collection','papers')",
            name="ck_research_guide_guide_kind_valid",
        ),
    )
    op.create_index("ix_research_guide_key", "research_guide", ["key"])
    op.create_index(
        "ix_research_guide_owner_project", "research_guide", ["project_id"]
    )
    op.create_index(
        "ix_research_guide_owner_collection", "research_guide", ["collection_id"]
    )

    op.create_table(
        "research_guide_section",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guide_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_guide.id",
                ondelete="CASCADE",
                name="fk_research_guide_section_guide_id_research_guide",
            ),
            nullable=False,
        ),
        sa.Column("heading", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_source_derived", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_research_guide_section_guide_position",
        "research_guide_section",
        ["guide_id", "position"],
    )

    op.create_table(
        "citation_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "section_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_guide_section.id",
                ondelete="CASCADE",
                name="fk_citation_record_section_id_research_guide_section",
            ),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_identifier", sa.String(length=255), nullable=False),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('publication','document','evidence','external')",
            name="ck_citation_record_source_type_valid",
        ),
    )
    op.create_index("ix_citation_record_section", "citation_record", ["section_id"])
    op.create_index(
        "ix_citation_record_source",
        "citation_record",
        ["source_type", "source_identifier"],
    )

    op.create_table(
        "achievement",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "category", sa.String(length=32), nullable=False, server_default="general"
        ),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("key", name="uq_achievement_key"),
    )
    op.create_index("ix_achievement_key", "achievement", ["key"])
    op.create_index("ix_achievement_category", "achievement", ["category"])

    op.create_table(
        "achievement_unlock",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "achievement_id",
            sa.Integer(),
            sa.ForeignKey(
                "achievement.id",
                ondelete="CASCADE",
                name="fk_achievement_unlock_achievement_id_achievement",
            ),
            nullable=False,
        ),
        sa.Column("user_key", sa.String(length=64), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), nullable=False),
        sa.Column("trigger_event", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "achievement_id",
            "user_key",
            name="uq_achievement_unlock_target",
        ),
    )
    op.create_index("ix_achievement_unlock_user", "achievement_unlock", ["user_key"])

    op.create_table(
        "user_activity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_key",
            sa.String(length=64),
            nullable=False,
            server_default="system",
        ),
        sa.Column("activity_kind", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_identifier", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "activity_kind IN ("
            "'app_started','project_created','project_updated','document_imported',"
            "'search_executed','collection_created','evidence_extracted',"
            "'evidence_verified','analysis_run','guide_generated',"
            "'achievement_unlocked','settings_changed')",
            name="ck_user_activity_activity_kind_valid",
        ),
    )
    op.create_index("ix_user_activity_occurred_at", "user_activity", ["occurred_at"])
    op.create_index(
        "ix_user_activity_user_occurred",
        "user_activity",
        ["user_key", "occurred_at"],
    )

    op.create_table(
        "research_plan",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_research_plan_project_id_research_project",
            ),
            nullable=False,
        ),
        sa.Column(
            "version_label",
            sa.String(length=32),
            nullable=False,
            server_default="1",
        ),
        sa.Column("background", sa.Text(), nullable=False, server_default=""),
        sa.Column("problem_statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("research_question", sa.Text(), nullable=False, server_default=""),
        sa.Column("objectives", sa.Text(), nullable=False, server_default=""),
        sa.Column("design", sa.Text(), nullable=False, server_default=""),
        sa.Column("population", sa.Text(), nullable=False, server_default=""),
        sa.Column("sampling", sa.Text(), nullable=False, server_default=""),
        sa.Column("data_collection", sa.Text(), nullable=False, server_default=""),
        sa.Column("analysis", sa.Text(), nullable=False, server_default=""),
        sa.Column("ethics", sa.Text(), nullable=False, server_default=""),
        sa.Column("limitations", sa.Text(), nullable=False, server_default=""),
        sa.Column("references_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("open_questions", sa.Text(), nullable=False, server_default=""),
        sa.Column("extensions_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_research_plan_project", "research_plan", ["project_id"])
    op.create_index("ix_research_plan_created_at", "research_plan", ["created_at"])

    op.create_table(
        "research_task",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_research_task_project_id_research_project",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_research_task_project_position",
        "research_task",
        ["project_id", "position"],
    )
    op.create_index("ix_research_task_completed", "research_task", ["completed"])

    op.create_table(
        "research_title_candidate",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_research_title_candidate_project_id_research_project",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("strengths", sa.Text(), nullable=False, server_default=""),
        sa.Column("problems", sa.Text(), nullable=False, server_default=""),
        sa.Column("assumptions", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "state",
            sa.String(length=16),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "state IN ('proposed','accepted','rejected','archived')",
            name="ck_research_title_candidate_state_valid",
        ),
    )
    op.create_index(
        "ix_research_title_candidate_project",
        "research_title_candidate",
        ["project_id"],
    )

    op.create_table(
        "methodology_proposal",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_methodology_proposal_project_id_research_project",
            ),
            nullable=False,
        ),
        sa.Column("methodology_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("strengths", sa.Text(), nullable=False, server_default=""),
        sa.Column("limitations", sa.Text(), nullable=False, server_default=""),
        sa.Column("assumptions", sa.Text(), nullable=False, server_default=""),
        sa.Column("data_requirements", sa.Text(), nullable=False, server_default=""),
        sa.Column("ethical_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "state",
            sa.String(length=16),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "state IN ('proposed','accepted','rejected','archived')",
            name="ck_methodology_proposal_state_valid",
        ),
    )
    op.create_index(
        "ix_methodology_proposal_project",
        "methodology_proposal",
        ["project_id"],
    )

    op.create_table(
        "analysis_recommendation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey(
                "research_project.id",
                ondelete="CASCADE",
                name="fk_analysis_recommendation_project_id_research_project",
            ),
            nullable=False,
        ),
        sa.Column("method_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("assumptions", sa.Text(), nullable=False, server_default=""),
        sa.Column("diagnostics", sa.Text(), nullable=False, server_default=""),
        sa.Column("alternatives", sa.Text(), nullable=False, server_default=""),
        sa.Column("cautions", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "state",
            sa.String(length=16),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "state IN ('proposed','accepted','rejected','archived')",
            name="ck_analysis_recommendation_state_valid",
        ),
    )
    op.create_index(
        "ix_analysis_recommendation_project",
        "analysis_recommendation",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_recommendation_project", table_name="analysis_recommendation"
    )
    op.drop_table("analysis_recommendation")

    op.drop_index("ix_methodology_proposal_project", table_name="methodology_proposal")
    op.drop_table("methodology_proposal")

    op.drop_index(
        "ix_research_title_candidate_project",
        table_name="research_title_candidate",
    )
    op.drop_table("research_title_candidate")

    op.drop_index("ix_research_task_completed", table_name="research_task")
    op.drop_index("ix_research_task_project_position", table_name="research_task")
    op.drop_table("research_task")

    op.drop_index("ix_research_plan_created_at", table_name="research_plan")
    op.drop_index("ix_research_plan_project", table_name="research_plan")
    op.drop_table("research_plan")

    op.drop_index("ix_user_activity_user_occurred", table_name="user_activity")
    op.drop_index("ix_user_activity_occurred_at", table_name="user_activity")
    op.drop_table("user_activity")

    op.drop_index("ix_achievement_unlock_user", table_name="achievement_unlock")
    op.drop_table("achievement_unlock")

    op.drop_index("ix_achievement_category", table_name="achievement")
    op.drop_index("ix_achievement_key", table_name="achievement")
    op.drop_table("achievement")

    op.drop_index("ix_citation_record_source", table_name="citation_record")
    op.drop_index("ix_citation_record_section", table_name="citation_record")
    op.drop_table("citation_record")

    op.drop_index(
        "ix_research_guide_section_guide_position",
        table_name="research_guide_section",
    )
    op.drop_table("research_guide_section")

    op.drop_index(
        "ix_research_guide_owner_collection", table_name="research_guide"
    )
    op.drop_index("ix_research_guide_owner_project", table_name="research_guide")
    op.drop_index("ix_research_guide_key", table_name="research_guide")
    op.drop_table("research_guide")

    op.drop_index(
        "ix_knowledge_relationship_target", table_name="knowledge_relationship"
    )
    op.drop_index(
        "ix_knowledge_relationship_source", table_name="knowledge_relationship"
    )
    op.drop_table("knowledge_relationship")

    op.drop_index("ix_knowledge_node_kind", table_name="knowledge_node")
    op.drop_index("ix_knowledge_node_key", table_name="knowledge_node")
    op.drop_table("knowledge_node")