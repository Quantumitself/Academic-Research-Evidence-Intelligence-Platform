"""Data model for Architecture Decision Records.

An ADR is represented by a frozen dataclass. Fields mirror the ADR template
defined in ``docs/adr/TEMPLATE.md``. Parsing produces validated instances;
consumers never construct ADRs by hand outside of tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ADRStatus(str, Enum):
    """Lifecycle status of an ADR.

    Values match the canonical set used across the project. Statuses are
    ordered from least to most final; ``superseded`` and ``deprecated``
    terminate a record's active lifetime.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class ADRValidationError(RuntimeError):
    """Raised when an ADR file cannot be parsed into a valid record."""


@dataclass(frozen=True, slots=True)
class ADRValidationIssue:
    """A single validation problem discovered in an ADR file."""

    field: str
    message: str

    def render(self) -> str:
        return f"{self.field}: {self.message}"


@dataclass(frozen=True, slots=True)
class ADR:
    """A parsed Architecture Decision Record.

    Attributes
    ----------
    number:
        Zero-padded numeric identifier (for example ``"0001"``).
    title:
        Short imperative title of the decision.
    status:
        Current lifecycle status.
    date:
        ISO-8601 date string (``YYYY-MM-DD``) of the decision.
    deciders:
        People or roles responsible for the decision.
    context:
        Narrative explaining the situation requiring a decision.
    decision:
        The chosen option, stated in the present tense.
    consequences:
        Outcomes, trade-offs, and follow-ups.
    alternatives:
        Options that were considered and rejected, with reasons.
    references:
        External or internal references supporting the decision.
    supersedes:
        Numbers of ADRs this record supersedes, if any.
    superseded_by:
        Number of the ADR that supersedes this record, if any.
    source_path:
        Absolute path to the file the record was parsed from.
    extra_sections:
        Any additional top-level sections found in the file, preserved
        verbatim so that no authoring content is lost.
    """

    number: str
    title: str
    status: ADRStatus
    date: str
    deciders: tuple[str, ...] = field(default_factory=tuple)
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives: str = ""
    references: tuple[str, ...] = field(default_factory=tuple)
    supersedes: tuple[str, ...] = field(default_factory=tuple)
    superseded_by: str | None = None
    source_path: Path | None = None
    extra_sections: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def slug(self) -> str:
        """Return a filesystem-safe slug derived from number and title."""
        safe_title = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in self.title.lower()
        )
        while "--" in safe_title:
            safe_title = safe_title.replace("--", "-")
        return f"{self.number}-{safe_title.strip('-')}"

    @property
    def is_active(self) -> bool:
        """Return True if the record is currently in force."""
        return self.status in {ADRStatus.PROPOSED, ADRStatus.ACCEPTED}