"""Value objects for the Topic & Problem workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TopicField(str, Enum):
    """The fields the Topic & Problem workspace captures."""

    BROAD_SUBJECT = "broad_subject"
    RESEARCH_PROBLEM = "research_problem"
    CONTEXT = "context"
    POPULATION = "population"
    TIME_PERIOD = "time_period"
    KEY_CONCEPTS = "key_concepts"
    POTENTIAL_OUTCOMES = "potential_outcomes"
    CONSTRAINTS = "constraints"
    KNOWLEDGE_LEVEL = "knowledge_level"

    @property
    def display_name(self) -> str:
        return {
            TopicField.BROAD_SUBJECT: "Broad subject",
            TopicField.RESEARCH_PROBLEM: "Research problem",
            TopicField.CONTEXT: "Context",
            TopicField.POPULATION: "Population",
            TopicField.TIME_PERIOD: "Time period",
            TopicField.KEY_CONCEPTS: "Key concepts",
            TopicField.POTENTIAL_OUTCOMES: "Potential outcomes",
            TopicField.CONSTRAINTS: "Constraints",
            TopicField.KNOWLEDGE_LEVEL: "Researcher's knowledge level",
        }[self]


#: Fields the completeness report treats as essential. The other fields
#: contribute to the report but do not block readiness.
ESSENTIAL_FIELDS: tuple[TopicField, ...] = (
    TopicField.BROAD_SUBJECT,
    TopicField.RESEARCH_PROBLEM,
)


@dataclass(frozen=True, slots=True)
class TopicDraft:
    """An immutable view of the workspace's current state."""

    project_key: str | None
    values: dict[str, str] = field(default_factory=dict)

    def value(self, field: TopicField) -> str:
        return self.values.get(field.value, "")

    @property
    def broad_subject(self) -> str:
        return self.value(TopicField.BROAD_SUBJECT)

    @property
    def research_problem(self) -> str:
        return self.value(TopicField.RESEARCH_PROBLEM)

    @property
    def context(self) -> str:
        return self.value(TopicField.CONTEXT)

    @property
    def population(self) -> str:
        return self.value(TopicField.POPULATION)

    @property
    def time_period(self) -> str:
        return self.value(TopicField.TIME_PERIOD)

    @property
    def key_concepts(self) -> str:
        return self.value(TopicField.KEY_CONCEPTS)

    @property
    def potential_outcomes(self) -> str:
        return self.value(TopicField.POTENTIAL_OUTCOMES)

    @property
    def constraints(self) -> str:
        return self.value(TopicField.CONSTRAINTS)

    @property
    def knowledge_level(self) -> str:
        return self.value(TopicField.KNOWLEDGE_LEVEL)

    @property
    def populated_fields(self) -> tuple[TopicField, ...]:
        return tuple(
            field
            for field in TopicField
            if self.values.get(field.value, "").strip()
        )

    @property
    def is_empty(self) -> bool:
        return not self.populated_fields


@dataclass(frozen=True, slots=True)
class TopicCompleteness:
    """Completeness report for a topic draft."""

    populated: tuple[TopicField, ...] = field(default_factory=tuple)
    missing_essential: tuple[TopicField, ...] = field(default_factory=tuple)
    populated_count: int = 0
    total_count: int = 0

    @property
    def is_ready(self) -> bool:
        """Return True when every essential field is populated."""
        return not self.missing_essential

    @property
    def ratio(self) -> float:
        if self.total_count <= 0:
            return 0.0
        return max(0.0, min(1.0, self.populated_count / self.total_count))

    @property
    def summary(self) -> str:
        if self.is_ready:
            return f"{self.populated_count} / {self.total_count} field(s) populated"
        missing = ", ".join(field.display_name for field in self.missing_essential)
        return f"missing essential: {missing}"