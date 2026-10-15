"""Repositories for research plans, tasks, and assistant proposals."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    AnalysisRecommendation,
    MethodologyProposal,
    ResearchPlan,
    ResearchTask,
    ResearchTitleCandidate,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class ResearchPlanRepository(Repository[ResearchPlan]):
    """Repository for the ``research_plan`` table."""

    entity = ResearchPlan

    def latest_for_project(self, project_id: int) -> ResearchPlan | None:
        """Return the most recently created plan for a project."""
        statement = (
            select(ResearchPlan)
            .where(ResearchPlan.project_id == project_id)
            .order_by(ResearchPlan.created_at.desc(), ResearchPlan.id.desc())
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"latest_for_project failed: {exc}") from exc

    def list_for_project(self, project_id: int) -> list[ResearchPlan]:
        """Return every plan for a project, newest first."""
        statement = (
            select(ResearchPlan)
            .where(ResearchPlan.project_id == project_id)
            .order_by(ResearchPlan.created_at.desc(), ResearchPlan.id.desc())
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc


class ResearchTaskRepository(Repository[ResearchTask]):
    """Repository for the ``research_task`` table."""

    entity = ResearchTask

    def list_for_project(self, project_id: int) -> list[ResearchTask]:
        """Return the tasks of a project ordered by position."""
        statement = (
            select(ResearchTask)
            .where(ResearchTask.project_id == project_id)
            .order_by(ResearchTask.position, ResearchTask.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc

    def list_open_for_project(self, project_id: int) -> list[ResearchTask]:
        """Return the open tasks of a project ordered by position."""
        statement = (
            select(ResearchTask)
            .where(
                ResearchTask.project_id == project_id,
                ResearchTask.completed == 0,
            )
            .order_by(ResearchTask.position, ResearchTask.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_open_for_project failed: {exc}") from exc

    def set_completed(self, task_id: int, completed: bool) -> ResearchTask:
        """Update the completion state of a task."""
        task = self.get_or_raise(task_id)
        task.completed = 1 if completed else 0
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_completed failed: {exc}") from exc
        return task


class ResearchTitleCandidateRepository(Repository[ResearchTitleCandidate]):
    """Repository for the ``research_title_candidate`` table."""

    entity = ResearchTitleCandidate

    def list_for_project(self, project_id: int) -> list[ResearchTitleCandidate]:
        """Return the title candidates of a project ordered by creation."""
        statement = (
            select(ResearchTitleCandidate)
            .where(ResearchTitleCandidate.project_id == project_id)
            .order_by(ResearchTitleCandidate.created_at, ResearchTitleCandidate.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc

    def set_state(self, candidate_id: int, state: str) -> ResearchTitleCandidate:
        """Update the state of a title candidate."""
        candidate = self.get_or_raise(candidate_id)
        candidate.state = state
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_state failed: {exc}") from exc
        return candidate


class MethodologyProposalRepository(Repository[MethodologyProposal]):
    """Repository for the ``methodology_proposal`` table."""

    entity = MethodologyProposal

    def list_for_project(self, project_id: int) -> list[MethodologyProposal]:
        """Return the methodology proposals of a project ordered by creation."""
        statement = (
            select(MethodologyProposal)
            .where(MethodologyProposal.project_id == project_id)
            .order_by(MethodologyProposal.created_at, MethodologyProposal.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc

    def set_state(self, proposal_id: int, state: str) -> MethodologyProposal:
        """Update the state of a methodology proposal."""
        proposal = self.get_or_raise(proposal_id)
        proposal.state = state
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_state failed: {exc}") from exc
        return proposal


class AnalysisRecommendationRepository(Repository[AnalysisRecommendation]):
    """Repository for the ``analysis_recommendation`` table."""

    entity = AnalysisRecommendation

    def list_for_project(self, project_id: int) -> list[AnalysisRecommendation]:
        """Return the analysis recommendations of a project ordered by creation."""
        statement = (
            select(AnalysisRecommendation)
            .where(AnalysisRecommendation.project_id == project_id)
            .order_by(AnalysisRecommendation.created_at, AnalysisRecommendation.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc

    def set_state(self, recommendation_id: int, state: str) -> AnalysisRecommendation:
        """Update the state of an analysis recommendation."""
        recommendation = self.get_or_raise(recommendation_id)
        recommendation.state = state
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_state failed: {exc}") from exc
        return recommendation