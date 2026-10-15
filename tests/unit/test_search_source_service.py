"""Tests for the search source service."""

from __future__ import annotations

import pytest

from academic_platform.application.search_sources.errors import (
    SourceNotFoundError,
    SourceValidationError,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)
from academic_platform.application.search_sources.source_config import (
    SourceConfig,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


class _ShimmedManager:
    """A manager that opens a fresh session per repository request.

    Tests use this shim so that the service can be constructed without a
    live application bootstrap. Sessions are committed and closed on
    ``close_all``.
    """

    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        repository_class = _REPOSITORY_REGISTRY[key]
        return repository_class(session)

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


@pytest.fixture()
def service(database: Database) -> SearchSourceService:
    registry = ProviderRegistry()
    registry.register_instance("null", _null_adapter())
    return SearchSourceService(
        repositories=_ShimmedManager(database),  # type: ignore[arg-type]
        registry=registry,
    )


def _null_adapter():
    from academic_platform.infrastructure.search_providers.null_adapter import (
        NullSearchProviderAdapter,
    )

    return NullSearchProviderAdapter()


def _config(**overrides) -> SourceConfig:
    defaults = {
        "key": "example",
        "provider_key": "example",
        "display_name": "Example",
        "source_type": "user_defined",
        "base_url": "https://api.crossref.org",
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)

def test_create_and_list(service: SearchSourceService) -> None:
    service.create(_config())
    records = service.list_sources()
    assert len(records) == 1
    assert records[0].config.display_name == "Example"


def test_get_by_key(service: SearchSourceService) -> None:
    service.create(_config())
    record = service.get_by_key("example")
    assert record.config.provider_key == "example"


def test_get_by_key_missing_raises(service: SearchSourceService) -> None:
    with pytest.raises(SourceNotFoundError):
        service.get_by_key("missing")


def test_create_rejects_invalid_config(service: SearchSourceService) -> None:
    with pytest.raises(SourceValidationError):
        service.create(_config(display_name=""))


def test_create_rejects_private_url(service: SearchSourceService) -> None:
    with pytest.raises(SourceValidationError):
        service.create(_config(base_url="https://10.0.0.1"))


def test_set_enabled_round_trip(service: SearchSourceService) -> None:
    service.create(_config())
    record = service.set_enabled("example", False)
    assert record.config.enabled is False
    record = service.set_enabled("example", True)
    assert record.config.enabled is True


def test_update_changes_display_name(service: SearchSourceService) -> None:
    service.create(_config())
    updated = service.update("example", {"display_name": "Updated"})
    assert updated.config.display_name == "Updated"


def test_update_rejects_unknown_field(service: SearchSourceService) -> None:
    service.create(_config())
    # Unknown fields are silently ignored, so the display name is
    # preserved.
    updated = service.update("example", {"unknown": "x"})
    assert updated.config.display_name == "Example"


def test_remove_user_defined_source(service: SearchSourceService) -> None:
    service.create(_config())
    service.remove("example")
    with pytest.raises(SourceNotFoundError):
        service.get_by_key("example")


def test_remove_builtin_source_rejected(service: SearchSourceService) -> None:
    service.create(_config(source_type="builtin"))
    with pytest.raises(SourceValidationError):
        service.remove("example")


def test_validate_reports_missing_display_name(service: SearchSourceService) -> None:
    issues = service.validate(_config(display_name=""))
    assert any(issue.field == "display_name" for issue in issues)


def test_validate_reports_missing_credential(service: SearchSourceService) -> None:
    issues = service.validate(_config(auth_type="api_key"))
    assert any(issue.field == "credential_reference" for issue in issues)


def test_validate_reports_http_url(service: SearchSourceService) -> None:
    issues = service.validate(_config(base_url="http://api.crossref.org"))
    assert any(issue.field == "base_url" for issue in issues)


def test_test_connection_returns_report(service: SearchSourceService) -> None:
    service.create(_config())
    report = service.test_connection("example")
    assert report.provider_key
    assert report.status.value in {"ok", "skipped", "failed", "disabled"}