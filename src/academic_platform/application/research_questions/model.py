"""Value objects for the research-question workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QuestionKind(str, Enum):
    """The kinds of question the workspace supports."""

    MAIN = "main"
    SUB = "sub"
    EXPLORATORY = "exploratory"
    HYPOTHESIS = "hypothesis"

    @property
    def display_name(self) -> str:
        return {
            QuestionKind.MAIN: "Main question",
            QuestionKind.SUB: "Sub question",
            QuestionKind.EXPLORATORY: "Exploratory question",
            QuestionKind.HYPOTHESIS: "Hypothesis",
        }[self]

    @property
    def is_testable(self) -> bool:
        """Return True for kinds that normally admit an empirical test."""
        return self in {
            QuestionKind.MAIN,
            QuestionKind.SUB,
            QuestionKind.HYPOTHESIS,
        }


@dataclass(frozen=True, slots=True)
class ResearchQuestionView:
    """A single question as seen by the presentation layer."""

    identifier: int
    text: str
    kind: QuestionKind
    is_primary: bool
    position: int
    created_at: str
    updated_at: str

    @property
    def display_label(self) -> str:
        prefix = "★ " if self.is_primary else ""
        return f"{prefix}[{self.kind.display_name}] {self.text}"


@dataclass(frozen=True, slots=True)
class QuestionValidationIssue:
    """A single validation issue."""

    severity: str  # "error" or "warning"
    field: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    @property
    def is_warning(self) -> bool:
        return self.severity == "warning"


@dataclass(frozen=True, slots=True)
class QuestionValidationReport:
    """The result of validating the workspace draft."""

    issues: tuple[QuestionValidationIssue, ...] = field(default_factory=tuple)
    score: float = 0.0

    @property
    def errors(self) -> tuple[QuestionValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.is_error)

    @property
    def warnings(self) -> tuple[QuestionValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.is_warning)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def summary(self) -> str:
        errors = len(self.errors)
        warnings = len(self.warnings)
        if errors == 0 and warnings == 0:
            return f"valid (score {self.score:.2f})"
        parts: list[str] = []
        if errors:
            parts.append(f"{errors} error(s)")
        if warnings:
            parts.append(f"{warnings} warning(s)")
        parts.append(f"score {self.score:.2f}")
        return " · ".join(parts)


@dataclass(frozen=True, slots=True)
class ResearchQuestionDraft:
    """An immutable view of the workspace's current state."""

    project_key: str | None
    primary_question: str = ""
    topic: str = ""
    problem: str = ""
    gap: str = ""
    questions: tuple[ResearchQuestionView, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return (
            not self.primary_question.strip()
            and not self.topic.strip()
            and not self.problem.strip()
            and not self.gap.strip()
            and not self.questions
        )

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def has_primary(self) -> bool:
        if self.primary_question.strip():
            return True
        return any(question.is_primary for question in self.questions)