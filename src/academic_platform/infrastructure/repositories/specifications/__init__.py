"""Reusable specifications.

Specifications that are used by more than one repository or that express
a query the application issues in several places live in this package.
Repository-private specifications live in the repository module itself.
"""

from academic_platform.infrastructure.repositories.specifications.ai import (
    AIInvocationByTask,
    AIInvocationFailed,
    AIModelByProvider,
    AIModelEnabled,
    AIProviderByKind,
    AIProviderEnabled,
)
from academic_platform.infrastructure.repositories.specifications.annotations import (
    AnnotationByDocument,
    AnnotationByKind,
    AnnotationOnPage,
)
from academic_platform.infrastructure.repositories.specifications.collections import (
    CollectionByKind,
    CollectionByProject,
)
from academic_platform.infrastructure.repositories.specifications.documents import (
    DocumentByProcessingState,
    DocumentByStorageMode,
    DocumentChecksum,
    DocumentDisplayNameContains,
    DocumentMissing,
)
from academic_platform.infrastructure.repositories.specifications.evidence import (
    AnalysisByType,
    AnalysisSucceeded,
    EvidenceAwaitingReview,
    EvidenceByDocument,
    EvidenceByType,
    EvidenceByVerification,
)
from academic_platform.infrastructure.repositories.specifications.knowledge import (
    AchievementActive,
    KnowledgeNodeByKind,
    KnowledgeRelationshipAIGrounded,
    KnowledgeRelationshipFrom,
    KnowledgeRelationshipTo,
    ResearchGuideByKind,
    ResearchGuideForProject,
    ResearchGuideSectionFor,
    ResearchPlanForProject,
    ResearchTaskForProject,
    ResearchTaskOpen,
)
from academic_platform.infrastructure.repositories.specifications.projects import (
    ProjectByStage,
    ProjectTitleContains,
)
from academic_platform.infrastructure.repositories.specifications.publications import (
    PublicationByDoi,
    PublicationInYearRange,
    PublicationOpenAccess,
    PublicationTitleContains,
)
from academic_platform.infrastructure.repositories.specifications.questions import (
    QuestionByKind,
    QuestionByProject,
    PrimaryQuestionForProject,
)
from academic_platform.infrastructure.repositories.specifications.search_sessions import (
    SearchResultByProvider,
    SearchResultBySession,
    SearchSessionByQueryText,
)
from academic_platform.infrastructure.repositories.specifications.search_sources import (
    SearchSourceByType,
    SearchSourceEnabled,
)

__all__ = [
    "AIInvocationByTask",
    "AIInvocationFailed",
    "AIModelByProvider",
    "AIModelEnabled",
    "AIProviderByKind",
    "AIProviderEnabled",
    "AchievementActive",
    "AnalysisByType",
    "AnalysisSucceeded",
    "AnnotationByDocument",
    "AnnotationByKind",
    "AnnotationOnPage",
    "CollectionByKind",
    "CollectionByProject",
    "DocumentByProcessingState",
    "DocumentByStorageMode",
    "DocumentChecksum",
    "DocumentDisplayNameContains",
    "DocumentMissing",
    "EvidenceAwaitingReview",
    "EvidenceByDocument",
    "EvidenceByType",
    "EvidenceByVerification",
    "KnowledgeNodeByKind",
    "KnowledgeRelationshipAIGrounded",
    "KnowledgeRelationshipFrom",
    "KnowledgeRelationshipTo",
    "PrimaryQuestionForProject",
    "ProjectByStage",
    "ProjectTitleContains",
    "PublicationByDoi",
    "PublicationInYearRange",
    "PublicationOpenAccess",
    "PublicationTitleContains",
    "QuestionByKind",
    "QuestionByProject",
    "ResearchGuideByKind",
    "ResearchGuideForProject",
    "ResearchGuideSectionFor",
    "ResearchPlanForProject",
    "ResearchTaskForProject",
    "ResearchTaskOpen",
    "SearchResultByProvider",
    "SearchResultBySession",
    "SearchSessionByQueryText",
    "SearchSourceByType",
    "SearchSourceEnabled",
]
