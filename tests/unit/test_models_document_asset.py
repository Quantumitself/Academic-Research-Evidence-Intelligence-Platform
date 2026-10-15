"""Tests for the DocumentAsset model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import DocumentAsset


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


_CHECKSUM = "0" * 64


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        asset = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256=_CHECKSUM,
        )
        session.add(asset)
        session.flush()
        identifier = asset.id
    with database.session() as session:
        loaded = session.get(DocumentAsset, identifier)
        assert loaded is not None
        assert loaded.storage_mode == "managed_copy"
        assert loaded.processing_state == "pending"
        assert loaded.ocr_state == "not_required"
        assert loaded.missing == 0


def test_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(key="doc-1", location="/tmp/a.pdf", checksum_sha256=_CHECKSUM)
        )
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-1", location="/tmp/b.pdf", checksum_sha256="1" * 64
                )
            )


def test_invalid_storage_mode_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-1",
                    location="/tmp/a.pdf",
                    checksum_sha256=_CHECKSUM,
                    storage_mode="bogus",
                )
            )


def test_invalid_processing_state_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-1",
                    location="/tmp/a.pdf",
                    checksum_sha256=_CHECKSUM,
                    processing_state="bogus",
                )
            )


def test_invalid_ocr_state_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-1",
                    location="/tmp/a.pdf",
                    checksum_sha256=_CHECKSUM,
                    ocr_state="bogus",
                )
            )