"""Application service coordinating the import workflow.

The coordinator has two responsibilities:

1. ``prepare`` — validate a list of source paths against the configured
   size and format policy, detect duplicates against the existing
   library, and return an ``ImportPlan`` the dialog can render.
2. ``import_files`` — persist the confirmed selection through the file
   storage service and the document repository.

Design decisions
----------------
- The coordinator never reads file contents. It validates metadata and
  delegates checksum computation to the file storage service.
- Duplicate detection is performed against the document repository by
  checksum. The repository's ``find_by_checksum`` is the single source
  of truth for duplicate detection.
- The coordinator is idempotent with respect to the source paths in a
  single call: importing the same path twice in one call is not
  possible because the plan lists each path once.
- The coordinator never commits. It runs inside a unit of work supplied
  by the caller.
- The coordinator never deletes source files. It does not manage
  temporary files; the file storage service handles that internally.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from academic_platform.application.library_import.errors import (
    ImportError,
    ImportStorageError,
    ImportValidationError,
)
from academic_platform.application.library_import.model import (
    ImportCandidate,
    ImportCandidateState,
    ImportMode,
    ImportPlan,
    ImportResult,
)
from academic_platform.infrastructure.database.models import DocumentAsset
from academic_platform.infrastructure.file_storage import (
    FileStorage,
    FileStorageError,
    FileStorageMissingError,
    FileStorageSizeError,
    FileStorageValidationError,
    StorageMode,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.application.deduplication.detector import (
    DocumentDuplicateDetector,
    DuplicateDecision,
    DuplicateSignal,
)
from academic_platform.application.deduplication.policy import DuplicatePolicy


_logger = logging.getLogger(__name__)

#: Extensions the coordinator accepts at this stage of the product.
#: The set is deliberately small: PDF is the primary document format.
#: Additional formats are added in later phases when their extractors
#: are available.
_DEFAULT_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

_DOCUMENT_KEY_LENGTH = 32


class ImportCoordinator:
    """Coordinate validation and persistence for the import workflow."""

    def __init__(
        self,
        repositories: RepositoryManager,
        storage: FileStorage,
        *,
        supported_extensions: frozenset[str] = _DEFAULT_SUPPORTED_EXTENSIONS,
        max_file_size_bytes: int | None = None,
        duplicate_policy: DuplicatePolicy | None = None,
    ) -> None:
        self._repositories = repositories
        self._storage = storage
        self._supported_extensions = {
            extension.lower() for extension in supported_extensions
        }
        self._max_file_size_bytes = (
            max_file_size_bytes
            if max_file_size_bytes is not None
            else storage.config.max_file_size_bytes
        )
        self._detector = DocumentDuplicateDetector(
            repositories, duplicate_policy or DuplicatePolicy()
        )

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------
    def prepare(
        self,
        sources: list[Path],
        mode: ImportMode,
    ) -> ImportPlan:
        """Validate a list of source paths and build an import plan."""
        candidates: list[ImportCandidate] = []
        seen_paths: set[Path] = set()
        for source in sources:
            resolved = _safe_resolve(source)
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            candidates.append(self._evaluate(resolved))
        return ImportPlan(mode=mode, candidates=tuple(candidates))

    def _evaluate(self, source: Path) -> ImportCandidate:
        base = _candidate_metadata(source)
        if not source.exists():
            return _replace_state(
                base,
                ImportCandidateState.MISSING,
                "File does not exist.",
            )
        if not source.is_file():
            return _replace_state(
                base,
                ImportCandidateState.UNREADABLE,
                "Path is not a regular file.",
            )
        extension = _extension_for(source)
        if extension and extension not in self._supported_extensions:
            return _replace_state(
                base,
                ImportCandidateState.UNSUPPORTED,
                f"Extension {extension} is not supported at this stage.",
            )
        try:
            size = source.stat().st_size
        except OSError as exc:
            return _replace_state(
                base,
                ImportCandidateState.UNREADABLE,
                f"Unable to read file metadata: {exc}",
            )
        if size > self._max_file_size_bytes:
            return _replace_state(
                base.with_size(size),
                ImportCandidateState.OVERSIZE,
                (
                    f"File is {size} bytes, exceeding the configured limit "
                    f"of {self._max_file_size_bytes} bytes."
                ),
            )
        try:
            checksum = self._storage.compute_checksum(source)
        except FileStorageMissingError:
            return _replace_state(
                base.with_size(size),
                ImportCandidateState.MISSING,
                "File disappeared during validation.",
            )
        except FileStorageSizeError as exc:
            return _replace_state(
                base.with_size(size),
                ImportCandidateState.OVERSIZE,
                str(exc),
            )
        except FileStorageValidationError as exc:
            return _replace_state(
                base.with_size(size),
                ImportCandidateState.UNREADABLE,
                str(exc),
            )
        except FileStorageError as exc:
            return _replace_state(
                base.with_size(size),
                ImportCandidateState.ERROR,
                str(exc),
            )

        decision = self._detector.evaluate(
            checksum_sha256=checksum,
            title=candidate_title(source),
        )
        if decision.is_duplicate and decision.existing_key is not None:
            return ImportCandidate(
                source_path=base.source_path,
                filename=base.filename,
                extension=base.extension,
                size_bytes=size,
                state=ImportCandidateState.DUPLICATE,
                message=(
                    f"Already in the library as "
                    f"{decision.existing_display_name or decision.existing_key}."
                ),
                duplicate_of_document_key=decision.existing_key,
                duplicate_checksum=checksum,
                duplicate_signal=(
                    decision.decisive_signal.value
                    if decision.decisive_signal is not None
                    else ""
                ),
            )

        return base.with_size(size)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def import_files(
        self,
        plan: ImportPlan,
        *,
        selected_paths: list[Path] | None = None,
        import_duplicates: bool = False,
    ) -> ImportResult:
        """Persist the confirmed candidates.

        Parameters
        ----------
        plan:
            The plan produced by ``prepare``.
        selected_paths:
            When supplied, only the candidates whose source path appears
            in this list are imported. When ``None``, every importable
            candidate is imported.
        import_duplicates:
            When True, candidates whose state is DUPLICATE are imported
            as new library records. When False, they are skipped and
            reported in the result.
        """
        selected_set = (
            {_safe_resolve(path) for path in selected_paths}
            if selected_paths is not None
            else None
        )
        imported: list[str] = []
        skipped: list[Path] = []
        failed: list[tuple[Path, str]] = []

        for candidate in plan.candidates:
            if selected_set is not None and candidate.source_path not in selected_set:
                continue
            if candidate.state is ImportCandidateState.DUPLICATE and not import_duplicates:
                skipped.append(candidate.source_path)
                continue
            if candidate.is_blocked and candidate.state is not ImportCandidateState.DUPLICATE:
                skipped.append(candidate.source_path)
                continue
            try:
                document_key = self._persist(candidate, plan.mode)
            except ImportStorageError as exc:
                failed.append((candidate.source_path, str(exc)))
                continue
            except ImportError as exc:
                failed.append((candidate.source_path, str(exc)))
                continue
            imported.append(document_key)

        return ImportResult(
            imported_document_keys=tuple(imported),
            skipped_sources=tuple(skipped),
            failed_sources=tuple(failed),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _persist(self, candidate: ImportCandidate, mode: ImportMode) -> str:
        storage_mode = (
            StorageMode.MANAGED_COPY
            if mode is ImportMode.MANAGED_COPY
            else StorageMode.REFERENCED_FILE
        )
        try:
            if storage_mode is StorageMode.MANAGED_COPY:
                stored = self._storage.import_managed_copy(candidate.source_path)
            else:
                stored = self._storage.record_referenced_file(candidate.source_path)
        except FileStorageError as exc:
            raise ImportStorageError(
                f"Unable to store {candidate.source_path}: {exc}"
            ) from exc

        document_repo = self._repositories.get("document_asset")
        key = _document_key_for(stored.checksum_sha256)
        try:
            existing_by_key = document_repo.find_by_key(key)
        except RepositoryError as exc:
            raise ImportStorageError(
                f"Unable to check for an existing document: {exc}"
            ) from exc
        if existing_by_key is not None:
            # The same checksum has already been recorded under the same
            # key. Import is a no-op; the caller receives the existing
            # key so that they can add it to a collection or project.
            return existing_by_key.key

        row = DocumentAsset(
            key=key,
            display_name=candidate.filename,
            original_filename=candidate.filename,
            storage_mode=stored.mode.value,
            location=str(stored.location),
            checksum_sha256=stored.checksum_sha256,
            size_bytes=stored.size_bytes,
            processing_state="pending",
            indexing_state="pending",
            ocr_state="not_required",
            missing=0,
        )
        try:
            document_repo.add(row)
        except RepositoryError as exc:
            raise ImportStorageError(
                f"Unable to record the document: {exc}"
            ) from exc
        return row.key

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _candidate_metadata(source: Path) -> ImportCandidate:
    return ImportCandidate(
        source_path=source,
        filename=source.name,
        extension=_extension_for(source),
        size_bytes=None,
    )


def _extension_for(source: Path) -> str:
    suffix = source.suffix.lower()
    return suffix


def _replace_state(
    base: ImportCandidate,
    state: ImportCandidateState,
    message: str,
) -> ImportCandidate:
    return ImportCandidate(
        source_path=base.source_path,
        filename=base.filename,
        extension=base.extension,
        size_bytes=base.size_bytes,
        state=state,
        message=message,
        duplicate_of_document_key=base.duplicate_of_document_key,
        duplicate_checksum=base.duplicate_checksum,
    )


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path


def _document_key_for(checksum: str) -> str:
    digest = hashlib.sha256(checksum.encode("utf-8")).hexdigest()
    return f"doc-{digest[:_DOCUMENT_KEY_LENGTH]}"

def candidate_title(source: Path) -> str:
    """Return a title candidate derived from the file name.

    The helper strips the extension and replaces common separators with
    spaces so that the detector's title comparison has a meaningful
    value even when no metadata has been extracted yet.
    """
    stem = source.stem
    for separator in ("_", "-", "."):
        stem = stem.replace(separator, " ")
    return stem.strip()