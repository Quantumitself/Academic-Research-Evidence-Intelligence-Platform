"""Rules-based research title engine.

The engine applies a fixed set of title patterns to a topic draft. Each
pattern is a small function that, given the draft, returns either a
candidate title or ``None`` when the draft lacks the fields the pattern
requires. The engine also evaluates every candidate against the draft
and returns the candidates sorted by alignment score.

Design decisions
----------------
- The engine is a pure function. It never persists anything, never
  calls an AI provider, and never invents values the draft does not
  support.
- Patterns are additive: they never overwrite each other's candidates.
  Two patterns may produce very similar titles; the evaluator
  distinguishes them by their strengths and problems.
- The alignment score is a bounded, documented formula. It counts how
  many of the fields the pattern used are populated in the draft and
  weights fields by the specification's significance.
- Titles longer than a fixed limit are rejected by the pattern and
  reported as skipped.
- The engine's output is deterministic: the same draft produces the
  same candidates in the same order on every run.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from academic_platform.application.title_builder.errors import (
    TitleBuilderError,
)
from academic_platform.application.title_builder.model import (
    TitleAlignmentReport,
    TitleCandidate,
    TitleGenerationReport,
    TitlePattern,
)
from academic_platform.application.topic_workspace.model import (
    TopicDraft,
    TopicField,
)

_logger = logging.getLogger(__name__)

_MAX_TITLE_LENGTH = 200
_MAX_CONCEPTS = 3

PatternBuilder = Callable[[TopicDraft], TitleCandidate | None]


class TitleBuilderEngine:
    """Generate and evaluate candidate titles from a topic draft."""

    def __init__(
        self,
        patterns: tuple[PatternBuilder, ...] | None = None,
        *,
        max_candidates: int = 12,
    ) -> None:
        if max_candidates < 1:
            raise TitleBuilderError("max_candidates must be at least 1")
        self._patterns = patterns if patterns is not None else _default_patterns()
        self._max_candidates = max_candidates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(
        self,
        draft: TopicDraft,
        *,
        max_candidates: int | None = None,
    ) -> TitleGenerationReport:
        """Generate candidate titles from a topic draft."""
        limit = self._max_candidates if max_candidates is None else max_candidates
        if limit < 1:
            raise TitleBuilderError("max_candidates must be at least 1")

        candidates: list[TitleCandidate] = []
        skipped: list[str] = []
        notes: list[str] = []

        for pattern in self._patterns:
            try:
                candidate = pattern(draft)
            except Exception as exc:  # noqa: BLE001 - boundary
                raise TitleBuilderError(
                    f"Title pattern raised: {exc}"
                ) from exc
            if candidate is None:
                continue
            if len(candidate.title) > _MAX_TITLE_LENGTH:
                skipped.append(
                    f"{candidate.pattern.value} (title too long)"
                )
                continue
            candidates.append(candidate)

        if not candidates:
            notes.append(
                "No candidate titles could be generated from the current "
                "draft. Fill in the broad subject and the research problem "
                "to receive candidates."
            )

        candidates.sort(key=lambda c: (-c.alignment.score, c.identifier))
        return TitleGenerationReport(
            candidates=tuple(candidates[:limit]),
            skipped_patterns=tuple(skipped),
            notes=tuple(notes),
        )


# ----------------------------------------------------------------------
# Default patterns
# ----------------------------------------------------------------------
def _default_patterns() -> tuple[PatternBuilder, ...]:
    return (
        _pattern_subject_and_outcome,
        _pattern_subject_in_population,
        _pattern_effect_of_x_on_y,
        _pattern_association_between_x_and_y,
        _pattern_exploration_of_subject,
        _pattern_comparison_across_groups,
        _pattern_development_of_instrument,
        _pattern_methodological_study,
    )


def _pattern_subject_and_outcome(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    outcome = _first_item(draft.potential_outcomes)
    if not subject or not outcome:
        return None
    title = f"{_title_case(subject)} and {_title_case(outcome)}"
    return _build_candidate(
        pattern=TitlePattern.SUBJECT_AND_OUTCOME,
        title=title,
        rationale=(
            "Pairs the broad subject with a specific outcome, which yields "
            "a focused and readable title."
        ),
        strengths=(
            "Names the subject and the outcome explicitly. The scope is "
            "narrow enough to be studyable."
        ),
        problems=(
            "May be too broad if the subject is not further narrowed by a "
            "population or context."
        ),
        assumptions=(
            "The outcome is a construct the study can measure, not a "
            "general aspiration."
        ),
        draft=draft,
        fields_used=(
            TopicField.BROAD_SUBJECT,
            TopicField.POTENTIAL_OUTCOMES,
        ),
    )


def _pattern_subject_in_population(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    population = draft.population
    if not subject or not population:
        return None
    title = f"{_title_case(subject)} in {_title_case(population)}"
    return _build_candidate(
        pattern=TitlePattern.SUBJECT_IN_POPULATION,
        title=title,
        rationale=(
            "Bounds the subject with a specific population, which makes "
            "the sampling frame explicit."
        ),
        strengths=(
            "Communicates the population at a glance. Useful for studies "
            "whose contribution is population-specific."
        ),
        problems=(
            "Does not name an outcome, so the reader must look elsewhere "
            "to learn what is measured."
        ),
        assumptions=(
            "The population is accessible to the researcher and matches "
            "the research question."
        ),
        draft=draft,
        fields_used=(
            TopicField.BROAD_SUBJECT,
            TopicField.POPULATION,
        ),
    )


def _pattern_effect_of_x_on_y(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    outcome = _first_item(draft.potential_outcomes)
    if not subject or not outcome:
        return None
    title = (
        f"The Effect of {_title_case(subject)} on {_title_case(outcome)}"
    )
    return _build_candidate(
        pattern=TitlePattern.EFFECT_OF_X_ON_Y,
        title=title,
        rationale=(
            "Frames the study as an effect investigation, which aligns "
            "with experimental and quasi-experimental designs."
        ),
        strengths=(
            "Clearly states an independent variable and a dependent "
            "variable."
        ),
        problems=(
            "Implies causation; only a design that can support causal "
            "inference may use this title."
        ),
        assumptions=(
            "The design can support a causal claim. Observational designs "
            "must not use this title."
        ),
        draft=draft,
        fields_used=(
            TopicField.BROAD_SUBJECT,
            TopicField.POTENTIAL_OUTCOMES,
        ),
    )


def _pattern_association_between_x_and_y(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    outcome = _first_item(draft.potential_outcomes)
    if not subject or not outcome:
        return None
    title = (
        f"Association Between {_title_case(subject)} and "
        f"{_title_case(outcome)}"
    )
    return _build_candidate(
        pattern=TitlePattern.ASSOCIATION_BETWEEN_X_AND_Y,
        title=title,
        rationale=(
            "Frames the study as an association investigation, which "
            "aligns with observational and correlational designs."
        ),
        strengths=(
            "Avoids implying causation. Suitable when the design cannot "
            "establish a causal relationship."
        ),
        problems=(
            "Association studies may still require large samples to "
            "detect modest effects."
        ),
        assumptions=(
            "The design observes the variables without intervening. No "
            "causal claim is intended."
        ),
        draft=draft,
        fields_used=(
            TopicField.BROAD_SUBJECT,
            TopicField.POTENTIAL_OUTCOMES,
        ),
    )


def _pattern_exploration_of_subject(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    if not subject:
        return None
    context = draft.context
    if context:
        title = (
            f"Exploring {_title_case(subject)} in {_title_case(context)}"
        )
    else:
        title = f"Exploring {_title_case(subject)}"
    return _build_candidate(
        pattern=TitlePattern.EXPLORATION_OF_SUBJECT,
        title=title,
        rationale=(
            "Signals an exploratory or qualitative inquiry, which does "
            "not require a pre-specified hypothesis."
        ),
        strengths=(
            "Broad enough to admit multiple research questions. Suitable "
            "for understudied topics."
        ),
        problems=(
            "Provides little specificity; the reader may not be able to "
            "tell what the study measures."
        ),
        assumptions=(
            "The topic is understudied enough that an exploratory design "
            "is appropriate."
        ),
        draft=draft,
        fields_used=(
            TopicField.BROAD_SUBJECT,
            *( [TopicField.CONTEXT] if context else [] ),
        ),
    )


def _pattern_comparison_across_groups(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    outcome = _first_item(draft.potential_outcomes)
    population = draft.population
    if not subject or not outcome or not population:
        return None
    title = (
        f"A Comparison of {_title_case(subject)} Across "
        f"{_title_case(population)}"
    )
    return _build_candidate(
        pattern=TitlePattern.COMPARISON_ACROSS_GROUPS,
        title=title,
        rationale=(
            "Frames the study as a group comparison, which aligns with "
            "cross-group designs."
        ),
        strengths=(
            "States the subject, the outcome and the population. Clear "
            "about the study's comparative goal."
        ),
        problems=(
            "Requires a defensible grouping. Groups must be defined "
            "before data collection."
        ),
        assumptions=(
            "The groups are well-defined and comparable on the relevant "
            "dimensions."
        ),
        draft=draft,
        fields_used=(
            TopicField.BROAD_SUBJECT,
            TopicField.POTENTIAL_OUTCOMES,
            TopicField.POPULATION,
        ),
    )


def _pattern_development_of_instrument(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    if not subject:
        return None
    lowered = subject.lower()
    if "instrument" not in lowered and "scale" not in lowered and "measure" not in lowered:
        return None
    return _build_candidate(
        pattern=TitlePattern.DEVELOPMENT_OF_INSTRUMENT,
        title=f"Development and Validation of a Measure of {_title_case(subject)}",
        rationale=(
            "Frames the study as a measurement-development project, "
            "which aligns with psychometric designs."
        ),
        strengths=(
            "States the project's contribution. Fits studies whose "
            "primary output is an instrument."
        ),
        problems=(
            "Requires a sample large enough for psychometric analysis."
        ),
        assumptions=(
            "The construct is not already covered by an adequate "
            "instrument."
        ),
        draft=draft,
        fields_used=(TopicField.BROAD_SUBJECT,),
    )


def _pattern_methodological_study(draft: TopicDraft) -> TitleCandidate | None:
    subject = draft.broad_subject
    if not subject:
        return None
    lowered = subject.lower()
    if "method" not in lowered and "methodolog" not in lowered:
        return None
    return _build_candidate(
        pattern=TitlePattern.METHODOLOGICAL_STUDY,
        title=f"A Methodological Study of {_title_case(subject)}",
        rationale=(
            "Signals a study of methods rather than of a substantive "
            "phenomenon."
        ),
        strengths=(
            "Clearly communicates the study's contribution to methods."
        ),
        problems=(
            "Methodological studies must justify why the method deserves "
            "examination."
        ),
        assumptions=(
            "The method's use is common enough that a methodological "
            "review is warranted."
        ),
        draft=draft,
        fields_used=(TopicField.BROAD_SUBJECT,),
    )


# ----------------------------------------------------------------------
# Candidate construction and alignment
# ----------------------------------------------------------------------
_FIELD_WEIGHTS: dict[TopicField, float] = {
    TopicField.BROAD_SUBJECT: 0.30,
    TopicField.RESEARCH_PROBLEM: 0.25,
    TopicField.POTENTIAL_OUTCOMES: 0.15,
    TopicField.POPULATION: 0.10,
    TopicField.CONTEXT: 0.05,
    TopicField.KEY_CONCEPTS: 0.05,
    TopicField.TIME_PERIOD: 0.03,
    TopicField.CONSTRAINTS: 0.03,
    TopicField.KNOWLEDGE_LEVEL: 0.04,
}

_FIELD_LABELS: dict[TopicField, str] = {
    field: field.display_name for field in TopicField
}


def _build_candidate(
    *,
    pattern: TitlePattern,
    title: str,
    rationale: str,
    strengths: str,
    problems: str,
    assumptions: str,
    draft: TopicDraft,
    fields_used: tuple[TopicField, ...],
) -> TitleCandidate:
    alignment = _evaluate_alignment(draft, fields_used)
    return TitleCandidate(
        identifier=f"title.{pattern.value}",
        pattern=pattern,
        title=title,
        rationale=rationale,
        strengths=strengths,
        problems=problems,
        assumptions=assumptions,
        alignment=alignment,
    )


def _evaluate_alignment(
    draft: TopicDraft,
    fields_used: tuple[TopicField, ...],
) -> TitleAlignmentReport:
    matched: list[str] = []
    missing: list[str] = []
    score = 0.0
    for field in fields_used:
        if draft.value(field).strip():
            matched.append(field.value)
            score += _FIELD_WEIGHTS.get(field, 0.0)
        else:
            missing.append(field.value)
    # Additional context fields contribute a small amount even when the
    # pattern did not explicitly require them, so that a fully filled
    # draft raises the score of every candidate.
    for field in TopicField:
        if field in fields_used:
            continue
        if not draft.value(field).strip():
            continue
        score += _FIELD_WEIGHTS.get(field, 0.0) * 0.25
    score = max(0.0, min(1.0, score))
    notes: list[str] = []
    if missing:
        notes.append(
            "Missing fields: "
            + ", ".join(_FIELD_LABELS.get(TopicField(f), f) for f in missing)
        )
    return TitleAlignmentReport(
        score=round(score, 3),
        matched_fields=tuple(matched),
        missing_fields=tuple(missing),
        notes=tuple(notes),
    )


# ----------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------
_WORD_PATTERN = re.compile(r"\b[\w'-]+\b")


def _title_case(value: str) -> str:
    """Return a title-case version of ``value`` while preserving acronyms."""
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    tokens = _WORD_PATTERN.findall(cleaned)
    if not tokens:
        return cleaned
    rendered: list[str] = []
    for token in tokens:
        if token.isupper() and len(token) <= 5:
            rendered.append(token)
        else:
            rendered.append(token.capitalize())
    return " ".join(rendered)


def _first_item(value: str) -> str:
    """Return the first item from a comma- or semicolon-separated list."""
    if not value:
        return ""
    for separator in (";", "|", ","):
        if separator in value:
            first = value.split(separator, 1)[0].strip()
            if first:
                return first
    return value.strip()


def _concepts_list(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    parts = [part.strip() for part in re.split(r"[;,|]", value)]
    return tuple(part for part in parts if part)[:_MAX_CONCEPTS]