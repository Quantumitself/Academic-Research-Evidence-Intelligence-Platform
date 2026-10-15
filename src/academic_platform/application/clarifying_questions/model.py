"""Value objects for the clarifying-question engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QuestionCategory(str, Enum):
    """The categories a clarifying question can belong to."""

    SCOPE = "scope"
    PROBLEM = "problem"
    CONTEXT = "context"
    POPULATION = "population"
    TIME = "time"
    CONCEPTS = "concepts"
    OUTCOMES = "outcomes"
    CONSTRAINTS = "constraints"
    KNOWLEDGE = "knowledge"

    @property
    def display_name(self) -> str:
        return {
            QuestionCategory.SCOPE: "Scope",
            QuestionCategory.PROBLEM: "Problem",
            QuestionCategory.CONTEXT: "Context",
            QuestionCategory.POPULATION: "Population",
            QuestionCategory.TIME: "Time period",
            QuestionCategory.CONCEPTS: "Key concepts",
            QuestionCategory.OUTCOMES: "Outcomes",
            QuestionCategory.CONSTRAINTS: "Constraints",
            QuestionCategory.KNOWLEDGE: "Knowledge",
        }[self]


@dataclass(frozen=True, slots=True)
class ClarifyingQuestion:
    """A single clarifying question.

    Attributes
    ----------
    identifier:
        Stable identifier derived from the target field and the reason.
        The identifier is used by the presentation layer to persist the
        user's answer or to dismiss the question.
    category:
        The category the question belongs to.
    target_field:
        The topic workspace field the answer should populate.
    text:
        The question text as the user will see it.
    rationale:
        A short explanation of why the question is being asked.
    priority:
        A lower number indicates a higher priority. The engine sorts
        the results in ascending priority order.
    blocking:
        When True, the engine considers the question to be essential
        to the next workflow step. When False, the question is
        advisory.
    example_answer:
        An optional example of the kind of answer the engine expects.
    """

    identifier: str
    category: QuestionCategory
    target_field: str
    text: str
    rationale: str
    priority: int = 100
    blocking: bool = False
    example_answer: str = ""

    @property
    def display_label(self) -> str:
        prefix = "★ " if self.blocking else ""
        return f"{prefix}{self.text}"