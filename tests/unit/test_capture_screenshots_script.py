"""Tests for the screenshot capture script's parsing and manifest logic."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "capture_screenshots.py"
    spec = importlib.util.spec_from_file_location("capture_screenshots_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture_screenshots_module"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


def test_size_parser_accepts_valid(script) -> None:
    assert script._parse_size("1280x800") == (1280, 800)


def test_size_parser_rejects_malformed(script) -> None:
    with pytest.raises(Exception):
        script._parse_size("not-a-size")


def test_size_parser_rejects_zero(script) -> None:
    with pytest.raises(Exception):
        script._parse_size("0x100")


def test_manifest_filename_is_stable(script) -> None:
    assert script.MANIFEST_FILENAME == "manifest.json"