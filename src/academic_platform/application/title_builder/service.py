"""Application service for the title builder.

The service composes the engine with the research title candidate
repository. It generates candidates from a topic draft, persists them
against the attached research project, and manages their state.

Design decisions
----------------
- The service is anchored to a research project. Title candidates are
  stored in the ``research_title_candidate`` table, which carries the
  project's identifier, the title, the rationale, the strengths, the
  problems, the assumptions, and the state.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Regenerating the candidates replaces the previous proposed candidates
  in a single transaction. Accepted, rejected, and archived candidates
  are preserved so that the user's decisions are not lost.
- The service records an audit event for each mutation.
"""

from __future__ import annotations

import logging
from typing import Any

from academic_platform.application.title_builder.engine import (
    TitleBuilderEngine,
)
from academic_platform.application.title_builder.errors import (
    TitleBuilderError,
    TitleBuilderNotFoundError,
    TitleBuilderValidationError,
)
from academic_platform.application.title_builder.model import (
    TitleCandidate,
    TitleGenerationReport,
    TitlePattern,
    TitleState,
)
from academic_platform.application.topic_workspace.model import TopicDraft
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
    ResearchTitleCandidate,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.application.title_builder.model import (
    TitleCandidate,
    TitleGenerationReport,
    TitleState,
)
from academic_platform.application.topic_workspace.model import TopicDraft


_logger = logging.getLogger(__name__)

_ACTION_TITLE_GENERATED = "title.generated"
_ACTION_TITLE_ACCEPTED = "title.accepted"
_ACTION_TITLE_REJECTED = "title.rejected"
_ACTION_TITLE_ARCHIVED = "title.archived"
_ACTION_TITLE_REMOVED = "title.removed"
_ACTION_TITLE_UPDATED = "title.updated"


class TitleBuilderService:
    """Application service for research title candidates."""

    def __init__(
        self,
        repositories: RepositoryManager,
        engine: TitleBuilderEngine | None = None,
    ) -> None:
        self._repositories = repositories
        self._engine = engine or TitleBuilderEngine()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate_for_project(
        self,
        project_key: str,
        draft: TopicDraft,
        *,
        actor: str = "system",
    ) -> list[TitleCandidate]:
        """Generate candidates from a draft and persist them."""
        project = self._require_project(project_key)
        report = self._engine.generate(draft)
        self._replace_proposed(project, report, actor=actor)
        return self.list_candidates(project_key)

    def preview(self, draft: TopicDraft) -> TitleGenerationReport:
        """Return the engine's output without persisting it."""
        return self._engine.generate(draft)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_candidates(self, project_key: str) -> list[TitleCandidate]:
        """Return every candidate for the project ordered by state then title."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_title_candidate")
        try:
            rows = repo.list_for_project(project.id)
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to list title candidates: {exc}"
            ) from exc
        candidates = [_row_to_candidate(row) for row in rows]
        candidates.sort(key=_candidate_sort_key)
        return candidates

    def list_accepted(self, project_key: str) -> list[TitleCandidate]:
        return [
            candidate
            for candidate in self.list_candidates(project_key)
            if candidate.state is TitleState.ACCEPTED
        ]

    # ------------------------------------------------------------------
    # State changes
    # ------------------------------------------------------------------
    def set_state(
        self,
        project_key: str,
        candidate_id: int,
        state: TitleState,
        *,
        actor: str = "system",
    ) -> TitleCandidate:
        """Set the state of a candidate and persist it."""
        project = self._require_project(project_key)
        row = self._require_candidate(project.id, candidate_id)
        previous_state = row.state
        row.state = state.value
        try:
            self._repositories.get("research_title_candidate").session.flush()
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to update the title candidate: {exc}"
            ) from exc
        action = _state_action(state)
        self._record_audit(
            actor=actor,
            action=action,
            target_identifier=project_key,
            summary=(
                f"Title candidate {row.title[:80]!r}: "
                f"{previous_state} -> {state.value}"
            ),
        )
        return _row_to_candidate(row)

    def accept_candidate(
        self,
        project_key: str,
        candidate_id: int,
        *,
        actor: str = "system",
    ) -> TitleCandidate:
        return self.set_state(
            project_key, candidate_id, TitleState.ACCEPTED, actor=actor
        )

    def reject_candidate(
        self,
        project_key: str,
        candidate_id: int,
        *,
        actor: str = "system",
    ) -> TitleCandidate:
        return self.set_state(
            project_key, candidate_id, TitleState.REJECTED, actor=actor
        )

    def archive_candidate(
        self,
        project_key: str,
        candidate_id: int,
        *,
        actor: str = "system",
    ) -> TitleCandidate:
        return self.set_state(
            project_key, candidate_id, TitleState.ARCHIVED, actor=actor
        )

    def remove_candidate(
        self,
        project_key: str,
        candidate_id: int,
        *,
        actor: str = "system",
    ) -> None:
        project = self._require_project(project_key)
        row = self._require_candidate(project.id, candidate_id)
        repo = self._repositories.get("research_title_candidate")
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to remove the title candidate: {exc}"
            ) from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TITLE_REMOVED,
            target_identifier=project_key,
            summary=f"Removed title candidate {row.title[:80]!r}",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to read the project: {exc}"
            ) from exc
        if row is None:
            raise TitleBuilderNotFoundError(f"No project with key {key!r}")
        return row

    def _require_candidate(
        self,
        project_id: int,
        candidate_id: int,
    ) -> ResearchTitleCandidate:
        repo = self._repositories.get("research_title_candidate")
        try:
            row = repo.get(candidate_id)
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to read the title candidate: {exc}"
            ) from exc
        if row is None or row.project_id != project_id:
            raise TitleBuilderNotFoundError(
                f"No title candidate with id {candidate_id!r} "
                f"in project {project_id!r}"
            )
        return row

    def _replace_proposed(
        self,
        project: ResearchProject,
        report: TitleGenerationReport,
        *,
        actor: str,
    ) -> None:
        repo = self._repositories.get("research_title_candidate")
        # Remove only the previously proposed candidates. Accepted,
        # rejected, and archived candidates are preserved.
        try:
            existing = repo.list_for_project(project.id)
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to read existing candidates: {exc}"
            ) from exc
        for row in existing:
            if row.state == TitleState.PROPOSED.value:
                try:
                    repo.delete(row)
                except RepositoryError:
                    _logger.warning(
                        "Unable to remove proposed candidate %s", row.id
                    )
        for candidate in report.candidates:
            row = ResearchTitleCandidate(
                project_id=project.id,
                title=candidate.title,
                rationale=_compose_field(
                    candidate.rationale,
                    candidate.alignment.summary,
                ),
                strengths=candidate.strengths,
                problems=candidate.problems,
                assumptions=candidate.assumptions,
                state=TitleState.PROPOSED.value,
            )
            try:
                repo.add(row)
            except RepositoryError as exc:
                raise TitleBuilderError(
                    f"Unable to persist a title candidate: {exc}"
                ) from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TITLE_GENERATED,
            target_identifier=project.key,
            summary=f"Generated {report.candidate_count} candidate(s)",
            payload={
                "patterns": [c.pattern.value for c in report.candidates],
                "skipped": list(report.skipped_patterns),
            },
        )

    def _record_audit(
        self,
        *,
        actor: str,
        action: str,
        target_identifier: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        import json

        try:
            session = self._repositories.get("audit_event").session
            session.add(
                AuditEvent(
                    actor=actor or "system",
                    action=action,
                    target_type="research_project",
                    target_identifier=target_identifier,
                    summary=summary,
                    payload_json=json.dumps(payload) if payload else None,
                )
            )
            session.flush()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.warning(
                "Unable to record the audit event for %s: %s",
                target_identifier,
                exc,
            )

    def update_title(
        self,
        project_key: str,
        candidate_id: int,
        title: str,
        *,
        actor: str = "system",
    ) -> TitleCandidate:
        """Replace a candidate's title text.

        The candidate's rationale, strengths, problems, and assumptions
        are preserved. The alignment report stored in the rationale is
        also preserved; recomputing it requires a fresh generation pass.

        Raises
        ------
        TitleBuilderValidationError
            If the title is empty or exceeds the maximum length.
        """
        cleaned = title.strip()
        issues: list[str] = []
        if not cleaned:
            issues.append("Title must not be empty")
        if len(cleaned) > 200:
            issues.append("Title must be at most 200 characters")
        if issues:
            raise TitleBuilderValidationError(issues)
        project = self._require_project(project_key)
        row = self._require_candidate(project.id, candidate_id)
        previous = row.title
        row.title = cleaned
        try:
            self._repositories.get("research_title_candidate").session.flush()
        except RepositoryError as exc:
            raise TitleBuilderError(
                f"Unable to update the title candidate: {exc}"
            ) from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TITLE_UPDATED,
            target_identifier=project_key,
            summary=f"Edited title candidate {previous[:80]!r}",
        )
        return _row_to_candidate(row)

    def restore_candidate(
        self,
        project_key: str,
        candidate_id: int,
        *,
        actor: str = "system",
    ) -> TitleCandidate:
        """Return a candidate to the proposed state."""
        return self.set_state(
            project_key, candidate_id, TitleState.PROPOSED, actor=actor
        )

    def list_by_state(
        self,
        project_key: str,
    ) -> dict[TitleState, tuple[TitleCandidate, ...]]:
        """Return the project's candidates grouped by state."""
        grouped: dict[TitleState, list[TitleCandidate]] = {
            state: [] for state in TitleState
        }
        for candidate in self.list_candidates(project_key):
            grouped[candidate.state].append(candidate)
        return {state: tuple(items) for state, items in grouped.items()}

    def comparison_report(
        self,
        project_key: str,
    ) -> tuple[TitleCandidate, ...]:
        """Return the candidates ordered for side-by-side comparison.

        The order is accepted first, then proposed (sorted by alignment
        descending), then rejected, then archived. The order matches the
        workspace's presentation.
        """
        return tuple(self.list_candidates(project_key))

# ----------------------------------------------------------------------
# Row and state helpers
# ----------------------------------------------------------------------
def _row_to_candidate(row: ResearchTitleCandidate) -> TitleCandidate:
    # The persisted row stores the alignment summary inside the rationale
    # field so that the row's schema is unchanged. The state is read from
    # the row's state column.
    rationale, alignment_text = _split_field(row.rationale)
    alignment = _alignment_from_text(alignment_text)
    return TitleCandidate(
        identifier=f"row.{row.id}",
        pattern=_guess_pattern(row.title),
        title=row.title,
        rationale=rationale,
        strengths=row.strengths or "",
        problems=row.problems or "",
        assumptions=row.assumptions or "",
        alignment=alignment,
        state=_safe_state(row.state),
    )


def _compose_field(rationale: str, alignment_text: str) -> str:
    return f"{rationale}\n---\n{alignment_text}"


def _split_field(raw: str) -> tuple[str, str]:
    if not raw:
        return "", ""
    if "\n---\n" in raw:
        rationale, alignment = raw.split("\n---\n", 1)
        return rationale.strip(), alignment.strip()
    return raw.strip(), ""


def _alignment_from_text(text: str):
    from academic_platform.application.title_builder.model import (
        TitleAlignmentReport,
    )

    if not text:
        return TitleAlignmentReport()
    match = re_search(r"alignment (\d+(?:\.\d+)?)", text)
    if match is None:
        return TitleAlignmentReport(notes=(text,))
    try:
        score = float(match)
    except ValueError:
        score = 0.0
    return TitleAlignmentReport(score=score, notes=(text,))


def _safe_state(value: str | None) -> TitleState:
    try:
        return TitleState(value) if value else TitleState.PROPOSED
    except ValueError:
        return TitleState.PROPOSED


def _guess_pattern(title: str) -> TitlePattern:
    # The pattern is not stored; it is recovered from the title's shape.
    # The recovery is conservative: unknown titles map to EXPLORATION.
    lowered = title.lower()
    if lowered.startswith("the effect of"):
        return TitlePattern.EFFECT_OF_X_ON_Y
    if lowered.startswith("association between"):
        return TitlePattern.ASSOCIATION_BETWEEN_X_AND_Y
    if lowered.startswith("a comparison of"):
        return TitlePattern.COMPARISON_ACROSS_GROUPS
    if lowered.startswith("development and validation"):
        return TitlePattern.DEVELOPMENT_OF_INSTRUMENT
    if lowered.startswith("a methodological study"):
        return TitlePattern.METHODOLOGICAL_STUDY
    if " in " in lowered:
        return TitlePattern.SUBJECT_IN_POPULATION
    if " and " in lowered:
        return TitlePattern.SUBJECT_AND_OUTCOME
    return TitlePattern.EXPLORATION_OF_SUBJECT


def _candidate_sort_key(candidate: TitleCandidate):
    state_rank = {
        TitleState.ACCEPTED: 0,
        TitleState.PROPOSED: 1,
        TitleState.REJECTED: 2,
        TitleState.ARCHIVED: 3,
    }.get(candidate.state, 4)
    return (state_rank, -candidate.alignment.score, candidate.identifier)


def _state_action(state: TitleState) -> str:
    return {
        TitleState.ACCEPTED: _ACTION_TITLE_ACCEPTED,
        TitleState.REJECTED: _ACTION_TITLE_REJECTED,
        TitleState.ARCHIVED: _ACTION_TITLE_ARCHIVED,
        TitleState.PROPOSED: _ACTION_TITLE_GENERATED,
    }[state]


import re


def re_search(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None