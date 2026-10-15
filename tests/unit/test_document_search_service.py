"""Tests for the in-document search service."""

from __future__ import annotations

import pytest

from academic_platform.application.document_search.errors import (
    DocumentSearchError,
    DocumentSearchNotFoundError,
)
from academic_platform.application.document_search.service import (
    DocumentSearchService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentChunk,
)
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed(database: Database, chunks: list[tuple[int, int, str]]) -> None:
    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        for chunk_index, page_number, content in chunks:
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    content=content,
                )
            )


def test_empty_query_returns_empty(database: Database) -> None:
    _seed(database, [(0, 1, "Content about measurement.")])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        result = service.search("doc-1", "")
        assert result.match_count == 0


def test_literal_search(database: Database) -> None:
    _seed(
        database,
        [
            (0, 1, "The study examined measurement invariance across groups."),
            (1, 2, "Results indicated reliability for the scale."),
        ],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        result = service.search("doc-1", "invariance")
        assert result.match_count == 1
        match = result.matches[0]
        assert match.page_number == 1
        assert match.match_text.lower() == "invariance"
        assert "[[" in match.snippet and "]]" in match.snippet


def test_case_insensitive_by_default(database: Database) -> None:
    _seed(database, [(0, 1, "Content about Invariance.")])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        assert service.search("doc-1", "invariance").match_count == 1


def test_case_sensitive_mode(database: Database) -> None:
    _seed(database, [(0, 1, "Content about Invariance.")])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        assert service.search("doc-1", "invariance", case_sensitive=True).match_count == 0
        assert service.search("doc-1", "Invariance", case_sensitive=True).match_count == 1


def test_regex_mode(database: Database) -> None:
    _seed(database, [(0, 1, "Call 1234 or 5678.")])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        result = service.search("doc-1", r"\d{4}", use_regex=True)
        assert result.match_count == 2


def test_invalid_regex_raises(database: Database) -> None:
    _seed(database, [(0, 1, "Content.")])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        with pytest.raises(DocumentSearchError):
            service.search("doc-1", "(", use_regex=True)


def test_unknown_document_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        with pytest.raises(DocumentSearchNotFoundError):
            service.search("missing", "text")


def test_limit_truncates(database: Database) -> None:
    _seed(database, [(0, 1, "alpha " * 100)])
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories, default_limit=10)
        result = service.search("doc-1", "alpha")
        assert result.match_count == 10
        assert result.truncated is True


def test_pages_with_matches_reported(database: Database) -> None:
    _seed(
        database,
        [
            (0, 1, "First page has keyword."),
            (1, 2, "Second page has keyword."),
            (2, 3, "Third page has keyword."),
        ],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        result = service.search("doc-1", "keyword")
        assert result.pages_with_matches == (1, 2, 3)


def test_snippet_contains_context(database: Database) -> None:
    _seed(
        database,
        [(0, 1, "The word alpha appears inside a reasonably long sentence.")],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentSearchService(repositories)
        result = service.search("doc-1", "alpha")
        snippet = result.matches[0].snippet
        assert "reasonably" in snippet
        assert snippet.count("[[") == 1
        assert snippet.count("]]") == 1