"""Repositories for research guides and their sections and citations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    CitationRecord,
    ResearchGuide,
    ResearchGuideSection,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class ResearchGuideRepository(Repository[ResearchGuide]):
    """Repository for the ``research_guide`` table."""

    entity = ResearchGuide

    def find_by_key(self, key: str) -> ResearchGuide | None:
        """Return the guide with the given key, or ``None``."""
        statement = (
            select(ResearchGuide).where(ResearchGuide.key == key).limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_all_ordered(self) -> list[ResearchGuide]:
        """Return every guide ordered by title."""
        statement = select(ResearchGuide).order_by(ResearchGuide.title)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_all_ordered failed: {exc}") from exc

    def list_for_project(self, project_id: int) -> list[ResearchGuide]:
        """Return guides owned by a specific project, newest first."""
        statement = (
            select(ResearchGuide)
            .where(ResearchGuide.project_id == project_id)
            .order_by(ResearchGuide.created_at.desc(), ResearchGuide.id.desc())
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc


class ResearchGuideSectionRepository(Repository[ResearchGuideSection]):
    """Repository for the ``research_guide_section`` table."""

    entity = ResearchGuideSection

    def list_for_guide(self, guide_id: int) -> list[ResearchGuideSection]:
        """Return the sections of a guide ordered by position."""
        statement = (
            select(ResearchGuideSection)
            .where(ResearchGuideSection.guide_id == guide_id)
            .order_by(ResearchGuideSection.position, ResearchGuideSection.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_guide failed: {exc}") from exc

    def next_position(self, guide_id: int) -> int:
        """Return the next position index for a guide."""
        statement = (
            select(ResearchGuideSection.position)
            .where(ResearchGuideSection.guide_id == guide_id)
            .order_by(ResearchGuideSection.position.desc())
            .limit(1)
        )
        try:
            current = self._session.execute(statement).scalar()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"next_position failed: {exc}") from exc
        return int(current or 0) + 1


class CitationRecordRepository(Repository[CitationRecord]):
    """Repository for the ``citation_record`` table."""

    entity = CitationRecord

    def list_for_section(self, section_id: int) -> list[CitationRecord]:
        """Return the citations of a section ordered by identifier."""
        statement = (
            select(CitationRecord)
            .where(CitationRecord.section_id == section_id)
            .order_by(CitationRecord.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_section failed: {exc}") from exc

    def list_for_source(
        self, source_type: str, source_identifier: str
    ) -> list[CitationRecord]:
        """Return every citation that references a specific source."""
        statement = (
            select(CitationRecord)
            .where(
                CitationRecord.source_type == source_type,
                CitationRecord.source_identifier == source_identifier,
            )
            .order_by(CitationRecord.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_source failed: {exc}") from exc