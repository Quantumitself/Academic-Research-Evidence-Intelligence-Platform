"""Tests for the DocumentMetadata model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentMetadata,
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


def test_create_and_read(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        metadata = DocumentMetadata(
            document_id=document_id,
            title="Paper",
            year=2023,
            doi="10.1000/xyz",
            extraction_confidence=0.8,
        )
        session.add(metadata)
        session.flush()
    with database.session() as session:
        loaded = session.query(DocumentMetadata).one()
        assert loaded.title == "Paper"
        assert loaded.year == 2023
        assert loaded.extraction_confidence == 0.8


def test_unique_per_document(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        session.add(DocumentMetadata(document_id=document_id))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(DocumentMetadata(document_id=document_id))


def test_confidence_range_enforced(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                DocumentMetadata(document_id=document_id, extraction_confidence=1.5)
            )
            

def test_cascade_delete(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        session.add(DocumentMetadata(document_id=document_id))
    with database.session() as session:
        asset = session.get(DocumentAsset, document_id)
        assert asset is not None
        session.delete(asset)
    with database.session() as session:
        assert session.query(DocumentMetadata).count() == 0