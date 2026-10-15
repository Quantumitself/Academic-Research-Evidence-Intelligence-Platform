"""Tests for the FTS5 query service."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
    Publication,
)
from academic_platform.infrastructure.full_text_search.errors import (
    FtsQueryError,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
)
from academic_platform.infrastructure.full_text_search.query import (
    FtsQueryService,
    SNIPPET_END_MARKER,
    SNIPPET_START_MARKER,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed(database: Database) -> None:
    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="The study examined measurement invariance across groups.",
            ),
            DocumentChunk(
                document_id=document.id,
                chunk_index=1,
                page_number=2,
                content="Results indicated strong reliability for the scale.",
            ),
        ]
        session.add_all(chunks)
        session.flush()
        indexer = FtsIndexer(session)
        indexer.index_document(document, chunks)

        publication = Publication(
            key="pub-1",
            title="A Study of Measurement",
            abstract="We investigate measurement invariance in detail.",
            venue="Journal of Things",
        )
        session.add(publication)
        session.flush()
        indexer.index_publication(publication)

        annotation = Annotation(
            document_id=document.id,
            kind="note",
            page_number=3,
            body="Key finding: invariance holds for the scale.",
        )
        session.add(annotation)
        session.flush()
        indexer.index_annotation(annotation, document.key)


def test_search_documents_returns_hits(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_documents("measurement")
        assert results
        assert results[0].domain == "document"
        assert results[0].identifier == "doc-1"


def test_search_documents_invalid_query(database: Database) -> None:
    with database.session() as session:
        service = FtsQueryService(session)
        with pytest.raises(FtsQueryError):
            service.search_documents("")


def test_search_documents_invalid_snippet_column(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        with pytest.raises(FtsQueryError):
            service.search_documents("measurement", snippet_column="bogus")


def test_search_documents_snippet_markers(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_documents("measurement")
        assert results
        snippet = results[0].snippet.text
        assert SNIPPET_START_MARKER in snippet
        assert SNIPPET_END_MARKER in snippet
        # The plain helper removes the markers.
        assert SNIPPET_START_MARKER not in results[0].snippet.plain()


def test_search_publications(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_publications("invariance")
        assert results
        assert results[0].domain == "publication"


def test_search_notes(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_notes("invariance")
        assert results
        assert results[0].domain == "note"
        assert results[0].metadata.get("document_key") == "doc-1"


def test_search_all_merges_results(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_all("invariance")
        domains = {result.domain for result in results}
        assert "document" in domains
        assert "publication" in domains
        assert "note" in domains


def test_search_all_orders_by_rank(database: Database) -> None:
    _seed(database)
    with database.session() as session:
        service = FtsQueryService(session)
        results = service.search_all("measurement")
        ranks = [result.rank for result in results]
        assert ranks == sorted(ranks)