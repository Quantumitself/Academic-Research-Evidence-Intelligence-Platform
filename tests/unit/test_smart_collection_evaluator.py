"""Tests for the smart-collection evaluator."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.smart_collections.evaluator import (
    SmartCollectionEvaluator,
)
from academic_platform.application.smart_collections.filter import (
    SmartCollectionFilter,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
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


def _seed_document(
    database: Database,
    *,
    key: str,
    display_name: str,
    location: str = "/tmp/paper.pdf",
    processing_state: str = "extracted",
    storage_mode: str = "managed_copy",
    missing: bool = False,
    title: str | None = None,
    authors: tuple[str, ...] = (),
    year: int | None = None,
    doi: str | None = None,
    annotation_count: int = 0,
) -> int:
    with database.session() as session:
        document = DocumentAsset(
            key=key,
            display_name=display_name,
            location=location,
            checksum_sha256="0" * 64,
            processing_state=processing_state,
            storage_mode=storage_mode,
            missing=1 if missing else 0,
        )
        session.add(document)
        session.flush()
        if title or authors or year is not None or doi:
            session.add(
                DocumentMetadata(
                    document_id=document.id,
                    title=title,
                    authors_json=json.dumps(list(authors)) if authors else None,
                    year=year,
                    doi=doi,
                )
            )
        for index in range(annotation_count):
            session.add(
                Annotation(
                    document_id=document.id,
                    kind="note",
                    page_number=1,
                    body=f"Note {index}",
                )
            )
        session.flush()
        return document.id


def _evaluator(database: Database) -> SmartCollectionEvaluator:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return SmartCollectionEvaluator(repositories)


def test_empty_filter_returns_all(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha")
    _seed_document(database, key="b", display_name="Beta")
    evaluator = _evaluator(database)
    items = evaluator.evaluate(SmartCollectionFilter())
    assert {item.item_identifier for item in items} == {"a", "b"}


def test_filter_by_processing_state(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", processing_state="extracted")
    _seed_document(database, key="b", display_name="Beta", processing_state="pending")
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(processing_states=frozenset({"pending"}))
    )
    assert [item.item_identifier for item in items] == ["b"]


def test_filter_by_extension(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", location="/tmp/a.pdf")
    _seed_document(database, key="b", display_name="Beta", location="/tmp/b.epub")
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(extensions=frozenset({".pdf"}))
    )
    assert [item.item_identifier for item in items] == ["a"]


def test_filter_by_storage_mode(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", storage_mode="managed_copy")
    _seed_document(
        database, key="b", display_name="Beta", storage_mode="referenced_file"
    )
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(storage_modes=frozenset({"referenced_file"}))
    )
    assert [item.item_identifier for item in items] == ["b"]


def test_filter_by_missing_flag(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", missing=False)
    _seed_document(database, key="b", display_name="Beta", missing=True)
    evaluator = _evaluator(database)
    items = evaluator.evaluate(SmartCollectionFilter(missing=True))
    assert [item.item_identifier for item in items] == ["b"]


def test_filter_by_year_range(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", year=2010)
    _seed_document(database, key="b", display_name="Beta", year=2020)
    _seed_document(database, key="c", display_name="Gamma", year=2030)
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(year_from=2015, year_to=2025)
    )
    assert [item.item_identifier for item in items] == ["b"]


def test_filter_by_title_contains(database: Database) -> None:
    _seed_document(
        database, key="a", display_name="Alpha", title="Measurement Study"
    )
    _seed_document(database, key="b", display_name="Beta", title="Other Study")
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(title_contains="measurement")
    )
    assert [item.item_identifier for item in items] == ["a"]


def test_filter_by_author_contains(database: Database) -> None:
    _seed_document(
        database,
        key="a",
        display_name="Alpha",
        authors=("A. Smith", "B. Jones"),
    )
    _seed_document(
        database,
        key="b",
        display_name="Beta",
        authors=("C. Brown",),
    )
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(author_contains="smith")
    )
    assert [item.item_identifier for item in items] == ["a"]


def test_filter_by_has_doi(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", doi="10.1000/xyz")
    _seed_document(database, key="b", display_name="Beta")
    evaluator = _evaluator(database)
    items = evaluator.evaluate(SmartCollectionFilter(has_doi=True))
    assert [item.item_identifier for item in items] == ["a"]


def test_filter_by_has_annotations(database: Database) -> None:
    _seed_document(
        database, key="a", display_name="Alpha", annotation_count=2
    )
    _seed_document(database, key="b", display_name="Beta")
    evaluator = _evaluator(database)
    items = evaluator.evaluate(
        SmartCollectionFilter(has_annotations=True)
    )
    assert [item.item_identifier for item in items] == ["a"]


def test_evaluate_json(database: Database) -> None:
    _seed_document(
        database, key="a", display_name="Alpha", processing_state="extracted"
    )
    _seed_document(
        database, key="b", display_name="Beta", processing_state="pending"
    )
    evaluator = _evaluator(database)
    items = evaluator.evaluate_json('{"processing_states": ["pending"]}')
    assert [item.item_identifier for item in items] == ["b"]


def test_limit_applied(database: Database) -> None:
    for index in range(5):
        _seed_document(
            database, key=f"doc-{index}", display_name=f"Doc {index}"
        )
    evaluator = _evaluator(database)
    items = evaluator.evaluate(SmartCollectionFilter(), limit=2)
    assert len(items) == 2