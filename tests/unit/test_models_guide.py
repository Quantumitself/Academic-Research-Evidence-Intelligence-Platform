"""Tests for the research guide models."""

from __future__ import annotations

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    CitationRecord,
    ResearchGuide,
    ResearchGuideSection,
)
import pytest

from academic_platform.infrastructure.database import DatabaseError


def test_guide_and_sections_and_citations() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            guide = ResearchGuide(
                key="g1", title="Guide", guide_kind="topic"
            )
            session.add(guide)
            session.flush()
            section = ResearchGuideSection(
                guide_id=guide.id,
                heading="Background",
                body="Body",
                position=0,
                is_source_derived=1,
            )
            session.add(section)
            session.flush()
            session.add(
                CitationRecord(
                    section_id=section.id,
                    source_type="publication",
                    source_identifier="pub-1",
                    quoted_text="quoted",
                )
            )
        with database.session() as session:
            assert session.query(ResearchGuide).count() == 1
            assert session.query(ResearchGuideSection).count() == 1
            assert session.query(CitationRecord).count() == 1
    finally:
        database.dispose()


def test_cascade_delete_from_guide() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            guide = ResearchGuide(
                key="g1", title="Guide", guide_kind="topic"
            )
            session.add(guide)
            session.flush()
            section = ResearchGuideSection(
                guide_id=guide.id, heading="H", body="B"
            )
            session.add(section)
            session.flush()
            session.add(
                CitationRecord(
                    section_id=section.id,
                    source_type="external",
                    source_identifier="https://example.invalid",
                )
            )
        with database.session() as session:
            guide = session.get(ResearchGuide, 1)
            assert guide is not None
            session.delete(guide)
        with database.session() as session:
            assert session.query(ResearchGuideSection).count() == 0
            assert session.query(CitationRecord).count() == 0
    finally:
        database.dispose()


def test_invalid_source_type_rejected() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            guide = ResearchGuide(key="g1", title="Guide", guide_kind="topic")
            session.add(guide)
            session.flush()
            section = ResearchGuideSection(guide_id=guide.id, heading="H", body="B")
            session.add(section)
            session.flush()
        with pytest.raises(DatabaseError):
            with database.session() as session:
                session.add(
                    CitationRecord(
                        section_id=1,
                        source_type="bogus",
                        source_identifier="x",
                    )
                )
    finally:
        database.dispose()