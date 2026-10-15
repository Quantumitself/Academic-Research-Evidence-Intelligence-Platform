"""Tests for the finalized package layout and build metadata."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_pyproject() -> dict:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_package_dir_is_src() -> None:
    data = _load_pyproject()
    assert data["tool"]["setuptools"]["package-dir"][""] == "src"


def test_packages_find_where_is_src() -> None:
    data = _load_pyproject()
    assert data["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]


def test_package_discovery_includes_academic_platform() -> None:
    data = _load_pyproject()
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "academic_platform*" in include


def test_console_script_entry_point_present() -> None:
    data = _load_pyproject()
    scripts = data["project"]["scripts"]
    assert scripts["academic-platform"] == "academic_platform.main:main"


def test_pytest_pythonpath_is_src() -> None:
    data = _load_pyproject()
    assert data["tool"]["pytest"]["ini_options"]["pythonpath"] == ["src"]


def test_expected_markers_are_declared() -> None:
    data = _load_pyproject()
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    declared = {marker.split(":", 1)[0].strip() for marker in markers}
    assert {"integration", "scientific", "ui"} <= declared