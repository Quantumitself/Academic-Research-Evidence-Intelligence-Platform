"""Tests for the document duplicate detector."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.deduplication.detector import (
    DocumentDuplicateDetector,
    DuplicateSignal,
)
from academic_platform.application.deduplication.policy import DuplicatePolicy
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentMetadata,
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


def _detector(database: Database, policy: DuplicatePolicy | None = None):
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield DocumentDuplicateDetector(repositories, policy)


def _seed_document(
    database: Database,
    *,
    key: str,
    display_name: str,
    checksum: str,
    authors: tuple[str, ...] = (),
) -> int:
    with database.session() as session:
        row = DocumentAsset(
            key=key,
            display_name=display_name,
            original_filename=display_name,
            location=f"/tmp/{key}.pdf",
            checksum_sha256=checksum,
        )
        session.add(row)
        session.flush()
        if authors:
            session.add(
                DocumentMetadata(
                    document_id=row.id,
                    authors_json=json.dumps(list(authors)),
                )
            )
        return row.id


def test_no_match_on_empty_library(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        decision = detector.evaluate(checksum_sha256="0" * 64)
        assert decision.is_duplicate is False
        assert decision.match_count == 0


def test_match_by_checksum(database: Database) -> None:
    _seed_document(
        database, key="doc-1", display_name="Paper", checksum="0" * 64
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        decision = detector.evaluate(checksum_sha256="0" * 64)
        assert decision.is_duplicate is True
        assert decision.decisive_signal is DuplicateSignal.CHECKSUM
        assert decision.existing_key == "doc-1"


def test_checksum_is_decisive_even_without_metadata(database: Database) -> None:
    _seed_document(
        database, key="doc-1", display_name="Paper", checksum="1" * 64
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        decision = detector.evaluate(
            checksum_sha256="1" * 64,
            title="Unrelated Title",
            authors=("Unrelated Author",),
        )
        assert decision.is_duplicate is True
        assert decision.decisive_signal is DuplicateSignal.CHECKSUM


def test_exclude_document_key(database: Database) -> None:
    _seed_document(
        database, key="doc-1", display_name="Paper", checksum="2" * 64
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        decision = detector.evaluate(
            checksum_sha256="2" * 64, exclude_document_key="doc-1"
        )
        assert decision.is_duplicate is False


def test_no_match_when_checksum_disabled(database: Database) -> None:
    _seed_document(
        database, key="doc-1", display_name="Paper", checksum="3" * 64
    )
    policy = DuplicatePolicy(use_checksum=False)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories, policy)
        decision = detector.evaluate(checksum_sha256="3" * 64)
        assert decision.is_duplicate is False


def test_title_match_requires_authors_by_default(database: Database) -> None:
    _seed_document(
        database,
        key="doc-1",
        display_name="A Study of Things",
        checksum="4" * 64,
        authors=("A. Author",),
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        # Title matches, but authors do not.
        decision = detector.evaluate(
            title="A Study of Things",
            authors=("B. Author",),
        )
        assert decision.is_duplicate is False


def test_title_match_with_matching_authors(database: Database) -> None:
    _seed_document(
        database,
        key="doc-1",
        display_name="A Study of Things",
        checksum="5" * 64,
        authors=("A. Author", "B. Author"),
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        decision = detector.evaluate(
            title="A Study of Things",
            authors=("B. Author", "A. Author"),
        )
        assert decision.is_duplicate is True
        assert decision.decisive_signal is DuplicateSignal.TITLE


def test_title_match_requires_exact_normalized_title(database: Database) -> None:
    _seed_document(
        database,
        key="doc-1",
        display_name="A Study of Things",
        checksum="6" * 64,
        authors=("A. Author",),
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        # Different title; no match.
        decision = detector.evaluate(
            title="A Study of Other Things",
            authors=("A. Author",),
        )
        assert decision.is_duplicate is False


def test_title_normalization_handles_punctuation_and_case(database: Database) -> None:
    _seed_document(
        database,
        key="doc-1",
        display_name="A Study: Of Things!",
        checksum="7" * 64,
        authors=("A. Author",),
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories)
        decision = detector.evaluate(
            title="A STUDY of things",
            authors=("A. Author",),
        )
        assert decision.is_duplicate is True


def test_metadata_disabled_skips_title_match(database: Database) -> None:
    _seed_document(
        database,
        key="doc-1",
        display_name="A Study",
        checksum="8" * 64,
    )
    policy = DuplicatePolicy(use_checksum=False, use_metadata=False)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories, policy)
        decision = detector.evaluate(title="A Study")
        assert decision.is_duplicate is False


def test_require_author_match_false_allows_title_only(database: Database) -> None:
    _seed_document(
        database,
        key="doc-1",
        display_name="A Study",
        checksum="9" * 64,
    )
    policy = DuplicatePolicy(require_author_match=False)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        detector = DocumentDuplicateDetector(repositories, policy)
        decision = detector.evaluate(title="A Study")
        assert decision.is_duplicate is True
        assert decision.decisive_signal is DuplicateSignal.TITLE