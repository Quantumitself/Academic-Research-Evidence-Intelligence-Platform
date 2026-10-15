"""Tests for package-level entry points."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


def test_package_exposes_version() -> None:
    package = importlib.import_module("academic_platform")
    assert isinstance(package.__version__, str)
    assert package.__version__


def test_main_module_is_importable_without_qt() -> None:
    # Importing ``academic_platform.main`` must not import PySide6 at module
    # scope; the GUI import happens inside ``run_application``.
    sys.modules.pop("academic_platform.main", None)
    sys.modules.pop("PySide6", None)
    module = importlib.import_module("academic_platform.main")
    assert hasattr(module, "main")
    assert hasattr(module, "EXIT_SUCCESS")


def test_dunder_main_delegates() -> None:
    module = importlib.import_module("academic_platform.__main__")
    assert hasattr(module, "main")