"""Application service for search source configuration.

The service is the single entry point the presentation layer uses to
list, enable, disable, test, and validate search sources. It is
constructed with a repository manager, a provider registry, and (when
available) the application's settings service so that it can honour the
user's HTTP and loopback preferences.

Design decisions
----------------
- The service never imports Qt. It emits plain data and raises typed
  exceptions; the presentation layer translates those to UI feedback.
- The service validates URLs before persisting them. Validation is
  fail-closed: a URL that fails validation is not persisted.
- Testing a source is a synchronous call. The presentation layer
  executes it on a worker thread; the service itself does not schedule
  work.
- The service produces value objects (``SourceRecord`` and
  ``SourceConfig``) rather than ORM instances. Callers never see ORM
  state.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from academic_platform.application.search_sources.errors import (
    SourceNotFoundError,
    SourceValidationError,
)
from academic_platform.application.search_sources.source_config import (
    SourceConfig,
    SourceRecord,
)
from academic_platform.application.search_sources.source_resolver import (
    SourceResolver,
)
from academic_platform.infrastructure.database.models import SearchSource
from academic_platform.infrastructure.database.schemas import (
    SearchSourceCreate,
    SearchSourceUpdate,
)
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.search_providers.adapter import (
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)
from academic_platform.infrastructure.search_providers.url_validator import (
    validate_url,
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from academic_platform.application.publications.service import (
        PublicationService,
    )



_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceValidationIssue:
    """A single validation issue for a source configuration."""

    field: str
    message: str


class SearchSourceService:
    """Application service for managing search sources."""

    def __init__(
        self,
        repositories: RepositoryManager,
        registry: ProviderRegistry,
        *,
        allow_http: bool = False,
        allow_loopback: bool = False,
    ) -> None:
        from academic_platform.application.publications.service import (
            PublicationService,
        )
        self._repositories = repositories
        self._registry = registry
        self._allow_http = allow_http
        self._allow_loopback = allow_loopback
        self._resolver = SourceResolver(registry)
        self._publications = PublicationService(repositories)

    @property
    def publications(self) -> PublicationService:
        return self._publications

    @property
    def resolver(self) -> SourceResolver:
        """Return the source resolver used to construct provider adapters."""
        return self._resolver

    @contextmanager
    def _operation(self) -> Iterator[None]:
        """Wrap an operation in a transaction boundary.

        Repositories obtained through the manager are bound to a session
        that is opened on first access and closed when the operation
        completes. The manager is responsible for its own transaction
        boundary; the service does not commit or roll back explicitly.
        """
        try:
            yield
        finally:
            manager = self._repositories
            close_all = getattr(manager, "close_all", None)
            if callable(close_all):
                close_all()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_sources(self) -> list[SourceRecord]:
        """Return every configured source ordered by display name."""
        with self._operation():
            repo = self._source_repository()
            rows = repo.list_all_ordered()
            return [self._to_record(row) for row in rows]

    def list_enabled(self) -> list[SourceRecord]:
        """Return enabled sources ordered by display name."""
        with self._operation():
            repo = self._source_repository()
            rows = repo.list_enabled()
            return [self._to_record(row) for row in rows]

    def get_by_key(self, key: str) -> SourceRecord:
        """Return the source with the given key.

        Raises
        ------
        SourceNotFoundError
            If no source matches the key.
        """
        with self._operation():
            repo = self._source_repository()
            row = repo.find_by_key(key)
            if row is None:
                raise SourceNotFoundError(f"No source with key {key!r}")
            return self._to_record(row)

    def get_by_provider_key(self, provider_key: str) -> SourceRecord | None:
        """Return the source with the given provider key, or ``None``."""
        with self._operation():
            repo = self._source_repository()
            row = repo.find_by_provider_key(provider_key)
            return self._to_record(row) if row is not None else None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self, config: SourceConfig) -> list[SourceValidationIssue]:
        """Validate a source configuration without persisting it."""
        issues: list[SourceValidationIssue] = []
        if not config.key.strip():
            issues.append(SourceValidationIssue("key", "Key must not be empty"))
        if not config.provider_key.strip():
            issues.append(
                SourceValidationIssue("provider_key", "Provider key must not be empty")
            )
        if not config.display_name.strip():
            issues.append(
                SourceValidationIssue(
                    "display_name", "Display name must not be empty"
                )
            )
        if config.source_type not in {"builtin", "user_defined"}:
            issues.append(
                SourceValidationIssue(
                    "source_type",
                    "Source type must be 'builtin' or 'user_defined'",
                )
            )
        if config.timeout_seconds < 1 or config.timeout_seconds > 180:
            issues.append(
                SourceValidationIssue(
                    "timeout_seconds", "Timeout must be between 1 and 180 seconds"
                )
            )
        if config.result_limit < 1 or config.result_limit > 500:
            issues.append(
                SourceValidationIssue(
                    "result_limit", "Result limit must be between 1 and 500"
                )
            )
        if config.auth_type not in {"none", "api_key", "bearer_token"}:
            issues.append(
                SourceValidationIssue("auth_type", "Auth type is not supported")
            )
        if config.auth_type != "none" and not config.credential_reference:
            issues.append(
                SourceValidationIssue(
                    "credential_reference",
                    "A credential reference is required when authentication is enabled",
                )
            )
        url_result = validate_url(
            config.base_url,
            allow_http=self._allow_http,
            allow_loopback=self._allow_loopback,
        )
        if not url_result.ok:
            issues.append(SourceValidationIssue("base_url", url_result.message))
        if config.endpoint:
            endpoint_url = config.base_url.rstrip("/") + "/" + config.endpoint.lstrip("/")
            endpoint_result = validate_url(
                endpoint_url,
                allow_http=self._allow_http,
                allow_loopback=self._allow_loopback,
            )
            if not endpoint_result.ok:
                issues.append(
                    SourceValidationIssue("endpoint", endpoint_result.message)
                )
        return issues

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create(self, config: SourceConfig) -> SourceRecord:
        """Persist a new source.

        Raises
        ------
        SourceValidationError
            If the configuration fails validation.
        """
        issues = self.validate(config)
        if issues:
            raise SourceValidationError([i.message for i in issues])
        with self._operation():
            repo = self._source_repository()
            payload = SearchSourceCreate(
                key=config.key,
                provider_key=config.provider_key,
                display_name=config.display_name,
                source_type=config.source_type,
                base_url=config.base_url,
                endpoint=config.endpoint,
                http_method=config.http_method,
                parameter_map_json=json.dumps(config.parameter_map),
                capabilities_json=json.dumps(config.capabilities),
                rate_limit_json=json.dumps(config.rate_limit)
                if config.rate_limit
                else None,
                auth_type=config.auth_type,
                credential_reference=config.credential_reference,
                enabled=config.enabled,
                timeout_seconds=config.timeout_seconds,
                result_limit=config.result_limit,
            )
            try:
                row = repo.create(payload)
            except DuplicateEntityError as exc:
                raise SourceValidationError(
                    [f"A source with key or provider key already exists: {exc}"]
                ) from exc
            self._resolver.invalidate(config.key)
            return self._to_record(row)

    def update(self, key: str, changes: dict[str, Any]) -> SourceRecord:
        """Apply changes to an existing source.

        Only the fields present in ``changes`` are modified. The
        resulting configuration is validated before persisting.
        """
        with self._operation():
            repo = self._source_repository()
            existing = repo.find_by_key(key)
            if existing is None:
                raise SourceNotFoundError(f"No source with key {key!r}")
            current = self._config_from_row(existing)
            merged = self._merge_config(current, changes)
            issues = self.validate(merged)
            if issues:
                raise SourceValidationError([i.message for i in issues])
            payload = SearchSourceUpdate(
                display_name=merged.display_name,
                base_url=merged.base_url,
                endpoint=merged.endpoint,
                http_method=merged.http_method,
                parameter_map_json=json.dumps(merged.parameter_map),
                capabilities_json=json.dumps(merged.capabilities),
                rate_limit_json=json.dumps(merged.rate_limit)
                if merged.rate_limit
                else None,
                auth_type=merged.auth_type,
                credential_reference=merged.credential_reference,
                enabled=merged.enabled,
                timeout_seconds=merged.timeout_seconds,
                result_limit=merged.result_limit,
            )
            try:
                row = repo.update(existing, payload)
            except DuplicateEntityError as exc:
                raise SourceValidationError([str(exc)]) from exc
            self._resolver.invalidate(key)
            return self._to_record(row)

    def set_enabled(self, key: str, enabled: bool) -> SourceRecord:
        """Enable or disable a source by key."""
        with self._operation():
            repo = self._source_repository()
            row = repo.find_by_key(key)
            if row is None:
                raise SourceNotFoundError(f"No source with key {key!r}")
            updated = repo.set_enabled(row.id, enabled)
            self._resolver.invalidate(key)
            return self._to_record(updated)

    def remove(self, key: str) -> None:
        """Remove a user-defined source.

        Built-in sources cannot be removed; they may only be disabled.
        Attempting to remove a built-in source raises
        ``SourceValidationError``.
        """
        with self._operation():
            repo = self._source_repository()
            row = repo.find_by_key(key)
            if row is None:
                raise SourceNotFoundError(f"No source with key {key!r}")
            if row.source_type == "builtin":
                raise SourceValidationError(
                    [f"Built-in source {key!r} cannot be removed; disable it instead"]
                )
            try:
                repo.delete(row)
            except RepositoryError as exc:
                raise SourceValidationError([str(exc)]) from exc
            self._resolver.invalidate(key)

    # ------------------------------------------------------------------
    # Testing
    # ------------------------------------------------------------------
    def test_connection(self, key: str) -> SourceStatusReport:
        """Test connectivity for a source by key."""
        record = self.get_by_key(key)
        adapter = self._resolver.resolve(record.config)
        report = adapter.test_connection()
        self._record_test_outcome(record, report)
        return report

    def _record_test_outcome(
        self,
        record: SourceRecord,
        report: SourceStatusReport,
    ) -> None:
        import datetime as dt

        with self._operation():
            repo = self._source_repository()
            try:
                repo.record_test_result(
                    record.id,
                    tested_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    error=report.message if report.status.value != "ok" else None,
                )
            except RepositoryError:
                _logger.exception("Failed to record source test outcome")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _source_repository(self):
        return self._repositories.get("search_source")

    def _to_record(self, row: SearchSource) -> SourceRecord:
        return SourceRecord(
            id=row.id,
            config=self._config_from_row(row),
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            version=row.version,
        )

    def _config_from_row(self, row: SearchSource) -> SourceConfig:
        return SourceConfig(
            key=row.key,
            provider_key=row.provider_key,
            display_name=row.display_name,
            source_type=row.source_type,
            base_url=row.base_url,
            endpoint=row.endpoint,
            http_method=row.http_method,
            parameter_map=_safe_json_dict(row.parameter_map_json),
            capabilities=_safe_json_dict(row.capabilities_json),
            rate_limit=_safe_json_dict(row.rate_limit_json) or None,
            auth_type=row.auth_type,
            credential_reference=row.credential_reference,
            enabled=bool(row.enabled),
            timeout_seconds=row.timeout_seconds,
            result_limit=row.result_limit,
            last_tested_at=row.last_tested_at,
            last_error=row.last_error,
        )

    def _merge_config(
        self,
        current: SourceConfig,
        changes: dict[str, Any],
    ) -> SourceConfig:
        allowed = {
            "display_name",
            "base_url",
            "endpoint",
            "http_method",
            "parameter_map",
            "capabilities",
            "rate_limit",
            "auth_type",
            "credential_reference",
            "enabled",
            "timeout_seconds",
            "result_limit",
        }
        merged = current
        for field_name, value in changes.items():
            if field_name not in allowed:
                continue
            merged = _replace_config_field(merged, field_name, value)
        return merged


def _safe_json_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _replace_config_field(
    config: SourceConfig,
    field_name: str,
    value: Any,
) -> SourceConfig:
    data = {
        "key": config.key,
        "provider_key": config.provider_key,
        "display_name": config.display_name,
        "source_type": config.source_type,
        "base_url": config.base_url,
        "endpoint": config.endpoint,
        "http_method": config.http_method,
        "parameter_map": config.parameter_map,
        "capabilities": config.capabilities,
        "rate_limit": config.rate_limit,
        "auth_type": config.auth_type,
        "credential_reference": config.credential_reference,
        "enabled": config.enabled,
        "timeout_seconds": config.timeout_seconds,
        "result_limit": config.result_limit,
        "last_tested_at": config.last_tested_at,
        "last_error": config.last_error,
    }
    data[field_name] = value
    return SourceConfig(**data)