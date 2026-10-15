"""Tests for the document Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AnnotationCreate,
    DocumentAssetCreate,
    DocumentAssetUpdate,
    DocumentMetadataCreate,
    DocumentChunkCreate,
)

_CHECKSUM = "0" * 64


def test_asset_create_defaults() -> None:
    payload = DocumentAssetCreate(
        key="doc-1",
        location="/tmp/a.pdf",
        checksum_sha256=_CHECKSUM,
    )
    assert payload.storage_mode == "managed_copy"
    assert payload.size_bytes == 0


def test_asset_create_rejects_bad_checksum() -> None:
    with pytest.raises(ValidationError):
        DocumentAssetCreate(
            key="doc-1",
            location="/tmp/a.pdf",
            checksum_sha256="not-a-checksum",
        )


def test_asset_create_rejects_bad_storage_mode() -> None:
    with pytest.raises(ValidationError):
        DocumentAssetCreate(
            key="doc-1",
            location="/tmp/a.pdf",
            checksum_sha256=_CHECKSUM,
            storage_mode="bogus",
        )


def test_asset_update_optional() -> None:
    payload = DocumentAssetUpdate()
    assert payload.display_name is None


def test_asset_update_rejects_bad_state() -> None:
    with pytest.raises(ValidationError):
        DocumentAssetUpdate(processing_state="bogus")


def test_metadata_create_defaults() -> None:
    payload = DocumentMetadataCreate(document_id=1)
    assert payload.extraction_method == "pdf_heuristic"
    assert payload.reviewed_by_user is False


def test_metadata_create_rejects_out_of_range_year() -> None:
    with pytest.raises(ValidationError):
        DocumentMetadataCreate(document_id=1, year=99999)


def test_chunk_create_requires_content() -> None:
    with pytest.raises(ValidationError):
        DocumentChunkCreate(document_id=1, chunk_index=0, content="")


def test_annotation_create_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(document_id=1, kind="bogus")


def test_annotation_create_rejects_bad_color() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(document_id=1, kind="highlight", color="bogus")


def test_annotation_create_accepts_valid() -> None:
    payload = AnnotationCreate(
        document_id=1,
        kind="highlight",
        page_number=3,
        color="yellow",
    )
    assert payload.color == "yellow"