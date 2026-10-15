"""Tests for the evidence repositories."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    EvidenceExtractionRun,
    EvidenceRecord,
)
from academic_platform.infrastructure.database.schemas import (
    EvidenceRecordCreate,
)
from academic_platform.infrastructure.repositories.evidence_repository import (
    EvidenceExtractionRunRepository,
    EvidenceRecordRepository,
    SynthesisReportRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_document(database: Database) -> int:
    with database.session() as session:
        asset = DocumentAsset(
            key="doc-1", location="/tmp/a.pdf", checksum_sha256="0" * 64
        )
        session.add(asset)
        session.flush()
        return asset.id


def test_create_and_list_for_document(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        repo = EvidenceRecordRepository(session)
        repo.create(
            EvidenceRecordCreate(
                document_id=document_id,
                evidence_type="sample_size",
                reported_value_json="120",
            )
        )
        repo.create(
            EvidenceRecordCreate(
                document_id=document_id,
                evidence_type="population",
                reported_value_json='"adults"',
            )
        )
    with database.session() as session:
        repo = EvidenceRecordRepository(session)
        records = repo.list_for_document(document_id)
        assert len(records) == 2


def test_list_awaiting_review(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        repo = EvidenceRecordRepository(session)
        repo.create(
            EvidenceRecordCreate(
                document_id=document_id,
                evidence_type="sample_size",
                verification_status="user_verified",
            )
        )
        repo.create(
            EvidenceRecordCreate(
                document_id=document_id,
                evidence_type="population",
                verification_status="ai_proposed",
            )
        )
    with database.session() as session:
        repo = EvidenceRecordRepository(session)
        pending = repo.list_awaiting_review()
        assert len(pending) == 1


def test_count_for_document(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        repo = EvidenceRecordRepository(session)
        for evidence_type in ("sample_size", "population"):
            repo.create(
                EvidenceRecordCreate(
                    document_id=document_id,
                    evidence_type=evidence_type,
                )
            )
    with database.session() as session:
        repo = EvidenceRecordRepository(session)
        assert repo.count_for_document(document_id) == 2


def test_run_lifecycle(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        repo = EvidenceExtractionRunRepository(session)
        run = EvidenceExtractionRun(
            document_id=document_id,
            status="running",
            method="rule_based",
            started_at=dt.datetime(2024, 1, 1, 12, 0, 0),
        )
        repo.add(run)
        run_id = run.id
    with database.session() as session:
        repo = EvidenceExtractionRunRepository(session)
        updated = repo.mark_finished(
            run_id,
            status="succeeded",
            finished_at=dt.datetime(2024, 1, 1, 12, 0, 5),
            duration_ms=5000,
            records_count=2,
        )
        assert updated.status == "succeeded"
        assert updated.records_count == 2


def test_latest_succeeded_run(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        repo = EvidenceExtractionRunRepository(session)
        for index, status in enumerate(["failed", "succeeded", "succeeded"]):
            repo.add(
                EvidenceExtractionRun(
                    document_id=document_id,
                    status=status,
                    method="rule_based",
                    started_at=dt.datetime(2024, 1, 1, 12, index, 0),
                )
            )
    with database.session() as session:
        repo = EvidenceExtractionRunRepository(session)
        latest = repo.latest_succeeded(document_id)
        assert latest is not None
        # The second succeeded run started later; it must be returned.
        assert latest.started_at.hour == 12
        assert latest.started_at.minute == 2


def test_synthesis_repository_latest(database: Database) -> None:
    from academic_platform.infrastructure.database.models import Collection
    from academic_platform.infrastructure.database.schemas import (
        SynthesisReportCreate,
    )

    with database.session() as session:
        collection = Collection(key="c1")
        session.add(collection)
        session.flush()
        collection_id = collection.id
    with database.session() as session:
        repo = SynthesisReportRepository(session)
        repo.create(
            SynthesisReportCreate(
                collection_id=collection_id,
                report_kind="narrative",
                title="First",
            )
        )
        repo.create(
            SynthesisReportCreate(
                collection_id=collection_id,
                report_kind="narrative",
                title="Second",
            )
        )
    with database.session() as session:
        repo = SynthesisReportRepository(session)
        latest = repo.latest_for_collection(collection_id)
        assert latest is not None
        assert latest.title == "Second"