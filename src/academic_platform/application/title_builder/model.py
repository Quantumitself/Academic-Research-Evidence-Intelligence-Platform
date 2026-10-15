"""Value objects for the title builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TitlePattern(str, Enum):
    """The title templates the engine knows how to render."""

    SUBJECT_AND_OUTCOME = "subject_and_outcome"
    SUBJECT_IN_POPULATION = "subject_in_population"
    EFFECT_OF_X_ON_Y = "effect_of_x_on_y"
    ASSOCIATION_BETWEEN_X_AND_Y = "association_between_x_and_y"
    EXPLORATION_OF_SUBJECT = "exploration_of_subject"
    COMPARISON_ACROSS_GROUPS = "comparison_across_groups"
    DEVELOPMENT_OF_INSTRUMENT = "development_of_instrument"
    METHODOLOGICAL_STUDY = "methodological_study"

    @property
    def display_name(self) -> str:
        return {
            TitlePattern.SUBJECT_AND_OUTCOME: "Subject and outcome",
            TitlePattern.SUBJECT_IN_POPULATION: "Subject in population",
            TitlePattern.EFFECT_OF_X_ON_Y: "Effect of X on Y",
            TitlePattern.ASSOCIATION_BETWEEN_X_AND_Y: "Association between X and Y",
            TitlePattern.EXPLORATION_OF_SUBJECT: "Exploration of subject",
            TitlePattern.COMPARISON_ACROSS_GROUPS: "Comparison across groups",
            TitlePattern.DEVELOPMENT_OF_INSTRUMENT: "Development of instrument",
            TitlePattern.METHODOLOGICAL_STUDY: "Methodological study",
        }[self]


class TitleState(str, Enum):
    """Lifecycle state of a candidate title."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"

    @property
    def display_name(self) -> str:
        return {
            TitleState.PROPOSED: "Proposed",
            TitleState.ACCEPTED: "Accepted",
            TitleState.REJECTED: "Rejected",
            TitleState.ARCHIVED: "Archived",
        }[self]


@dataclass(frozen=True, slots=True)
class TitleAlignmentReport:
    """The result of evaluating a candidate against the draft."""

    score: float = 0.0
    matched_fields: tuple[str, ...] = field(default_factory=tuple)
    missing_fields: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_ready(self) -> bool:
        return self.score >= 0.6

    @property
    def summary(self) -> str:
        if self.is_ready:
            return f"alignment {self.score:.2f}"
        if self.missing_fields:
            missing = ", ".join(self.missing_fields)
            return f"alignment {self.score:.2f} (missing: {missing})"
        return f"alignment {self.score:.2f}"


@dataclass(frozen=True, slots=True)
class TitleCandidate:
    """A single candidate research title."""

    identifier: str
    pattern: TitlePattern
    title: str
    rationale: str
    strengths: str
    problems: str
    assumptions: str
    alignment: TitleAlignmentReport
    state: TitleState = TitleState.PROPOSED

    @property
    def display_label(self) -> str:
        marker = "★ " if self.state is TitleState.ACCEPTED else ""
        return f"{marker}{self.title}"

    @property
    def is_accepted(self) -> bool:
        return self.state is TitleState.ACCEPTED


@dataclass(frozen=True, slots=True)
class TitleGenerationReport:
    """The engine's output for a single generation call."""

    candidates: tuple[TitleCandidate, ...] = field(default_factory=tuple)
    skipped_patterns: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def is_empty(self) -> bool:
        return not self.candidates