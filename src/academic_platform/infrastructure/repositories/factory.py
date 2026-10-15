"""Repository factory helpers.

The factory module provides a thin wrapper that constructs a
``RepositoryManager`` for the duration of a unit of work and registers
the standard repository classes. It exists so that application code does
not need to remember which repositories to register.

Design decisions
----------------
- The factory accepts a ``Database`` and yields a manager bound to a
  single session. The session is committed on success and rolled back on
  failure.
- Registration is driven by a module-level mapping. New repositories are
  added to the mapping; the factory does not need to be edited.
- The factory is a context manager. Callers use it as::

      with unit_of_work(database) as repositories:
          profile = repositories.get("user_profile").get(1)

- The unit of work does not provide nested transactions. Nested contexts
  share the outer session and commit at the outermost boundary.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.manager import RepositoryManager
from academic_platform.infrastructure.repositories.app_settings_repository import (
    AppSettingsRepository,
)
from academic_platform.infrastructure.repositories.audit_event_repository import (
    AuditEventRepository,
)
from academic_platform.infrastructure.repositories.user_profile_repository import (
    UserProfileRepository,
)
from academic_platform.infrastructure.repositories.collection_repository import (
    CollectionItemRepository,
    CollectionRepository,
)
from academic_platform.infrastructure.repositories.research_project_repository import (
    ResearchProjectRepository,
)
from academic_platform.infrastructure.repositories.research_question_repository import (
    ResearchQuestionRepository,
)
from academic_platform.infrastructure.repositories.document_asset_repository import (
    AnnotationRepository,
    DocumentAssetRepository,
    DocumentChunkRepository,
    DocumentMetadataRepository,
)
from academic_platform.infrastructure.repositories.publication_repository import (
    PublicationRepository,
)
from academic_platform.infrastructure.repositories.search_session_repository import (
    SavedSearchQueryRepository,
    SearchResultRepository,
    SearchSessionRepository,
)
from academic_platform.infrastructure.repositories.search_source_repository import (
    SearchSourceRepository,
)
from academic_platform.infrastructure.repositories.ai_provider_repository import (
    AIInvocationRepository,
    AIModelRepository,
    AIProviderRepository,
    AITaskRoutingRepository,
)
from academic_platform.infrastructure.repositories.analysis_repository import (
    AnalysisInputRepository,
    AnalysisRunRepository,
)
from academic_platform.infrastructure.repositories.evidence_repository import (
    EvidenceExtractionRunRepository,
    EvidenceRecordRepository,
    SynthesisReportRepository,
)
from academic_platform.infrastructure.repositories.achievement_repository import (
    AchievementRepository,
    AchievementUnlockRepository,
    UserActivityRepository,
)
from academic_platform.infrastructure.repositories.knowledge_repository import (
    KnowledgeNodeRepository,
    KnowledgeRelationshipRepository,
)
from academic_platform.infrastructure.repositories.research_guide_repository import (
    CitationRecordRepository,
    ResearchGuideRepository,
    ResearchGuideSectionRepository,
)
from academic_platform.infrastructure.repositories.research_plan_repository import (
    AnalysisRecommendationRepository,
    MethodologyProposalRepository,
    ResearchPlanRepository,
    ResearchTaskRepository,
    ResearchTitleCandidateRepository,
)


_logger = logging.getLogger(__name__)

#: Mapping of repository key to repository class. Concrete repositories
#: are registered here as they are implemented. The mapping is a plain
#: dictionary so that tests may override entries for the duration of a
#: test.
_REPOSITORY_REGISTRY: dict[str, type[Repository]] = {
    "user_profile": UserProfileRepository,
    "app_settings": AppSettingsRepository,
    "audit_event": AuditEventRepository,
    "research_project": ResearchProjectRepository,
    "research_question": ResearchQuestionRepository,
    "collection": CollectionRepository,
    "collection_item": CollectionItemRepository,
    "document_asset": DocumentAssetRepository,
    "document_metadata": DocumentMetadataRepository,
    "document_chunk": DocumentChunkRepository,
    "annotation": AnnotationRepository,
    "publication": PublicationRepository,
    "search_source": SearchSourceRepository,
    "saved_search_query": SavedSearchQueryRepository,
    "search_session": SearchSessionRepository,
    "search_result": SearchResultRepository,
    "ai_provider": AIProviderRepository,
    "ai_model": AIModelRepository,
    "ai_task_routing": AITaskRoutingRepository,
    "ai_invocation": AIInvocationRepository,
    "evidence_record": EvidenceRecordRepository,
    "evidence_extraction_run": EvidenceExtractionRunRepository,
    "analysis_run": AnalysisRunRepository,
    "analysis_input": AnalysisInputRepository,
    "synthesis_report": SynthesisReportRepository,
    "knowledge_node": KnowledgeNodeRepository,
    "knowledge_relationship": KnowledgeRelationshipRepository,
    "research_guide": ResearchGuideRepository,
    "research_guide_section": ResearchGuideSectionRepository,
    "citation_record": CitationRecordRepository,
    "achievement": AchievementRepository,
    "achievement_unlock": AchievementUnlockRepository,
    "user_activity": UserActivityRepository,
    "research_plan": ResearchPlanRepository,
    "research_task": ResearchTaskRepository,
    "research_title_candidate": ResearchTitleCandidateRepository,
    "methodology_proposal": MethodologyProposalRepository,
    "analysis_recommendation": AnalysisRecommendationRepository,
}


def register_repository(key: str, repository_class: type[Repository]) -> None:
    """Register a repository class under a stable key."""
    _REPOSITORY_REGISTRY[key] = repository_class


def registered_repository_keys() -> tuple[str, ...]:
    """Return the sorted keys of every registered repository."""
    return tuple(sorted(_REPOSITORY_REGISTRY.keys()))


@contextmanager
def unit_of_work(database: Database) -> Iterator[RepositoryManager]:
    """Yield a ``RepositoryManager`` bound to a transactional session.

    The session is committed on success and rolled back on failure. The
    manager is discarded when the context exits; callers must not retain
    references to it or to its repositories after the context exits.
    """
    with database.session() as session:
        manager = RepositoryManager(session)
        manager.register_all(dict(_REPOSITORY_REGISTRY))
        try:
            yield manager
        finally:
            manager.clear_cache()