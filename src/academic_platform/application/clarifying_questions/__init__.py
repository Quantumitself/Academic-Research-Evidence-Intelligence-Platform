"""Rules-based clarifying-question engine.

This subpackage owns the deterministic rules that produce focused
clarifying questions for the research assistant's Topic & Problem
workflow:

- ``ClarifyingQuestion`` — an immutable question with its target field,
  rationale, and priority.
- ``QuestionCategory`` — the closed set of categories a question can
  belong to.
- ``ClarifyingQuestionEngine`` — the engine that evaluates a topic
  draft and returns the questions that should be asked.
- ``ClarifyingQuestionError`` — typed error.

The engine is a pure function over its inputs. It never persists
anything, never calls an AI provider, and never emits a question whose
answer would not change the workflow's next step.
"""

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

__all__ = [
    "ClarifyingQuestion",
    "ClarifyingQuestionEngine",
    "ClarifyingQuestionError",
    "QuestionCategory",
]