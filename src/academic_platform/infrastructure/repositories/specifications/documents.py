"""Specifications for the document repository layer."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import DocumentAsset
from academic_platform.infrastructure.repositories.specification import Specification


class DocumentByProcessingState(Specification[DocumentAsset]):
    """Matches documents in a specific processing state."""

    def __init__(self, state: str) -> None:
        self._state = state

    def to_expression(self, entity: type[DocumentAsset]):
        return entity.processing_state == self._state


class DocumentByStorageMode(Specification[DocumentAsset]):
    """Matches documents stored in a specific mode."""

    def __init__(self, mode: str) -> None:
        self._mode = mode

    def to_expression(self, entity: type[DocumentAsset]):
        return entity.storage_mode == self._mode


class DocumentMissing(Specification[DocumentAsset]):
    """Matches documents whose underlying file has been marked missing."""

    def to_expression(self, entity: type[DocumentAsset]):
        return entity.missing == 1


class DocumentDisplayNameContains(Specification[DocumentAsset]):
    """Matches documents whose display name contains a fragment."""

    def __init__(self, fragment: str) -> None:
        self._fragment = fragment

    def to_expression(self, entity: type[DocumentAsset]):
        return entity.display_name.ilike(f"%{self._fragment}%")


class DocumentChecksum(Specification[DocumentAsset]):
    """Matches the document with a specific SHA-256 checksum."""

    def __init__(self, checksum: str) -> None:
        self._checksum = checksum

    def to_expression(self, entity: type[DocumentAsset]):
        return entity.checksum_sha256 == self._checksum