"""Document asset model.

A document asset represents a physical file that the user imported or
referenced. It carries the file location, its checksum, its processing
state, and the metadata extracted from it (title, authors, year, DOI).

Design decisions
----------------
- ``storage_mode`` distinguishes managed copies from referenced files.
  Managed copies live under the application's managed library directory;
  referenced files stay in their original location and are tracked by
  absolute path.
- ``checksum_sha256`` is stored as a lowercase hexadecimal string. It is
  the primary key for duplicate detection across imports.
- ``processing_state`` is a closed enumeration that tracks the pipeline
  stage: ``pending``, ``extracting``, ``extracted``, ``indexed``,
  ``failed``. The state is advanced by the processing pipeline, not by
  the repository.
- ``ocr_state`` is optional. It records whether OCR was applied and
  whether it succeeded. Documents that do not require OCR have this
  field set to ``not_required``.
- ``missing`` records whether the underlying file has been detected as
  missing. Referenced files can disappear when the user moves them;
  managed files should not, but the flag protects against accidental
  deletion.
- The model never stores the file contents. The file lives on disk; the
  database stores its location and metadata.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_STORAGE_MODES = ("managed_copy", "referenced_file")
_STORAGE_MODE_CHECK = (
    "storage_mode IN (" + ", ".join(f"'{value}'" for value in _STORAGE_MODES) + ")"
)

_PROCESSING_STATES = (
    "pending",
    "extracting",
    "extracted",
    "indexed",
    "failed",
)
_PROCESSING_STATE_CHECK = (
    "processing_state IN ("
    + ", ".join(f"'{value}'" for value in _PROCESSING_STATES)
    + ")"
)

_OCR_STATES = ("not_required", "pending", "completed", "failed")
_OCR_STATE_CHECK = (
    "ocr_state IN (" + ", ".join(f"'{value}'" for value in _OCR_STATES) + ")"
)


class DocumentAsset(Base, TimestampMixin, VersionMixin):
    """A physical file the user imported or referenced."""

    __tablename__ = "document_asset"
    __table_args__ = (
        CheckConstraint(_STORAGE_MODE_CHECK, name="storage_mode_valid"),
        CheckConstraint(_PROCESSING_STATE_CHECK, name="processing_state_valid"),
        CheckConstraint(_OCR_STATE_CHECK, name="ocr_state_valid"),
        Index("ix_document_asset_checksum", "checksum_sha256"),
        Index("ix_document_asset_processing_state", "processing_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    original_filename: Mapped[str] = mapped_column(
        String(512), nullable=False, default=""
    )
    storage_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="managed_copy", server_default="managed_copy"
    )
    location: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Absolute filesystem path or application-relative path under the managed library.",
    )
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    processing_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        doc="Version of the processing pipeline that produced this record.",
    )
    ocr_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_required", server_default="not_required"
    )
    indexing_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    missing: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentAsset key={self.key!r} state={self.processing_state!r}>"