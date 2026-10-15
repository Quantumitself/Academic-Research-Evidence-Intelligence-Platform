"""Tests for the settings persistence bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.app.settings import (
    SETTINGS_SCHEMA_VERSION,
    SettingsService,
)
from academic_platform.application.settings_persistence import (
    SettingsPersistenceBridge,
    SettingsPersistenceError,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import UserProfile
from academic_platform.infrastructure.repositories.app_settings_repository import (
    AppSettingsRepository,
)
from academic_platform.infrastructure.repositories.user_profile_repository import (
    UserProfileRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


@pytest.fixture()
def settings_service(tmp_path: Path) -> SettingsService:
    service = SettingsService(tmp_path / "config.toml")
    service.load()
    return service


def _make_bridge(
    settings_service: SettingsService,
    database: Database,
) -> SettingsPersistenceBridge:
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        return bridge


def test_synchronize_mirrors_schema_version(
    settings_service: SettingsService, database: Database
) -> None:
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        # Set the row to an out-of-date version so synchronize has work to do.
        app_repo.upsert(settings_schema_version=1)
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        row = bridge.synchronize()
    assert row.settings_schema_version == SETTINGS_SCHEMA_VERSION


def test_set_active_user_requires_existing_profile(
    settings_service: SettingsService, database: Database
) -> None:
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        with pytest.raises(SettingsPersistenceError):
            bridge.set_active_user("missing")


def test_set_active_user_updates_row(
    settings_service: SettingsService, database: Database
) -> None:
    with database.session() as session:
        profile_repo = UserProfileRepository(session)
        profile_repo.add(UserProfile(key="alice"))
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        row = bridge.set_active_user("alice")
        assert row.active_user_key == "alice"
        assert bridge.get_active_user_key() == "alice"


def test_set_active_user_none_clears(
    settings_service: SettingsService, database: Database
) -> None:
    with database.session() as session:
        profile_repo = UserProfileRepository(session)
        profile_repo.add(UserProfile(key="alice"))
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        bridge.set_active_user("alice")
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        bridge.set_active_user(None)
        assert bridge.get_active_user_key() is None


def test_get_active_user_key_defaults_to_none(
    settings_service: SettingsService, database: Database
) -> None:
    with database.session() as session:
        app_repo = AppSettingsRepository(session)
        profile_repo = UserProfileRepository(session)
        bridge = SettingsPersistenceBridge(
            settings_service=settings_service,
            app_settings_repository=app_repo,
            user_profile_repository=profile_repo,
        )
        assert bridge.get_active_user_key() is None