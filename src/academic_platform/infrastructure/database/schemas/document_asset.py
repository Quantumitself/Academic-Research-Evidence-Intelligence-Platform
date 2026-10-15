"""Pydantic schemas for the document asset, metadata, chunk, and annotation models."""

from __future__ import annotations

import datetime as dt
import re

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VALID_STORAGE_MODES = {"managed_copy", "referenced_file"}
_VALID_PROCESSING_STATES = {"pending", "extracting", "extracted", "indexed", "failed"}
_VALID_OCR_STATES = {"not_required", "pending", "completed", "failed"}
_VALID_ANNOTATION_KINDS = {"note", "highlight", "bookmark"}
_VALID_ANNOTATION_COLORS = {"yellow", "green", "blue", "pink"}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _validate_key(value: str) -> str:
    if not _KEY_PATTERN.match(value):
        raise ValueError("key must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return value


def _validate_checksum(value: str) -> str:
    if not _SHA256_PATTERN.match(value):
        raise ValueError("checksum_sha256 must be a lowercase hexadecimal SHA-256")
    return value


class DocumentAssetCreate(PersistenceSchema):
    """Payload accepted when registering a document asset."""

    key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=512)
    original_filename: str = Field(default="", max_length=512)
    storage_mode: str = Field(default="managed_copy", max_length=32)
    location: str = Field(min_length=1)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(default=0, ge=0)
    page_count: int | None = Field(default=None, ge=0)

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _validate_key(value)

    @field_validator("checksum_sha256")
    @classmethod
    def _check_checksum(cls, value: str) -> str:
        return _validate_checksum(value)

    @field_validator("storage_mode")
    @classmethod
    def _check_storage_mode(cls, value: str) -> str:
        if value not in _VALID_STORAGE_MODES:
            raise ValueError(f"storage_mode must be one of {sorted(_VALID_STORAGE_MODES)}")
        return value


class DocumentAssetUpdate(PersistenceSchema):
    """Payload accepted when updating a document asset."""

    display_name: str | None = Field(default=None, max_length=512)
    location: str | None = Field(default=None)
    processing_state: str | None = Field(default=None, max_length=32)
    processing_version: int | None = Field(default=None, ge=1)
    ocr_state: str | None = Field(default=None, max_length=32)
    indexing_state: str | None = Field(default=None, max_length=32)
    missing: bool | None = None
    last_error: str | None = None
    page_count: int | None = Field(default=None, ge=0)

    @field_validator("processing_state")
    @classmethod
    def _check_processing_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _VALID_PROCESSING_STATES:
            raise ValueError(
                f"processing_state must be one of {sorted(_VALID_PROCESSING_STATES)}"
            )
        return value

    @field_validator("ocr_state")
    @classmethod
    def _check_ocr_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _VALID_OCR_STATES:
            raise ValueError(f"ocr_state must be one of {sorted(_VALID_OCR_STATES)}")
        return value


class DocumentAssetRead(PersistenceSchema):
    """Payload returned when reading a document asset."""

    id: int
    key: str
    display_name: str
    original_filename: str
    storage_mode: str
    location: str
    checksum_sha256: str
    size_bytes: int
    page_count: int | None
    processing_state: str
    processing_version: int
    ocr_state: str
    indexing_state: str
    missing: bool
    last_error: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int

    @field_validator("missing", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)


class DocumentMetadataCreate(PersistenceSchema):
    """Payload accepted when storing extracted metadata."""

    document_id: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=1024)
    authors_json: str | None = None
    year: int | None = Field(default=None, ge=0, le=3000)
    venue: str | None = Field(default=None, max_length=512)
    doi: str | None = Field(default=None, max_length=255)
    abstract: str | None = None
    language: str | None = Field(default=None, max_length=16)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extraction_method: str = Field(default="pdf_heuristic", max_length=64)
    reviewed_by_user: bool = False


class DocumentMetadataUpdate(PersistenceSchema):
    """Payload accepted when updating extracted metadata."""

    title: str | None = Field(default=None, max_length=1024)
    authors_json: str | None = None
    year: int | None = Field(default=None, ge=0, le=3000)
    venue: str | None = Field(default=None, max_length=512)
    doi: str | None = Field(default=None, max_length=255)
    abstract: str | None = None
    language: str | None = Field(default=None, max_length=16)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reviewed_by_user: bool | None = None


class DocumentMetadataRead(PersistenceSchema):
    """Payload returned when reading extracted metadata."""

    id: int
    document_id: int
    title: str | None
    authors_json: str | None
    year: int | None
    venue: str | None
    doi: str | None
    abstract: str | None
    language: str | None
    extraction_confidence: float | None
    extraction_method: str
    reviewed_by_user: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    @field_validator("reviewed_by_user", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)


class DocumentChunkCreate(PersistenceSchema):
    """Payload accepted when storing an extracted text chunk."""

    document_id: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1)
    token_count: int | None = Field(default=None, ge=0)


class DocumentChunkRead(PersistenceSchema):
    """Payload returned when reading an extracted text chunk."""

    id: int
    document_id: int
    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    token_count: int | None
    created_at: dt.datetime
    updated_at: dt.datetime


class AnnotationCreate(PersistenceSchema):
    """Payload accepted when creating an annotation or bookmark."""

    document_id: int = Field(ge=1)
    kind: str = Field(max_length=16)
    page_number: int | None = Field(default=None, ge=1)
    text_excerpt: str | None = None
    body: str = ""
    anchor: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, max_length=16)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        if value not in _VALID_ANNOTATION_KINDS:
            raise ValueError(f"kind must be one of {sorted(_VALID_ANNOTATION_KINDS)}")
        return value

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _VALID_ANNOTATION_COLORS:
            raise ValueError(
                f"color must be one of {sorted(_VALID_ANNOTATION_COLORS)}"
            )
        return value


class AnnotationUpdate(PersistenceSchema):
    """Payload accepted when updating an annotation or bookmark."""

    page_number: int | None = Field(default=None, ge=1)
    text_excerpt: str | None = None
    body: str | None = None
    anchor: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, max_length=16)

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _VALID_ANNOTATION_COLORS:
            raise ValueError(
                f"color must be one of {sorted(_VALID_ANNOTATION_COLORS)}"
            )
        return value


class AnnotationRead(PersistenceSchema):
    """Payload returned when reading an annotation or bookmark."""

    id: int
    document_id: int
    kind: str
    page_number: int | None
    text_excerpt: str | None
    body: str
    anchor: str | None
    color: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int