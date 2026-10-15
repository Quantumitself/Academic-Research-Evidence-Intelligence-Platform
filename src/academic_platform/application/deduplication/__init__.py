"""Duplicate detection for the personal library.

This subpackage owns the detection of duplicate documents across the
library. It exposes:

- ``DuplicatePolicy`` — an immutable description of the thresholds and
  signals the detector uses.
- ``DuplicateSignal`` — an enum of the individual signals the detector
  evaluates.
- ``DuplicateMatch`` — a value object describing a single match.
- ``DuplicateDecision`` — the outcome of evaluating a candidate against
  the library.
- ``DocumentDuplicateDetector`` — the application service that runs the
  detection against the document repository.

The subpackage never imports Qt. It may import from the repository
layer, the document processing layer, and the persistence schemas.
"""

from academic_platform.application.deduplication.detector import (
    DocumentDuplicateDetector,
    DuplicateDecision,
    DuplicateMatch,
    DuplicateSignal,
)
from academic_platform.application.deduplication.policy import DuplicatePolicy
from academic_platform.application.deduplication.errors import (
    DuplicateDetectionError,
)

__all__ = [
    "DocumentDuplicateDetector",
    "DuplicateDecision",
    "DuplicateDetectionError",
    "DuplicateMatch",
    "DuplicatePolicy",
    "DuplicateSignal",
]