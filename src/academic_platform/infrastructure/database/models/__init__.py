"""ORM models.

Models in this package inherit from ``Base`` and, where appropriate, from
the shared mixins in ``academic_platform.infrastructure.database.base``.
Every model is imported here so that Alembic's autogenerate sees the full
schema when it inspects ``Base.metadata``.
"""

from academic_platform.infrastructure.database.models.achievement import (
    Achievement,
    AchievementUnlock,
    UserActivity,
)
from academic_platform.infrastructure.database.models.ai_invocation import AIInvocation
from academic_platform.infrastructure.database.models.ai_model import AIModel
from academic_platform.infrastructure.database.models.ai_provider import AIProvider
from academic_platform.infrastructure.database.models.ai_task_routing import (
    AITaskRouting,
)
from academic_platform.infrastructure.database.models.analysis_run import (
    AnalysisInput,
    AnalysisRun,
)
from academic_platform.infrastructure.database.models.annotation import Annotation
from academic_platform.infrastructure.database.models.audit_event import AuditEvent
from academic_platform.infrastructure.database.models.app_settings import AppSettings
from academic_platform.infrastructure.database.models.collection import Collection
from academic_platform.infrastructure.database.models.collection_item import (
    CollectionItem,
)
from academic_platform.infrastructure.database.models.document_asset import DocumentAsset
from academic_platform.infrastructure.database.models.document_chunk import DocumentChunk
from academic_platform.infrastructure.database.models.document_metadata import (
    DocumentMetadata,
)
from academic_platform.infrastructure.database.models.evidence_extraction_run import (
    EvidenceExtractionRun,
)
from academic_platform.infrastructure.database.models.evidence_record import (
    EvidenceRecord,
)
from academic_platform.infrastructure.database.models.knowledge import (
    KnowledgeNode,
    KnowledgeRelationship,
)
from academic_platform.infrastructure.database.models.publication import Publication
from academic_platform.infrastructure.database.models.research_guide import (
    CitationRecord,
    ResearchGuide,
    ResearchGuideSection,
)
from academic_platform.infrastructure.database.models.research_plan import (
    AnalysisRecommendation,
    MethodologyProposal,
    ResearchPlan,
    ResearchTask,
    ResearchTitleCandidate,
)
from academic_platform.infrastructure.database.models.research_project import (
    ResearchProject,
)
from academic_platform.infrastructure.database.models.research_question import (
    ResearchQuestion,
)
from academic_platform.infrastructure.database.models.search_query import SavedSearchQuery
from academic_platform.infrastructure.database.models.search_session import (
    SearchResult,
    SearchSession,
)
from academic_platform.infrastructure.database.models.search_source import SearchSource
from academic_platform.infrastructure.database.models.synthesis_report import (
    SynthesisReport,
)
from academic_platform.infrastructure.database.models.user_profile import UserProfile

__all__ = [
    "AIInvocation",
    "AIModel",
    "AIProvider",
    "AITaskRouting",
    "Achievement",
    "AchievementUnlock",
    "AnalysisInput",
    "AnalysisRecommendation",
    "AnalysisRun",
    "Annotation",
    "AppSettings",
    "AuditEvent",
    "CitationRecord",
    "Collection",
    "CollectionItem",
    "DocumentAsset",
    "DocumentChunk",
    "DocumentMetadata",
    "EvidenceExtractionRun",
    "EvidenceRecord",
    "KnowledgeNode",
    "KnowledgeRelationship",
    "MethodologyProposal",
    "Publication",
    "ResearchGuide",
    "ResearchGuideSection",
    "ResearchPlan",
    "ResearchProject",
    "ResearchQuestion",
    "ResearchTask",
    "ResearchTitleCandidate",
    "SavedSearchQuery",
    "SearchResult",
    "SearchSession",
    "SearchSource",
    "SynthesisReport",
    "UserActivity",
    "UserProfile",
]