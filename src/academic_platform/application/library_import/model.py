"""Value objects for the library import workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ImportMode(str, Enum):
    """How a file will be stored after import."""

    MANAGED_COPY = "managed_copy"
    REFERENCED_FILE = "referenced_file"


class ImportCandidateState(str, Enum):
    """Validation state of a single import candidate."""

    READY = "ready"
    DUPLICATE = "duplicate"
    UNSUPPORTED = "unsupported"
    OVERSIZE = "oversize"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ImportCandidate:
    """A single file the user selected for import.

    Attributes
    ----------
    source_path:
        Absolute path to the file the user selected.
    filename:
        Basename of ``source_path``.
    extension:
        Lowercase extension including the leading dot, or empty.
    size_bytes:
        File size in bytes at validation time. ``None`` when the file
        could not be stat'ed.
    state:
        Current validation state.
    message:
        Human-readable explanation of the state when it is not READY.
    duplicate_of_document_key:
        When the file duplicates an existing library record, the
        document key of the existing record. Otherwise ``None``.
    duplicate_checksum:
        When a duplicate was detected, the matching checksum. ``None``
        otherwise.
    """

    source_path: Path
    filename: str
    extension: str
    size_bytes: int | None
    state: ImportCandidateState = ImportCandidateState.READY
    message: str = ""
    duplicate_of_document_key: str | None = None
    duplicate_checksum: str | None = None
    duplicate_signal: str = ""


    @property
    def is_importable(self) -> bool:
        """Return True when the candidate may be imported as-is."""
        return self.state in {
            ImportCandidateState.READY,
            ImportCandidateState.DUPLICATE,
        }

    @property
    def is_blocked(self) -> bool:
        """Return True when the candidate must not be imported."""
        return not self.is_importable

    def with_size(self, size_bytes: int) -> "ImportCandidate":
        """Return a copy of the candidate with ``size_bytes`` replaced."""
        return ImportCandidate(
            source_path=self.source_path,
            filename=self.filename,
            extension=self.extension,
            size_bytes=size_bytes,
            state=self.state,
            message=self.message,
            duplicate_of_document_key=self.duplicate_of_document_key,
            duplicate_checksum=self.duplicate_checksum,
            duplicate_signal=self.duplicate_signal,
        )


@dataclass(frozen=True, slots=True)
class ImportPlan:
    """The list of candidates the dialog will present.

    The plan is produced by the coordinator's ``prepare`` method and is
    immutable. The dialog renders it; the user's decisions are recorded
    by re-invoking the coordinator with the selected candidates.
    """

    mode: ImportMode
    candidates: tuple[ImportCandidate, ...] = field(default_factory=tuple)

    @property
    def importable_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_importable)

    @property
    def duplicate_count(self) -> int:
        return sum(
            1
            for c in self.candidates
            if c.state is ImportCandidateState.DUPLICATE
        )

    @property
    def blocked_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_blocked)


@dataclass(frozen=True, slots=True)
class ImportResult:
    """The outcome of an import operation."""

    imported_document_keys: tuple[str, ...] = field(default_factory=tuple)
    skipped_sources: tuple[Path, ...] = field(default_factory=tuple)
    failed_sources: tuple[tuple[Path, str], ...] = field(default_factory=tuple)

    @property
    def imported_count(self) -> int:
        return len(self.imported_document_keys)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_sources)

    @property
    def failed_count(self) -> int:
        return len(self.failed_sources)