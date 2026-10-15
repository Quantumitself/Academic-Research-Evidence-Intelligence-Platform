"""Repository for audit events.

Audit events are append-only. The repository exposes write operations for
appending events and read operations for querying the timeline. There
are no update or delete operations because the table's contract forbids
them; the base class methods that would perform those operations are
shadowed with methods that raise ``RepositoryError``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import AuditEvent
from academic_platform.infrastructure.database.schemas import AuditEventCreate
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError
from academic_platform.infrastructure.repositories.pagination import Page, PageRequest
from academic_platform.infrastructure.repositories.specification import Specification


class AuditEventRepository(Repository[AuditEvent]):
    """Repository for the ``audit_event`` table."""

    entity = AuditEvent

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def append(
        self,
        action: str,
        *,
        actor: str = "system",
        target_type: str | None = None,
        target_identifier: str | None = None,
        summary: str = "",
        payload_json: str | None = None,
        occurred_at: dt.datetime | None = None,
    ) -> AuditEvent:
        """Append an audit event.

        The event is created from a validated ``AuditEventCreate`` payload
        so that the same validation rules apply regardless of the caller.
        """
        payload = AuditEventCreate(
            actor=actor,
            action=action,
            target_type=target_type,
            target_identifier=target_identifier,
            summary=summary,
            payload_json=payload_json,
            occurred_at=occurred_at,
        )
        return self.create(payload)

    def append_many(self, events: Iterable[AuditEventCreate]) -> list[AuditEvent]:
        """Append multiple events in a single flush."""
        materialized: list[AuditEvent] = []
        for payload in events:
            materialized.append(
                AuditEvent(
                    actor=payload.actor,
                    action=payload.action,
                    target_type=payload.target_type,
                    target_identifier=payload.target_identifier,
                    summary=payload.summary,
                    payload_json=payload.payload_json,
                    occurred_at=payload.occurred_at
                    or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
                )
            )
        return self.add_all(materialized)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def recent(self, limit: int = 50) -> list[AuditEvent]:
        """Return the most recent events, newest first."""
        statement = (
            select(AuditEvent)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"recent failed: {exc}") from exc

    def for_actor(self, actor: str, limit: int = 50) -> list[AuditEvent]:
        """Return the most recent events for a specific actor."""
        statement = (
            select(AuditEvent)
            .where(AuditEvent.actor == actor)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"for_actor failed: {exc}") from exc

    def find_page_ordered(
        self,
        request: PageRequest,
        specification: Specification[AuditEvent] | None = None,
    ) -> Page[AuditEvent]:
        """Return a page of events ordered newest-first."""
        return self.find_page(
            request,
            specification,
            order_by=[AuditEvent.occurred_at.desc(), AuditEvent.id.desc()],
        )

    # ------------------------------------------------------------------
    # Forbidden operations
    # ------------------------------------------------------------------
    def update(self, entity: AuditEvent, payload) -> AuditEvent:  # type: ignore[override]
        raise RepositoryError("Audit events are append-only and cannot be updated")

    def update_fields(self, identifier, **changes) -> AuditEvent:  # type: ignore[override]
        raise RepositoryError("Audit events are append-only and cannot be updated")

    def delete(self, entity: AuditEvent) -> None:  # type: ignore[override]
        raise RepositoryError("Audit events are append-only and cannot be deleted")

    def delete_by_id(self, identifier) -> bool:  # type: ignore[override]
        raise RepositoryError("Audit events are append-only and cannot be deleted")