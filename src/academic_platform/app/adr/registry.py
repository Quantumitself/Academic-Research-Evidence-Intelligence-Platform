"""In-memory registry of parsed ADRs.

The registry provides:

- Lookup by number.
- Lookup by status.
- Full-text search over title, context, decision, and consequences.
- Supersession chain resolution (both forward and backward).
- Duplicate-number detection.

The registry is constructed from a parsed directory and is immutable once
constructed. It performs no filesystem access after construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from academic_platform.app.adr.model import ADR, ADRStatus, ADRValidationError
from academic_platform.app.adr.parser import parse_adr_directory


@dataclass(frozen=True, slots=True)
class SupersessionChain:
    """A resolved supersession chain for a single ADR."""

    origin: ADR
    superseded_by: ADR | None
    supersedes: tuple[ADR, ...]


class ADRRegistry:
    """Immutable registry of ADR records."""

    def __init__(self, records: list[ADR], errors: list[tuple[Path, str]] | None = None) -> None:
        by_number: dict[str, ADR] = {}
        for record in records:
            if record.number in by_number:
                raise ADRValidationError(
                    f"Duplicate ADR number {record.number} in registry"
                )
            by_number[record.number] = record
        self._by_number = by_number
        self._ordered = tuple(sorted(by_number.values(), key=lambda record: record.number))
        self._errors = tuple(errors or ())

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_directory(cls, directory: Path) -> "ADRRegistry":
        records, errors = parse_adr_directory(directory)
        return cls(records, errors)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def records(self) -> tuple[ADR, ...]:
        return self._ordered

    @property
    def errors(self) -> tuple[tuple[Path, str], ...]:
        return self._errors

    def get(self, number: str) -> ADR | None:
        return self._by_number.get(number)

    def require(self, number: str) -> ADR:
        record = self._by_number.get(number)
        if record is None:
            raise KeyError(f"No ADR with number {number}")
        return record

    def by_status(self, status: ADRStatus) -> tuple[ADR, ...]:
        return tuple(record for record in self._ordered if record.status is status)

    def active(self) -> tuple[ADR, ...]:
        return tuple(record for record in self._ordered if record.is_active)

    def search(self, query: str) -> tuple[ADR, ...]:
        needle = query.strip().lower()
        if not needle:
            return self._ordered
        matches: list[ADR] = []
        for record in self._ordered:
            haystack = " ".join(
                (
                    record.number,
                    record.title,
                    record.context,
                    record.decision,
                    record.consequences,
                    record.alternatives,
                )
            ).lower()
            if needle in haystack:
                matches.append(record)
        return tuple(matches)

    def chain_for(self, number: str) -> SupersessionChain:
        origin = self.require(number)
        forward = self.get(origin.superseded_by) if origin.superseded_by else None
        backward: list[ADR] = []
        for reference in origin.supersedes:
            target = self.get(reference)
            if target is not None:
                backward.append(target)
        return SupersessionChain(
            origin=origin,
            superseded_by=forward,
            supersedes=tuple(backward),
        )