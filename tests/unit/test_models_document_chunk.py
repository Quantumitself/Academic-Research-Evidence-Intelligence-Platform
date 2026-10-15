"""Tests for the DocumentChunk model."""

from __future__ import annotations

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentChunk,
)


def test_create_and_order() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            asset = DocumentAsset(
                key="doc-1", location="/tmp/a.pdf", checksum_sha256="0" * 64
            )
            session.add(asset)
            session.flush()
            document_id = asset.id
        with database.session() as session:
            session.add_all(
                [
                    DocumentChunk(
                        document_id=document_id,
                        chunk_index=1,
                        page_number=1,
                        content="second",
                    ),
                    DocumentChunk(
                        document_id=document_id,
                        chunk_index=0,
                        page_number=1,
                        content="first",
                    ),
                ]
            )
        with database.session() as session:
            chunks = (
                session.query(DocumentChunk)
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            assert [c.content for c in chunks] == ["first", "second"]
    finally:
        database.dispose()


def test_cascade_delete() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            asset = DocumentAsset(
                key="doc-1", location="/tmp/a.pdf", checksum_sha256="0" * 64
            )
            session.add(asset)
            session.flush()
            session.add(
                DocumentChunk(
                    document_id=asset.id,
                    chunk_index=0,
                    content="text",
                )
            )
        with database.session() as session:
            asset = session.get(DocumentAsset, 1)
            assert asset is not None
            session.delete(asset)
        with database.session() as session:
            assert session.query(DocumentChunk).count() == 0
    finally:
        database.dispose()