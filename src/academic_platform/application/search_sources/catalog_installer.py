"""Install the built-in source catalog into the database.

The installer is idempotent. It creates missing built-in sources and
refreshes the display-level fields of existing ones. It never removes a
built-in source, and it never modifies a user-defined source.

Design decisions
----------------
- Installation runs during application startup, after migrations and
  after settings reconciliation. A failure is reported and does not
  prevent the UI from starting; the search page falls back to the null
  adapter.
- Existing built-in sources keep their user-editable fields (enabled,
  result_limit, timeout_seconds). Only the display-level fields that the
  application ships (display_name, base_url, endpoint, parameter_map,
  capabilities) are refreshed. This is a deliberate choice: the user
  can change the enabled state and the limits of a built-in source
  without losing those changes on the next application start.
"""

from __future__ import annotations

import json
import logging

from academic_platform.application.search_sources.catalog import (
    BUILTIN_SOURCES,
    BuiltinSource,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)

_logger = logging.getLogger(__name__)


class CatalogInstaller:
    """Install built-in sources into the database."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    def install(self) -> tuple[int, int]:
        """Install the catalog.

        Returns ``(created, refreshed)``. A source that already exists is
        refreshed only when its display-level fields differ from the
        catalog.
        """
        created = 0
        refreshed = 0
        for entry in BUILTIN_SOURCES:
            outcome = self._install_entry(entry)
            if outcome == "created":
                created += 1
            elif outcome == "refreshed":
                refreshed += 1
        return created, refreshed

    def _install_entry(self, entry: BuiltinSource) -> str:
        repo = self._repositories.get("search_source")
        existing = repo.find_by_key(entry.config.key)
        if existing is None:
            repo.create(_create_payload(entry))
            _logger.info("Installed built-in source %s", entry.config.key)
            return "created"
        if _needs_refresh(existing, entry):
            repo.update(existing, _update_payload(entry))
            _logger.info("Refreshed built-in source %s", entry.config.key)
            return "refreshed"
        return "unchanged"


def _create_payload(entry: BuiltinSource):
    from academic_platform.infrastructure.database.schemas import (
        SearchSourceCreate,
    )

    config = entry.config
    return SearchSourceCreate(
        key=config.key,
        provider_key=config.provider_key,
        display_name=config.display_name,
        source_type=config.source_type,
        base_url=config.base_url,
        endpoint=config.endpoint,
        http_method=config.http_method,
        parameter_map_json=json.dumps(config.parameter_map),
        capabilities_json=json.dumps(config.capabilities),
        rate_limit_json=json.dumps(config.rate_limit) if config.rate_limit else None,
        auth_type=config.auth_type,
        credential_reference=config.credential_reference,
        enabled=config.enabled,
        timeout_seconds=config.timeout_seconds,
        result_limit=config.result_limit,
    )


def _update_payload(entry: BuiltinSource):
    from academic_platform.infrastructure.database.schemas import (
        SearchSourceUpdate,
    )

    config = entry.config
    return SearchSourceUpdate(
        display_name=config.display_name,
        base_url=config.base_url,
        endpoint=config.endpoint,
        http_method=config.http_method,
        parameter_map_json=json.dumps(config.parameter_map),
        capabilities_json=json.dumps(config.capabilities),
        rate_limit_json=json.dumps(config.rate_limit) if config.rate_limit else None,
    )


def _needs_refresh(existing, entry: BuiltinSource) -> bool:
    config = entry.config
    return (
        existing.display_name != config.display_name
        or existing.base_url != config.base_url
        or existing.endpoint != config.endpoint
        or existing.http_method != config.http_method
        or existing.parameter_map_json != json.dumps(config.parameter_map)
        or existing.capabilities_json != json.dumps(config.capabilities)
    )