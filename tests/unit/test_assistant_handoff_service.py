"""Tests for the assistant handoff service."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.assistant_handoff.errors import (
    AssistantHandoffNotFoundError,
)
from academic_platform.application.assistant_handoff.model import (
    HandoffOptions,
)
from academic_platform.application.assistant_handoff.service import (
    AssistantHandoffService,
)
from academic_platform.application.assistant_handoff.store import HandoffStore
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
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
    key: str = "doc-1",
    page_count: int = 3,
    title: str | None = None,
    authors: tuple[str, ...] = (),
    year: int | None = None,
    abstract: str | None = None,
    chunks: list[tuple[int, int, str]] | None = None,
    annotations: list[tuple[str, int, str, str]] | None = None,
) -> int:
    with database.session() as session:
        document = DocumentAsset(
            key=key,
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
            page_count=page_count,
        )
        session.add(document)
        session.flush()
        if title or authors or year is not None or abstract:
            session.add(
                DocumentMetadata(
                    document_id=document.id,
                    title=title,
                    authors_json=json.dumps(list(authors)) if authors else None,
                    year=year,
                    abstract=abstract,
                )
            )
        for chunk_index, page_number, content in chunks or []:
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    content=content,
                )
            )
        for kind, page_number, body, excerpt in annotations or []:
            session.add(
                Annotation(
                    document_id=document.id,
                    kind=kind,
                    page_number=page_number,
                    body=body,
                    text_excerpt=excerpt,
                )
            )
        session.flush()
        return document.id


def _service(database: Database) -> AssistantHandoffService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return AssistantHandoffService(repositories, store=HandoffStore())


def test_build_handoff_includes_metadata(database: Database) -> None:
    _seed_document(
        database,
        title="A Study",
        authors=("A. Author", "B. Author"),
        year=2020,
        abstract="An abstract.",
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        handoff = service.build_handoff("doc-1")
        assert handoff.title == "A Study"
        assert handoff.authors == ("A. Author", "B. Author")
        assert handoff.year == 2020
        assert handoff.abstract == "An abstract."


def test_build_handoff_includes_page_excerpt(database: Database) -> None:
    _seed_document(
        database,
        chunks=[
            (0, 1, "Page one text."),
            (1, 2, "Page two text about invariance."),
            (2, 3, "Page three text."),
        ],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        handoff = service.build_handoff("doc-1", current_page=2)
        assert "invariance" in handoff.page_text_excerpt
        assert handoff.current_page == 2
        assert handoff.page_count == 3


def test_build_handoff_omits_excerpt_when_disabled(database: Database) -> None:
    _seed_document(
        database,
        chunks=[(0, 1, "Page one text.")],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        handoff = service.build_handoff(
            "doc-1",
            current_page=1,
            options=HandoffOptions(include_current_page_text=False),
        )
        assert handoff.page_text_excerpt == ""


def test_build_handoff_includes_annotations(database: Database) -> None:
    _seed_document(
        database,
        annotations=[
            ("note", 1, "A note.", ""),
            ("highlight", 2, "", "Highlighted text"),
            ("bookmark", 3, "", ""),
        ],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        handoff = service.build_handoff(
            "doc-1",
            options=HandoffOptions(include_annotations=True),
        )
        assert len(handoff.annotations) == 3


def test_build_handoff_omits_annotations_when_disabled(database: Database) -> None:
    _seed_document(
        database,
        annotations=[("note", 1, "A note.", "")],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        handoff = service.build_handoff("doc-1")
        assert handoff.annotations == ()


def test_build_handoff_falls_back_to_display_name(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        handoff = service.build_handoff("doc-1")
        assert handoff.title == "Paper"


def test_build_handoff_unknown_document_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories)
        with pytest.raises(AssistantHandoffNotFoundError):
            service.build_handoff("missing")


def test_handoff_stored(database: Database) -> None:
    _seed_document(database)
    store = HandoffStore()
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories, store=store)
        service.build_handoff("doc-1")
    assert store.get("doc-1") is not None
    assert store.latest() is not None


def test_excerpt_truncated(database: Database) -> None:
    _seed_document(
        database,
        chunks=[(0, 1, "word " * 2000)],
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AssistantHandoffService(repositories, excerpt_length=100)
        handoff = service.build_handoff("doc-1", current_page=1)
        assert len(handoff.page_text_excerpt) <= 200
        assert handoff.page_text_excerpt.endswith("…")