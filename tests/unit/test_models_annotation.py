"""Tests for the Annotation model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import Annotation, DocumentAsset


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


def test_create_note(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        annotation = Annotation(
            document_id=document_id,
            kind="note",
            page_number=3,
            body="Important point",
        )
        session.add(annotation)
        session.flush()
        identifier = annotation.id
    with database.session() as session:
        loaded = session.get(Annotation, identifier)
        assert loaded is not None
        assert loaded.kind == "note"
        assert loaded.body == "Important point"


def test_create_highlight_with_color(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        session.add(
            Annotation(
                document_id=document_id,
                kind="highlight",
                page_number=2,
                text_excerpt="excerpt",
                color="yellow",
            )
        )


def test_invalid_kind_rejected(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                Annotation(document_id=document_id, kind="bogus")
            )


def test_invalid_color_rejected(database: Database) -> None:
    document_id = _seed_document(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                Annotation(document_id=document_id, kind="highlight", color="bogus")
            )


def test_cascade_delete(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        session.add(Annotation(document_id=document_id, kind="bookmark"))
    with database.session() as session:
        asset = session.get(DocumentAsset, document_id)
        assert asset is not None
        session.delete(asset)
    with database.session() as session:
        assert session.query(Annotation).count() == 0