"""Repositories for analysis runs and their inputs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    AnalysisInput,
    AnalysisRun,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class AnalysisRunRepository(Repository[AnalysisRun]):
    """Repository for the ``analysis_run`` table."""

    entity = AnalysisRun

    def list_recent(self, *, limit: int = 25) -> list[AnalysisRun]:
        """Return the most recent analysis runs, newest first."""
        statement = (
            select(AnalysisRun)
            .order_by(AnalysisRun.started_at.desc(), AnalysisRun.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_recent failed: {exc}") from exc

    def list_for_type(self, analysis_type: str, *, limit: int = 50) -> list[AnalysisRun]:
        """Return analysis runs of a specific type, newest first."""
        statement = (
            select(AnalysisRun)
            .where(AnalysisRun.analysis_type == analysis_type)
            .order_by(AnalysisRun.started_at.desc(), AnalysisRun.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_type failed: {exc}") from exc

    def mark_finished(
        self,
        run_id: int,
        *,
        status: str,
        finished_at,
        duration_ms: int | None,
        result_json: str | None,
        warnings_json: str | None = None,
        error_message: str | None = None,
        inputs_count: int | None = None,
    ) -> AnalysisRun:
        """Record the outcome of an analysis run."""
        run = self.get_or_raise(run_id)
        run.status = status
        run.finished_at = finished_at
        run.duration_ms = duration_ms
        run.result_json = result_json
        run.warnings_json = warnings_json
        run.error_message = error_message
        if inputs_count is not None:
            run.inputs_count = inputs_count
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"mark_finished failed: {exc}") from exc
        return run


class AnalysisInputRepository(Repository[AnalysisInput]):
    """Repository for the ``analysis_input`` table."""

    entity = AnalysisInput

    def list_for_run(self, run_id: int) -> list[AnalysisInput]:
        """Return the inputs of an analysis run ordered by input key."""
        statement = (
            select(AnalysisInput)
            .where(AnalysisInput.analysis_run_id == run_id)
            .order_by(AnalysisInput.input_key, AnalysisInput.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_run failed: {exc}") from exc

    def add_inputs(self, run_id: int, inputs: list[AnalysisInput]) -> list[AnalysisInput]:
        """Add multiple inputs to a run in a single flush.

        The caller is responsible for having constructed each input with
        the correct ``analysis_run_id``.
        """
        for item in inputs:
            if item.analysis_run_id != run_id:
                raise RepositoryError(
                    "Input analysis_run_id does not match the target run"
                )
        try:
            self._session.add_all(inputs)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"add_inputs failed: {exc}") from exc
        return inputs