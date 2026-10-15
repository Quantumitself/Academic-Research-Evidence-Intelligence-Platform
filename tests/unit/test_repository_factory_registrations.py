"""Tests that the factory registers the standard repository set."""

from __future__ import annotations

from academic_platform.infrastructure.repositories import factory


def test_standard_registry_keys() -> None:
    keys = factory.registered_repository_keys()
    assert set(keys) == {
        "achievement",
        "achievement_unlock",
        "ai_invocation",
        "ai_model",
        "ai_provider",
        "ai_task_routing",
        "analysis_input",
        "analysis_recommendation",
        "analysis_run",
        "annotation",
        "app_settings",
        "audit_event",
        "citation_record",
        "collection",
        "collection_item",
        "document_asset",
        "document_chunk",
        "document_metadata",
        "evidence_extraction_run",
        "evidence_record",
        "knowledge_node",
        "knowledge_relationship",
        "methodology_proposal",
        "publication",
        "research_guide",
        "research_guide_section",
        "research_plan",
        "research_project",
        "research_question",
        "research_task",
        "research_title_candidate",
        "saved_search_query",
        "search_result",
        "search_session",
        "search_source",
        "synthesis_report",
        "user_activity",
        "user_profile",
    }


def test_standard_registry_classes_construct() -> None:
    """Every registered class must be a subclass of Repository."""
    from academic_platform.infrastructure.repositories.base import Repository

    from academic_platform.infrastructure.repositories import factory as factory_module

    for key, repository_class in factory_module._REPOSITORY_REGISTRY.items():  # noqa: SLF001
        assert issubclass(repository_class, Repository), key