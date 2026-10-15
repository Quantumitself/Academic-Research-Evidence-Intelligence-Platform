"""Tests for the rules-based clarifying-question engine."""

from __future__ import annotations

import pytest

from academic_platform.application.clarifying_questions.engine import (
    ClarifyingQuestionEngine,
)
from academic_platform.application.clarifying_questions.errors import (
    ClarifyingQuestionError,
)
from academic_platform.application.clarifying_questions.model import (
    ClarifyingQuestion,
    QuestionCategory,
)
from academic_platform.application.topic_workspace.model import (
    TopicDraft,
    TopicField,
)


def _draft(**overrides) -> TopicDraft:
    values = {field.value: "" for field in TopicField}
    values.update(overrides)
    return TopicDraft(project_key="p", values=values)


def test_empty_draft_produces_blocking_questions() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft())
    identifiers = {q.identifier for q in questions}
    assert "topic.scope.starting_point" in identifiers
    assert "topic.problem.missing" in identifiers
    blocking = [q for q in questions if q.blocking]
    assert len(blocking) >= 2


def test_engine_is_deterministic() -> None:
    engine = ClarifyingQuestionEngine()
    draft = _draft(broad_subject="remote work")
    first = [q.identifier for q in engine.evaluate(draft)]
    second = [q.identifier for q in engine.evaluate(draft)]
    assert first == second


def test_questions_sorted_by_priority() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft())
    priorities = [q.priority for q in questions]
    assert priorities == sorted(priorities)


def test_broad_subject_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(broad_subject="A specific subject"))
    identifiers = {q.identifier for q in questions}
    assert "topic.scope.starting_point" not in identifiers


def test_broad_subject_too_broad_rule_fires() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(broad_subject="work"))
    identifiers = {q.identifier for q in questions}
    assert "topic.scope.too_broad" in identifiers


def test_broad_subject_too_broad_rule_skipped_when_specific() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(
        _draft(broad_subject="remote work and team cohesion")
    )
    identifiers = {q.identifier for q in questions}
    assert "topic.scope.too_broad" not in identifiers


def test_problem_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(research_problem="A problem"))
    identifiers = {q.identifier for q in questions}
    assert "topic.problem.missing" not in identifiers


def test_problem_nature_rule_fires_when_short_and_unmarked() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(research_problem="Something is wrong"))
    identifiers = {q.identifier for q in questions}
    assert "topic.problem.nature" in identifiers


def test_problem_nature_rule_skipped_when_marked() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(
        _draft(research_problem="A practical problem in schools")
    )
    identifiers = {q.identifier for q in questions}
    assert "topic.problem.nature" not in identifiers


def test_problem_nature_rule_skipped_when_long() -> None:
    engine = ClarifyingQuestionEngine()
    long_problem = " ".join(["word"] * 20)
    questions = engine.evaluate(_draft(research_problem=long_problem))
    identifiers = {q.identifier for q in questions}
    assert "topic.problem.nature" not in identifiers


def test_context_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(context="A university"))
    identifiers = {q.identifier for q in questions}
    assert "topic.context.missing" not in identifiers


def test_population_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(population="Adults"))
    identifiers = {q.identifier for q in questions}
    assert "topic.population.missing" not in identifiers


def test_time_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(time_period="Last decade"))
    identifiers = {q.identifier for q in questions}
    assert "topic.time.missing" not in identifiers


def test_concepts_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(key_concepts="Concept A"))
    identifiers = {q.identifier for q in questions}
    assert "topic.concepts.missing" not in identifiers


def test_outcomes_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(potential_outcomes="Performance"))
    identifiers = {q.identifier for q in questions}
    assert "topic.outcomes.missing" not in identifiers


def test_constraints_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(constraints="Six months"))
    identifiers = {q.identifier for q in questions}
    assert "topic.constraints.missing" not in identifiers


def test_knowledge_rule_skipped_when_present() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft(knowledge_level="Experienced"))
    identifiers = {q.identifier for q in questions}
    assert "topic.knowledge.missing" not in identifiers


def test_dismissed_questions_excluded() -> None:
    engine = ClarifyingQuestionEngine()
    full = engine.evaluate(_draft())
    target = full[0].identifier
    filtered = engine.evaluate(
        _draft(), dismissed_identifiers=frozenset({target})
    )
    assert target not in {q.identifier for q in filtered}


def test_max_questions_respected() -> None:
    engine = ClarifyingQuestionEngine(max_questions=3)
    questions = engine.evaluate(_draft())
    assert len(questions) <= 3


def test_max_questions_override_respected() -> None:
    engine = ClarifyingQuestionEngine(max_questions=10)
    questions = engine.evaluate(_draft(), max_questions=2)
    assert len(questions) <= 2


def test_max_questions_must_be_positive() -> None:
    with pytest.raises(ClarifyingQuestionError):
        ClarifyingQuestionEngine(max_questions=0)


def test_rule_exception_is_wrapped() -> None:
    def _bad_rule(_draft: TopicDraft):
        raise RuntimeError("boom")

    engine = ClarifyingQuestionEngine(rules=(_bad_rule,))
    with pytest.raises(ClarifyingQuestionError):
        engine.evaluate(_draft())


def test_question_identifiers_stable() -> None:
    engine = ClarifyingQuestionEngine()
    questions = engine.evaluate(_draft())
    for question in questions:
        assert isinstance(question, ClarifyingQuestion)
        assert question.identifier
        assert question.target_field
        assert question.text
        assert question.rationale
        assert isinstance(question.category, QuestionCategory)