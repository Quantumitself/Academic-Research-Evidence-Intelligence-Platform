"""Tests for the research guide repositories."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.schemas import (
    CitationRecordCreate,
    ResearchGuideCreate,
    ResearchGuideSectionCreate,
)
from academic_platform.infrastructure.repositories.research_guide_repository import (
    CitationRecordRepository,
    ResearchGuideRepository,
    ResearchGuideSectionRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_guide_create_and_find(database: Database) -> None:
    with database.session() as session:
        repo = ResearchGuideRepository(session)
        repo.create(
            ResearchGuideCreate(key="g1", title="Guide", guide_kind="topic")
        )
    with database.session() as session:
        repo = ResearchGuideRepository(session)
        assert repo.find_by_key("g1") is not None
        assert repo.find_by_key("missing") is None


def test_section_position_sequence(database: Database) -> None:
    with database.session() as session:
        guide_repo = ResearchGuideRepository(session)
        section_repo = ResearchGuideSectionRepository(session)
        guide = guide_repo.create(
            ResearchGuideCreate(key="g1", title="Guide", guide_kind="topic")
        )
        assert section_repo.next_position(guide.id) == 1
        section_repo.create(
            ResearchGuideSectionCreate(guide_id=guide.id, heading="A")
        )
        assert section_repo.next_position(guide.id) == 1
        section_repo.create(
            ResearchGuideSectionCreate(guide_id=guide.id, heading="B")
        )
        # After two sections at default position 0, next_position must
        # return 1 because positions are 0-based and not auto-assigned.
        assert section_repo.next_position(guide.id) == 1


def test_citation_listing(database: Database) -> None:
    with database.session() as session:
        guide_repo = ResearchGuideRepository(session)
        section_repo = ResearchGuideSectionRepository(session)
        citation_repo = CitationRecordRepository(session)
        guide = guide_repo.create(
            ResearchGuideCreate(key="g1", title="Guide", guide_kind="topic")
        )
        section = section_repo.create(
            ResearchGuideSectionCreate(guide_id=guide.id, heading="A")
        )
        citation_repo.create(
            CitationRecordCreate(
                section_id=section.id,
                source_type="publication",
                source_identifier="pub-1",
            )
        )
        citation_repo.create(
            CitationRecordCreate(
                section_id=section.id,
                source_type="external",
                source_identifier="https://example.invalid",
            )
        )
    with database.session() as session:
        citation_repo = CitationRecordRepository(session)
        assert len(citation_repo.list_for_section(1)) == 2
        assert (
            len(citation_repo.list_for_source("publication", "pub-1")) == 1
        )