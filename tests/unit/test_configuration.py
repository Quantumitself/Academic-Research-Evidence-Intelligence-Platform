"""Tests for runtime directory resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.app import configuration


def test_override_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(configuration.ENV_HOME, str(tmp_path / "home"))
    directories = configuration.load_runtime_directories()
    assert directories.root == (tmp_path / "home").resolve()
    assert directories.config_dir.is_dir()
    assert directories.data_dir.is_dir()
    assert directories.logs_dir.is_dir()
    assert directories.cache_dir.is_dir()


def test_directories_are_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "root"
    monkeypatch.setenv(configuration.ENV_HOME, str(target))
    directories = configuration.load_runtime_directories()
    for path in (
        directories.config_dir,
        directories.data_dir,
        directories.logs_dir,
        directories.cache_dir,
    ):
        assert path.exists()
        assert path.is_dir()


def test_file_in_place_of_directory_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "home"
    target.mkdir()
    (target / "config").write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv(configuration.ENV_HOME, str(target))
    with pytest.raises(configuration.ConfigurationError):
        configuration.load_runtime_directories()


def test_derived_paths_are_under_expected_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(configuration.ENV_HOME, str(tmp_path / "home"))
    directories = configuration.load_runtime_directories()
    assert directories.config_file.parent == directories.config_dir
    assert directories.database_file.parent == directories.data_dir
    assert directories.managed_library_dir.parent == directories.data_dir
    assert directories.exports_dir.parent == directories.data_dir
    assert directories.config_file.name == configuration.APP_CONFIG_FILENAME