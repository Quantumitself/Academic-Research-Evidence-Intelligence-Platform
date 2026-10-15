"""Rules-based clarifying-question engine.

The engine inspects a topic draft and produces a bounded list of
focused clarifying questions. Each rule is a small function that reads
the draft and yields zero or one questions. The engine runs every rule,
sorts the results by priority, and returns the top ``max_questions``.

Design decisions
----------------
- The engine is a pure function. It never mutates the draft, never
  persists anything, and never calls an AI provider.
- Rules emit a question only when the missing information materially
  affects the next recommendation. Rules that would ask about
  information already present in the draft never fire.
- The engine bounds the number of returned questions. A long list of
  questions is a worse experience than a short, focused list.
- Questions are identified by a stable identifier derived from the
  target field and a rule-specific suffix so that the presentation
  layer can persist the user's dismissal of a specific question.
- The engine is deterministic. The same draft produces the same
  questions in the same order on every run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

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

_logger = logging.getLogger(__name__)

_DEFAULT_MAX_QUESTIONS = 8

Rule = Callable[[TopicDraft], ClarifyingQuestion | None]


class ClarifyingQuestionEngine:
    """Evaluate a topic draft and return focused clarifying questions."""

    def __init__(
        self,
        rules: tuple[Rule, ...] | None = None,
        *,
        max_questions: int = _DEFAULT_MAX_QUESTIONS,
    ) -> None:
        if max_questions < 1:
            raise ClarifyingQuestionError(
                "max_questions must be at least 1"
            )
        self._rules = rules if rules is not None else _default_rules()
        self._max_questions = max_questions

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(
        self,
        draft: TopicDraft,
        *,
        dismissed_identifiers: frozenset[str] = frozenset(),
        max_questions: int | None = None,
    ) -> list[ClarifyingQuestion]:
        """Return the clarifying questions appropriate to the draft.

        Parameters
        ----------
        draft:
            The current topic draft. The engine never mutates it.
        dismissed_identifiers:
            Identifiers of questions the user has already dismissed.
            Dismissed questions are excluded from the result.
        max_questions:
            Optional cap on the number of questions to return. When
            omitted, the engine's configured cap is used.

        Raises
        ------
        ClarifyingQuestionError
            If a rule raises an unexpected exception.
        """
        limit = self._max_questions if max_questions is None else max_questions
        if limit < 1:
            raise ClarifyingQuestionError(
                "max_questions must be at least 1"
            )
        questions: list[ClarifyingQuestion] = []
        for rule in self._rules:
            try:
                question = rule(draft)
            except Exception as exc:  # noqa: BLE001 - boundary
                raise ClarifyingQuestionError(
                    f"Clarifying-question rule raised: {exc}"
                ) from exc
            if question is None:
                continue
            if question.identifier in dismissed_identifiers:
                continue
            questions.append(question)
        questions.sort(key=lambda q: (q.priority, q.identifier))
        return questions[:limit]


# ----------------------------------------------------------------------
# Default rules
# ----------------------------------------------------------------------
def _default_rules() -> tuple[Rule, ...]:
    """Return the engine's built-in rule set."""
    return (
        _rule_broad_subject_present,
        _rule_broad_subject_scope,
        _rule_research_problem_present,
        _rule_research_problem_practical_or_theoretical,
        _rule_context_present,
        _rule_population_present,
        _rule_time_period_present,
        _rule_key_concepts_present,
        _rule_potential_outcomes_present,
        _rule_constraints_present,
        _rule_knowledge_level_present,
    )


def _rule_broad_subject_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.broad_subject:
        return None
    return ClarifyingQuestion(
        identifier="topic.scope.starting_point",
        category=QuestionCategory.SCOPE,
        target_field=TopicField.BROAD_SUBJECT.value,
        text="What general area of inquiry does the study address?",
        rationale=(
            "The topic is the starting point for every later decision. "
            "Without a broad subject, the assistant cannot suggest titles, "
            "search terms, or methodologies."
        ),
        priority=10,
        blocking=True,
        example_answer=(
            "For example: 'measurement invariance across cultures' or "
            "'the effect of remote work on team cohesion'."
        ),
    )


def _rule_broad_subject_scope(draft: TopicDraft) -> ClarifyingQuestion | None:
    if not draft.broad_subject:
        return None
    if _word_count(draft.broad_subject) >= 3:
        return None
    return ClarifyingQuestion(
        identifier="topic.scope.too_broad",
        category=QuestionCategory.SCOPE,
        target_field=TopicField.BROAD_SUBJECT.value,
        text=(
            "The topic you described is broad. Which specific aspect of it "
            "should the study focus on?"
        ),
        rationale=(
            "A very broad subject cannot be answered by a single study. "
            "Narrowing the scope makes the research question answerable."
        ),
        priority=15,
        blocking=False,
        example_answer=(
            "For example, from 'remote work' to 'the effect of remote work "
            "on team cohesion in software teams'."
        ),
    )


def _rule_research_problem_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.research_problem:
        return None
    return ClarifyingQuestion(
        identifier="topic.problem.missing",
        category=QuestionCategory.PROBLEM,
        target_field=TopicField.RESEARCH_PROBLEM.value,
        text=(
            "What practical or theoretical problem does the study address?"
        ),
        rationale=(
            "A research study is justified by the problem it addresses. "
            "The problem shapes the research question and the choice of "
            "methodology."
        ),
        priority=20,
        blocking=True,
        example_answer=(
            "For example: 'existing instruments are not validated in this "
            "population' or 'the field disagrees about the effect size'."
        ),
    )


def _rule_research_problem_practical_or_theoretical(
    draft: TopicDraft,
) -> ClarifyingQuestion | None:
    if not draft.research_problem:
        return None
    lowered = draft.research_problem.lower()
    markers = (
        "practical",
        "theoretical",
        "empirical",
        "applied",
        "conceptual",
    )
    if any(marker in lowered for marker in markers):
        return None
    if _word_count(draft.research_problem) >= 12:
        return None
    return ClarifyingQuestion(
        identifier="topic.problem.nature",
        category=QuestionCategory.PROBLEM,
        target_field=TopicField.RESEARCH_PROBLEM.value,
        text=(
            "Is the problem primarily practical, theoretical, or both?"
        ),
        rationale=(
            "The nature of the problem informs whether the study is applied "
            "or theoretical, which in turn affects the methodology."
        ),
        priority=25,
        blocking=False,
    )


def _rule_context_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.context:
        return None
    return ClarifyingQuestion(
        identifier="topic.context.missing",
        category=QuestionCategory.CONTEXT,
        target_field=TopicField.CONTEXT.value,
        text=(
            "In what setting or context will the study be conducted?"
        ),
        rationale=(
            "The setting affects sampling, instruments, and the "
            "generalizability of the findings."
        ),
        priority=30,
        blocking=False,
        example_answer=(
            "For example: 'a single university', 'three hospitals in an "
            "urban region', or 'remote teams across two continents'."
        ),
    )


def _rule_population_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.population:
        return None
    return ClarifyingQuestion(
        identifier="topic.population.missing",
        category=QuestionCategory.POPULATION,
        target_field=TopicField.POPULATION.value,
        text="Which population does the study concern?",
        rationale=(
            "The population determines the sampling strategy and the "
            "inclusion and exclusion criteria."
        ),
        priority=35,
        blocking=False,
        example_answer=(
            "For example: 'undergraduate students', 'patients with a "
            "specific diagnosis', or 'software engineers with at least "
            "two years of experience'."
        ),
    )


def _rule_time_period_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.time_period:
        return None
    return ClarifyingQuestion(
        identifier="topic.time.missing",
        category=QuestionCategory.TIME,
        target_field=TopicField.TIME_PERIOD.value,
        text="Does the study cover a specific time period?",
        rationale=(
            "A time period bounds the literature review and, for "
            "longitudinal studies, the observation window."
        ),
        priority=40,
        blocking=False,
        example_answer=(
            "For example: 'the last ten years' or 'since the 2020 policy "
            "change'."
        ),
    )


def _rule_key_concepts_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.key_concepts:
        return None
    return ClarifyingQuestion(
        identifier="topic.concepts.missing",
        category=QuestionCategory.CONCEPTS,
        target_field=TopicField.KEY_CONCEPTS.value,
        text=(
            "Which concepts or constructs are central to the study?"
        ),
        rationale=(
            "Named concepts are the basis for search terms and for the "
            "operational definitions the study requires."
        ),
        priority=45,
        blocking=False,
        example_answer=(
            "For example: 'measurement invariance', 'team cohesion', or "
            "'task interdependence'."
        ),
    )


def _rule_potential_outcomes_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.potential_outcomes:
        return None
    return ClarifyingQuestion(
        identifier="topic.outcomes.missing",
        category=QuestionCategory.OUTCOMES,
        target_field=TopicField.POTENTIAL_OUTCOMES.value,
        text="Which outcomes or variables will the study measure?",
        rationale=(
            "The outcomes determine the statistical analysis and the "
            "effect sizes that the study can estimate."
        ),
        priority=50,
        blocking=False,
        example_answer=(
            "For example: 'team performance ratings', 'self-reported "
            "well-being', or 'error rate'."
        ),
    )


def _rule_constraints_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.constraints:
        return None
    return ClarifyingQuestion(
        identifier="topic.constraints.missing",
        category=QuestionCategory.CONSTRAINTS,
        target_field=TopicField.CONSTRAINTS.value,
        text="Are there any constraints the study must respect?",
        rationale=(
            "Constraints such as time, ethics, or access shape the "
            "feasibility of the proposed methodology."
        ),
        priority=55,
        blocking=False,
        example_answer=(
            "For example: 'the study must complete within six months' or "
            "'access to the population is limited to a single site'."
        ),
    )


def _rule_knowledge_level_present(draft: TopicDraft) -> ClarifyingQuestion | None:
    if draft.knowledge_level:
        return None
    return ClarifyingQuestion(
        identifier="topic.knowledge.missing",
        category=QuestionCategory.KNOWLEDGE,
        target_field=TopicField.KNOWLEDGE_LEVEL.value,
        text=(
            "How familiar are you with this topic?"
        ),
        rationale=(
            "The assistant tailors its explanations to the user's "
            "familiarity with the topic and its methods."
        ),
        priority=60,
        blocking=False,
        example_answer=(
            "For example: 'I have read a few papers' or 'I have worked on "
            "this topic for several years'."
        ),
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _word_count(value: str) -> int:
    return len([token for token in value.split() if token])