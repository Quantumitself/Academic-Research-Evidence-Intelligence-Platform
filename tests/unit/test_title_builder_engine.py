"""Tests for the rules-based title builder engine."""

from __future__ import annotations

import pytest

from academic_platform.application.title_builder.engine import (
    TitleBuilderEngine,
)
from academic_platform.application.title_builder.errors import (
    TitleBuilderError,
)
from academic_platform.application.title_builder.model import (
    TitleCandidate,
    TitlePattern,
)
from academic_platform.application.topic_workspace.model import (
    TopicDraft,
    TopicField,
)


def _draft(**overrides) -> TopicDraft:
    values = {field.value: "" for field in TopicField}
    values.update(overrides)
    return TopicDraft(project_key="p", values=values)


def test_empty_draft_produces_no_candidates() -> None:
    report = TitleBuilderEngine().generate(_draft())
    assert report.is_empty
    assert report.notes


def test_subject_only_produces_exploration_candidate() -> None:
    report = TitleBuilderEngine().generate(
        _draft(broad_subject="measurement invariance")
    )
    patterns = {c.pattern for c in report.candidates}
    assert TitlePattern.EXPLORATION_OF_SUBJECT in patterns


def test_subject_and_outcome_pattern() -> None:
    report = TitleBuilderEngine().generate(
        _draft(
            broad_subject="remote work",
            potential_outcomes="team cohesion",
        )
    )
    patterns = {c.pattern for c in report.candidates}
    assert TitlePattern.SUBJECT_AND_OUTCOME in patterns
    assert TitlePattern.EFFECT_OF_X_ON_Y in patterns
    assert TitlePattern.ASSOCIATION_BETWEEN_X_AND_Y in patterns


def test_subject_in_population_pattern() -> None:
    report = TitleBuilderEngine().generate(
        _draft(broad_subject="measurement invariance", population="adults")
    )
    patterns = {c.pattern for c in report.candidates}
    assert TitlePattern.SUBJECT_IN_POPULATION in patterns


def test_comparison_pattern() -> None:
    report = TitleBuilderEngine().generate(
        _draft(
            broad_subject="remote work",
            population="software teams",
            potential_outcomes="team cohesion",
        )
    )
    patterns = {c.pattern for c in report.candidates}
    assert TitlePattern.COMPARISON_ACROSS_GROUPS in patterns


def test_instrument_development_pattern() -> None:
    report = TitleBuilderEngine().generate(
        _draft(broad_subject="scale to measure resilience")
    )
    patterns = {c.pattern for c in report.candidates}
    assert TitlePattern.DEVELOPMENT_OF_INSTRUMENT in patterns


def test_methodological_study_pattern() -> None:
    report = TitleBuilderEngine().generate(
        _draft(broad_subject="methodology of measurement invariance")
    )
    patterns = {c.pattern for c in report.candidates}
    assert TitlePattern.METHODOLOGICAL_STUDY in patterns


def test_candidates_sorted_by_alignment() -> None:
    report = TitleBuilderEngine().generate(
        _draft(
            broad_subject="remote work",
            research_problem="a practical problem in distributed teams",
            potential_outcomes="team cohesion",
            population="software teams",
            context="remote-first companies",
        )
    )
    scores = [c.alignment.score for c in report.candidates]
    assert scores == sorted(scores, reverse=True)


def test_max_candidates_respected() -> None:
    report = TitleBuilderEngine(max_candidates=2).generate(
        _draft(
            broad_subject="remote work",
            potential_outcomes="team cohesion",
        )
    )
    assert report.candidate_count <= 2


def test_max_candidates_override_respected() -> None:
    report = TitleBuilderEngine(max_candidates=10).generate(
        _draft(
            broad_subject="remote work",
            potential_outcomes="team cohesion",
        ),
        max_candidates=1,
    )
    assert report.candidate_count <= 1


def test_max_candidates_must_be_positive() -> None:
    with pytest.raises(TitleBuilderError):
        TitleBuilderEngine(max_candidates=0)


def test_pattern_exception_is_wrapped() -> None:
    def _bad(_draft: TopicDraft):
        raise RuntimeError("boom")

    engine = TitleBuilderEngine(patterns=(_bad,))
    with pytest.raises(TitleBuilderError):
        engine.generate(_draft(broad_subject="x"))


def test_candidate_fields_populated() -> None:
    report = TitleBuilderEngine().generate(
        _draft(broad_subject="remote work")
    )
    for candidate in report.candidates:
        assert isinstance(candidate, TitleCandidate)
        assert candidate.identifier
        assert candidate.title
        assert candidate.rationale
        assert candidate.strengths
        assert candidate.problems
        assert candidate.assumptions
        assert candidate.alignment.score >= 0.0