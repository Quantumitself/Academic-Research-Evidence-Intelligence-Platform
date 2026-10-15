"""Tests for the evidence models."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    EvidenceExtractionRun,
    EvidenceRecord,
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
            key="doc-1",
            location="/tmp/a.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(asset)
        session.flush()
        return asset.id


def test_create_evidence_record(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        record = EvidenceRecord(
            document_id=document_id,
            evidence_type="sample_size",
            reported_value_json="120",
        )
        session.add(record)
        session.flush()
        identifier = record.id
    with database.session() as session:
        loaded = session.get(EvidenceRecord, identifier)
        assert loaded is not None
        assert loaded.verification_status == "ai_proposed"
        assert loaded.extraction_method == "rule_based"


def test_invalid_evidence_type_rejected(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                EvidenceRecord(
                    document_id=document_id,
                    evidence_type="bogus",
                )
            )


def test_invalid_verification_rejected(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                EvidenceRecord(
                    document_id=document_id,
                    evidence_type="sample_size",
                    verification_status="bogus",
                )
            )


def test_run_lifecycle(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        run = EvidenceExtractionRun(
            document_id=document_id,
            status="running",
            method="rule_based",
            started_at=dt.datetime(2024, 1, 1, 12, 0, 0),
        )
        session.add(run)
        session.flush()
        identifier = run.id
    with database.session() as session:
        loaded = session.get(EvidenceExtractionRun, identifier)
        assert loaded is not None
        assert loaded.status == "running"


def test_invalid_run_status_rejected(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                EvidenceExtractionRun(
                    document_id=document_id,
                    status="bogus",
                    method="rule_based",
                    started_at=dt.datetime(2024, 1, 1),
                )
            )


def test_invalid_run_method_rejected(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                EvidenceExtractionRun(
                    document_id=document_id,
                    status="running",
                    method="bogus",
                    started_at=dt.datetime(2024, 1, 1),
                )
            )