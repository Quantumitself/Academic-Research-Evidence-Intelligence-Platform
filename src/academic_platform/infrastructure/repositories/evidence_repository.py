"""Repositories for evidence records, extraction runs, and synthesis reports."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    EvidenceExtractionRun,
    EvidenceRecord,
    SynthesisReport,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class EvidenceRecordRepository(Repository[EvidenceRecord]):
    """Repository for the ``evidence_record`` table."""

    entity = EvidenceRecord

    def list_for_document(self, document_id: int) -> list[EvidenceRecord]:
        """Return the evidence records of a document ordered by type."""
        statement = (
            select(EvidenceRecord)
            .where(EvidenceRecord.document_id == document_id)
            .order_by(EvidenceRecord.evidence_type, EvidenceRecord.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_document failed: {exc}") from exc

    def list_for_run(self, run_id: int) -> list[EvidenceRecord]:
        """Return the evidence records produced by a specific extraction run."""
        statement = (
            select(EvidenceRecord)
            .where(EvidenceRecord.extraction_run_id == run_id)
            .order_by(EvidenceRecord.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_run failed: {exc}") from exc

    def list_awaiting_review(self) -> list[EvidenceRecord]:
        """Return evidence records that require human review."""
        statement = (
            select(EvidenceRecord)
            .where(EvidenceRecord.verification_status.in_(("ai_proposed", "uncertain")))
            .order_by(EvidenceRecord.document_id, EvidenceRecord.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_awaiting_review failed: {exc}") from exc

    def count_for_document(self, document_id: int) -> int:
        """Return the number of evidence records of a document."""
        statement = select(EvidenceRecord).where(
            EvidenceRecord.document_id == document_id
        )
        try:
            return len(list(self._session.execute(statement).scalars().all()))
        except SQLAlchemyError as exc:
            raise RepositoryError(f"count_for_document failed: {exc}") from exc


class EvidenceExtractionRunRepository(Repository[EvidenceExtractionRun]):
    """Repository for the ``evidence_extraction_run`` table."""

    entity = EvidenceExtractionRun

    def list_for_document(self, document_id: int) -> list[EvidenceExtractionRun]:
        """Return the extraction runs of a document, newest first."""
        statement = (
            select(EvidenceExtractionRun)
            .where(EvidenceExtractionRun.document_id == document_id)
            .order_by(EvidenceExtractionRun.started_at.desc(), EvidenceExtractionRun.id.desc())
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_document failed: {exc}") from exc

    def latest_succeeded(self, document_id: int) -> EvidenceExtractionRun | None:
        """Return the most recent successful extraction run for a document."""
        statement = (
            select(EvidenceExtractionRun)
            .where(
                EvidenceExtractionRun.document_id == document_id,
                EvidenceExtractionRun.status == "succeeded",
            )
            .order_by(EvidenceExtractionRun.started_at.desc(), EvidenceExtractionRun.id.desc())
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"latest_succeeded failed: {exc}") from exc

    def mark_finished(
        self,
        run_id: int,
        *,
        status: str,
        finished_at,
        duration_ms: int | None,
        records_count: int,
        error_message: str | None = None,
    ) -> EvidenceExtractionRun:
        """Record the outcome of an extraction run."""
        run = self.get_or_raise(run_id)
        run.status = status
        run.finished_at = finished_at
        run.duration_ms = duration_ms
        run.records_count = records_count
        run.error_message = error_message
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"mark_finished failed: {exc}") from exc
        return run


class SynthesisReportRepository(Repository[SynthesisReport]):
    """Repository for the ``synthesis_report`` table."""

    entity = SynthesisReport

    def list_for_collection(self, collection_id: int) -> list[SynthesisReport]:
        """Return the synthesis reports of a collection, newest first."""
        statement = (
            select(SynthesisReport)
            .where(SynthesisReport.collection_id == collection_id)
            .order_by(SynthesisReport.created_at.desc(), SynthesisReport.id.desc())
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_collection failed: {exc}") from exc

    def latest_for_collection(self, collection_id: int) -> SynthesisReport | None:
        """Return the most recent synthesis report for a collection."""
        statement = (
            select(SynthesisReport)
            .where(SynthesisReport.collection_id == collection_id)
            .order_by(SynthesisReport.created_at.desc(), SynthesisReport.id.desc())
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"latest_for_collection failed: {exc}") from exc

    def list_recent(self, *, limit: int = 25) -> list[SynthesisReport]:
        """Return the most recently created synthesis reports."""
        statement = (
            select(SynthesisReport)
            .order_by(SynthesisReport.created_at.desc(), SynthesisReport.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_recent failed: {exc}") from exc