"""Specifications for the evidence and analysis repositories."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import (
    AnalysisRun,
    EvidenceRecord,
)
from academic_platform.infrastructure.repositories.specification import Specification


class EvidenceByDocument(Specification[EvidenceRecord]):
    """Matches evidence records belonging to a document."""

    def __init__(self, document_id: int) -> None:
        self._document_id = document_id

    def to_expression(self, entity: type[EvidenceRecord]):
        return entity.document_id == self._document_id


class EvidenceByType(Specification[EvidenceRecord]):
    """Matches evidence records of a specific type."""

    def __init__(self, evidence_type: str) -> None:
        self._evidence_type = evidence_type

    def to_expression(self, entity: type[EvidenceRecord]):
        return entity.evidence_type == self._evidence_type


class EvidenceByVerification(Specification[EvidenceRecord]):
    """Matches evidence records in a specific verification state."""

    def __init__(self, verification_status: str) -> None:
        self._status = verification_status

    def to_expression(self, entity: type[EvidenceRecord]):
        return entity.verification_status == self._status


class EvidenceAwaitingReview(Specification[EvidenceRecord]):
    """Matches evidence records that require human review.

    A record requires review when its verification status is ``ai_proposed``
    or ``uncertain``. Records that are verified, rejected, or missing are
    not part of the pending-review queue.
    """

    def to_expression(self, entity: type[EvidenceRecord]):
        return entity.verification_status.in_(("ai_proposed", "uncertain"))


class AnalysisByType(Specification[AnalysisRun]):
    """Matches analysis runs of a specific type."""

    def __init__(self, analysis_type: str) -> None:
        self._analysis_type = analysis_type

    def to_expression(self, entity: type[AnalysisRun]):
        return entity.analysis_type == self._analysis_type


class AnalysisSucceeded(Specification[AnalysisRun]):
    """Matches analysis runs that completed successfully."""

    def to_expression(self, entity: type[AnalysisRun]):
        return entity.status == "succeeded"