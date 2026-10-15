"""Typed configuration schema.

The schema is defined with Pydantic v2 so that every field is validated,
documented, and exportable to JSON Schema. The schema is versioned: each
persisted file records the schema version it was written under, and the
settings service is responsible for migrating older files.

Design decisions
----------------
- Every field has an explicit default. A missing field in a persisted file
  is therefore not an error; it is filled with the current default.
- Unknown fields are rejected. This prevents silent drift when a user hand
  edits the file or when a newer application version writes fields that an
  older version does not understand.
- The schema is flat enough to be read by a human but grouped into sections
  so that the settings UI can render them cohesively.
- No field stores secrets. Credentials are stored separately in the
  operating system keyring; only references to credentials appear here.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SETTINGS_SCHEMA_VERSION: int = 1


class ThemeMode(str, Enum):
    """Available interface theme modes."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class _StrictModel(BaseModel):
    """Base model forbidding unknown fields and enforcing strict types."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class GeneralSettings(_StrictModel):
    """General application preferences."""

    language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
        description="Interface language code (BCP 47 subset).",
    )
    check_for_updates: bool = Field(
        default=False,
        description="Whether to check for application updates on startup.",
    )
    telemetry_enabled: bool = Field(
        default=False,
        description=(
            "Whether anonymous usage statistics are collected. Disabled by "
            "default; enabling requires explicit user action in the UI."
        ),
    )
    confirm_on_exit: bool = Field(
        default=True,
        description="Prompt for confirmation before closing the application.",
    )

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        normalized = value.strip().lower().replace("_", "-")
        if not normalized:
            raise ValueError("language must not be empty")
        return normalized


class AppearanceSettings(_StrictModel):
    """Visual preferences."""

    theme: ThemeMode = Field(default=ThemeMode.SYSTEM)
    font_scale: float = Field(
        default=1.0,
        ge=0.75,
        le=2.0,
        description="Multiplier applied to the base interface font size.",
    )
    density: Literal["compact", "comfortable", "spacious"] = Field(default="comfortable")
    show_sidebar_labels: bool = Field(
        default=True,
        description="Whether the navigation sidebar displays text labels.",
    )


class LibrarySettings(_StrictModel):
    """Personal library preferences."""

    default_import_mode: Literal["reference", "copy"] = Field(
        default="copy",
        description=(
            "Whether imported files are referenced in place or copied into "
            "the managed library directory by default."
        ),
    )
    auto_extract_text: bool = Field(
        default=True,
        description="Automatically extract text after a document is imported.",
    )
    auto_index_full_text: bool = Field(
        default=True,
        description="Automatically add extracted text to the FTS index.",
    )
    ocr_enabled: bool = Field(
        default=False,
        description=(
            "Whether OCR is permitted. Requires an OCR backend to be "
            "configured; disabled by default because it is resource-intensive."
        ),
    )
    ocr_language: str = Field(
        default="eng",
        min_length=2,
        max_length=16,
        description="Default Tesseract language code for OCR.",
    )
    ocr_dpi: int = Field(
        default=300,
        ge=70,
        le=1200,
        description="Rasterization DPI used for OCR.",
    )
    ocr_max_pages: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum number of pages to OCR per document. None means "
            "every page is processed."
        ),
    )
    max_import_size_mb: int = Field(
        default=512,
        ge=1,
        le=8192,
        description="Maximum permitted size of a single imported file, in MB.",
    )


class SearchSettings(_StrictModel):
    """Academic search preferences."""

    default_result_limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Default number of results requested per source.",
    )
    request_timeout_seconds: float = Field(
        default=20.0,
        ge=1.0,
        le=180.0,
        description="Per-request timeout applied to search providers.",
    )
    max_concurrent_sources: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum number of search providers queried in parallel.",
    )
    deduplicate_results: bool = Field(
        default=True,
        description="Whether to deduplicate results across sources.",
    )
    require_https: bool = Field(
        default=True,
        description=(
            "Whether user-added sources must use HTTPS. HTTP is never "
            "permitted unless this is explicitly disabled for a specific "
            "local-development source."
        ),
    )


class AISettings(_StrictModel):
    """AI provider preferences."""

    default_provider_id: str | None = Field(
        default=None,
        description="Identifier of the default AI provider, if any.",
    )
    default_model_id: str | None = Field(
        default=None,
        description="Identifier of the default model within the default provider.",
    )
    allow_external_providers: bool = Field(
        default=True,
        description=(
            "Whether third-party AI providers may be configured. Local "
            "providers remain available regardless of this setting."
        ),
    )
    send_document_excerpts: bool = Field(
        default=False,
        description=(
            "Whether document excerpts may be transmitted to external AI "
            "providers. Disabled by default; per-request confirmation is "
            "required when disabled."
        ),
    )


class PrivacySettings(_StrictModel):
    """Privacy and data-protection preferences."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_retention_days: int = Field(
        default=14,
        ge=1,
        le=365,
        description="Number of days rotating log files are retained.",
    )
    redact_document_content_in_logs: bool = Field(
        default=True,
        description=(
            "Whether document content is redacted from diagnostic logs. "
            "Must remain enabled unless explicitly overridden for support."
        ),
    )
    store_search_history: bool = Field(
        default=True,
        description="Whether executed search queries are recorded for reuse.",
    )


class NetworkSettings(_StrictModel):
    """Network behavior preferences."""

    offline_mode: bool = Field(
        default=False,
        description="When enabled, no outbound network requests are issued.",
    )
    use_system_proxy: bool = Field(
        default=True,
        description="Whether the operating system proxy configuration is used.",
    )
    user_agent_suffix: str = Field(
        default="",
        max_length=128,
        description=(
            "Optional suffix appended to the HTTP User-Agent header for "
            "requests issued by the application."
        ),
    )


class SettingsSchema(_StrictModel):
    """Root configuration schema.

    The ``schema_version`` field is authoritative for migration. Files whose
    version is lower than ``SETTINGS_SCHEMA_VERSION`` are upgraded by the
    settings service before validation.
    """

    schema_version: int = Field(
        default=SETTINGS_SCHEMA_VERSION,
        ge=1,
        description="On-disk schema version for migration.",
    )
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    library: LibrarySettings = Field(default_factory=LibrarySettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    ai: AISettings = Field(default_factory=AISettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)

    @field_validator("schema_version")
    @classmethod
    def _check_schema_version(cls, value: int) -> int:
        if value > SETTINGS_SCHEMA_VERSION:
            raise ValueError(
                f"Configuration file schema version {value} is newer than "
                f"this application supports ({SETTINGS_SCHEMA_VERSION})."
            )
        return value