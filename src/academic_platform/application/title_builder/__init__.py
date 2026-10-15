"""Rules-based research title builder.

This subpackage owns the deterministic rules that generate and evaluate
candidate research titles from a topic draft:

- ``TitlePattern`` — the closed set of title templates.
- ``TitleCandidate`` — an immutable title candidate with its rationale,
  strengths, problems, assumptions, and alignment score.
- ``TitleAlignmentReport`` — the alignment report produced by the
  evaluator.
- ``TitleBuilderEngine`` — the engine that generates candidates from a
  draft.
- ``TitleBuilderService`` — the application service that persists the
  candidates against a research project.
- ``TitleBuilderError`` and subclasses — typed errors.

The engine is a pure function over its inputs. It never persists
anything, never calls an AI provider, and never emits a candidate whose
fields could not be derived from the draft. The service is the only
component that writes; it stores candidates in the research title
candidate repository.
"""

from academic_platform.application.title_builder.engine import (
    TitleBuilderEngine,
)
from academic_platform.application.title_builder.errors import (
    TitleBuilderError,
    TitleBuilderNotFoundError,
    TitleBuilderValidationError,
)
from academic_platform.application.title_builder.model import (
    TitleAlignmentReport,
    TitleCandidate,
    TitlePattern,
    TitleState,
)
from academic_platform.application.title_builder.service import (
    TitleBuilderService,
)

__all__ = [
    "TitleAlignmentReport",
    "TitleBuilderEngine",
    "TitleBuilderError",
    "TitleBuilderNotFoundError",
    "TitleBuilderService",
    "TitleBuilderValidationError",
    "TitleCandidate",
    "TitlePattern",
    "TitleState",
]