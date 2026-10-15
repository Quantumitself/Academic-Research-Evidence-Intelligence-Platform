"""Repository for research projects."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    ResearchProject,
    ResearchQuestion,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class ResearchProjectRepository(Repository[ResearchProject]):
    """Repository for the ``research_project`` table."""

    entity = ResearchProject

    def find_by_key(self, key: str) -> ResearchProject | None:
        """Return the project with the given stable key, or ``None``."""
        statement = select(ResearchProject).where(ResearchProject.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_ordered_by_updated(self, *, limit: int | None = None) -> list[ResearchProject]:
        """Return projects ordered by most recently updated first."""
        statement = select(ResearchProject).order_by(ResearchProject.updated_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_ordered_by_updated failed: {exc}") from exc

    def question_count(self, project_id: int) -> int:
        """Return the number of research questions belonging to a project."""
        statement = (
            select(ResearchQuestion)
            .where(ResearchQuestion.project_id == project_id)
        )
        try:
            return len(list(self._session.execute(statement).scalars().all()))
        except SQLAlchemyError as exc:
            raise RepositoryError(f"question_count failed: {exc}") from exc