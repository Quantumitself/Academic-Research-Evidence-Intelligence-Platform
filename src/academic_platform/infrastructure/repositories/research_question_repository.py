"""Repository for research questions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import ResearchQuestion
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class ResearchQuestionRepository(Repository[ResearchQuestion]):
    """Repository for the ``research_question`` table."""

    entity = ResearchQuestion

    def list_for_project(self, project_id: int) -> list[ResearchQuestion]:
        """Return the questions of a project ordered by position."""
        statement = (
            select(ResearchQuestion)
            .where(ResearchQuestion.project_id == project_id)
            .order_by(ResearchQuestion.position, ResearchQuestion.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc

    def primary_for_project(self, project_id: int) -> ResearchQuestion | None:
        """Return the primary question of a project, if one is designated."""
        statement = (
            select(ResearchQuestion)
            .where(
                ResearchQuestion.project_id == project_id,
                ResearchQuestion.is_primary == 1,
            )
            .order_by(ResearchQuestion.position, ResearchQuestion.id)
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"primary_for_project failed: {exc}") from exc

    def clear_primary_for_project(self, project_id: int) -> int:
        """Clear the primary flag for every question of a project.

        Returns the number of rows that were updated. The repository does
        not set a new primary question; the caller sets it after clearing.
        """
        statement = (
            ResearchQuestion.__table__.update()
            .where(ResearchQuestion.project_id == project_id)
            .values(is_primary=0)
        )
        try:
            result = self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"clear_primary_for_project failed: {exc}") from exc
        return int(result.rowcount or 0)

    def next_position(self, project_id: int) -> int:
        """Return the next position index for a project."""
        statement = (
            select(ResearchQuestion.position)
            .where(ResearchQuestion.project_id == project_id)
            .order_by(ResearchQuestion.position.desc())
            .limit(1)
        )
        try:
            current = self._session.execute(statement).scalar()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"next_position failed: {exc}") from exc
        return int(current or 0) + 1