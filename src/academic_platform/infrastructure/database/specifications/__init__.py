"""Reusable specifications.

Specifications that are used by more than one repository or that express
a query the application issues in several places live in this package.
Repository-private specifications live in the repository module itself.
"""

from academic_platform.infrastructure.repositories.specifications.collections import (
    CollectionByKind,
    CollectionByProject,
)
from academic_platform.infrastructure.repositories.specifications.projects import (
    ProjectByStage,
    ProjectTitleContains,
)
from academic_platform.infrastructure.repositories.specifications.questions import (
    QuestionByKind,
    QuestionByProject,
    PrimaryQuestionForProject,
)

__all__ = [
    "CollectionByKind",
    "CollectionByProject",
    "PrimaryQuestionForProject",
    "ProjectByStage",
    "ProjectTitleContains",
    "QuestionByKind",
    "QuestionByProject",
]