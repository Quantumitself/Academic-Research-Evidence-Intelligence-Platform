"""Smart-collection filter model.

A smart-collection filter is a JSON object describing the collection's
rule. The supported fields are a closed, documented set. The filter is
parsed into an immutable value object before it is applied.

Design decisions
----------------
- Unknown fields are rejected. A silent no-op would hide the user's
  intent; a clear error is more useful.
- Every field is optional. An empty filter matches everything, which is
  the correct behavior for a smart collection with no constraints.
- The filter does not interpret domain semantics. It maps to primitive
  comparisons that the evaluator applies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from academic_platform.application.smart_collections.errors import (
    SmartCollectionFilterError,
)


class SmartFilterField(str, Enum):
    """Supported filter fields."""

    YEAR_FROM = "year_from"
    YEAR_TO = "year_to"
    PROCESSING_STATES = "processing_states"
    EXTENSIONS = "extensions"
    STORAGE_MODES = "storage_modes"
    MISSING = "missing"
    TITLE_CONTAINS = "title_contains"
    AUTHOR_CONTAINS = "author_contains"
    HAS_ANNOTATIONS = "has_annotations"
    HAS_DOI = "has_doi"


_KNOWN_FIELDS = {field.value for field in SmartFilterField}


@dataclass(frozen=True, slots=True)
class SmartCollectionFilter:
    """An immutable description of a smart-collection filter."""

    year_from: int | None = None
    year_to: int | None = None
    processing_states: frozenset[str] = field(default_factory=frozenset)
    extensions: frozenset[str] = field(default_factory=frozenset)
    storage_modes: frozenset[str] = field(default_factory=frozenset)
    missing: bool | None = None
    title_contains: str = ""
    author_contains: str = ""
    has_annotations: bool | None = None
    has_doi: bool | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.year_from is None
            and self.year_to is None
            and not self.processing_states
            and not self.extensions
            and not self.storage_modes
            and self.missing is None
            and not self.title_contains
            and not self.author_contains
            and self.has_annotations is None
            and self.has_doi is None
        )

    @classmethod
    def from_json(cls, raw: str | None) -> "SmartCollectionFilter":
        """Parse a JSON filter payload into a validated filter.

        An empty or ``None`` payload produces an empty filter, which
        matches every document.
        """
        if raw is None or not raw.strip():
            return cls()
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise SmartCollectionFilterError(
                [f"Filter payload is not valid JSON: {exc}"]
            ) from exc
        if not isinstance(parsed, dict):
            raise SmartCollectionFilterError(
                ["Filter payload must be a JSON object"]
            )
        return cls.from_dict(parsed)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SmartCollectionFilter":
        """Validate a filter dictionary and construct a filter."""
        issues: list[str] = []
        unknown = set(payload.keys()) - _KNOWN_FIELDS
        if unknown:
            issues.append(
                "Unknown filter field(s): "
                + ", ".join(sorted(unknown))
                + ". Supported fields: "
                + ", ".join(sorted(_KNOWN_FIELDS))
            )
        year_from = _coerce_int(payload.get("year_from"), "year_from", issues)
        year_to = _coerce_int(payload.get("year_to"), "year_to", issues)
        if (
            year_from is not None
            and year_to is not None
            and year_from > year_to
        ):
            issues.append("year_from must not exceed year_to")
        processing_states = _coerce_str_set(
            payload.get("processing_states"), "processing_states", issues
        )
        extensions = _coerce_str_set(
            payload.get("extensions"), "extensions", issues
        )
        storage_modes = _coerce_str_set(
            payload.get("storage_modes"), "storage_modes", issues
        )
        missing = _coerce_bool(payload.get("missing"), "missing", issues)
        has_annotations = _coerce_bool(
            payload.get("has_annotations"), "has_annotations", issues
        )
        has_doi = _coerce_bool(payload.get("has_doi"), "has_doi", issues)
        title_contains = _coerce_str(
            payload.get("title_contains"), "title_contains", issues
        )
        author_contains = _coerce_str(
            payload.get("author_contains"), "author_contains", issues
        )
        if issues:
            raise SmartCollectionFilterError(issues)
        return cls(
            year_from=year_from,
            year_to=year_to,
            processing_states=frozenset(processing_states),
            extensions=frozenset(extensions),
            storage_modes=frozenset(storage_modes),
            missing=missing,
            title_contains=title_contains,
            author_contains=author_contains,
            has_annotations=has_annotations,
            has_doi=has_doi,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation suitable for JSON serialization."""
        payload: dict[str, Any] = {}
        if self.year_from is not None:
            payload["year_from"] = self.year_from
        if self.year_to is not None:
            payload["year_to"] = self.year_to
        if self.processing_states:
            payload["processing_states"] = sorted(self.processing_states)
        if self.extensions:
            payload["extensions"] = sorted(self.extensions)
        if self.storage_modes:
            payload["storage_modes"] = sorted(self.storage_modes)
        if self.missing is not None:
            payload["missing"] = self.missing
        if self.title_contains:
            payload["title_contains"] = self.title_contains
        if self.author_contains:
            payload["author_contains"] = self.author_contains
        if self.has_annotations is not None:
            payload["has_annotations"] = self.has_annotations
        if self.has_doi is not None:
            payload["has_doi"] = self.has_doi
        return payload


# ----------------------------------------------------------------------
# Coercion helpers
# ----------------------------------------------------------------------
def _coerce_int(value: Any, name: str, issues: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        issues.append(f"{name} must be an integer, not a boolean")
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    issues.append(f"{name} must be an integer")
    return None


def _coerce_bool(value: Any, name: str, issues: list[str]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    issues.append(f"{name} must be a boolean")
    return None


def _coerce_str(value: Any, name: str, issues: list[str]) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        issues.append(f"{name} must be a string")
        return ""
    return value.strip()


def _coerce_str_set(value: Any, name: str, issues: list[str]) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list):
        issues.append(f"{name} must be an array of strings")
        return set()
    result: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            issues.append(f"{name} must be an array of strings")
            return set()
        cleaned = item.strip()
        if cleaned:
            result.add(cleaned.lower() if name == "extensions" else cleaned)
    return result