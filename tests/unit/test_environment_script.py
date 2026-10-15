"""Tests for the environment validation script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script(module_name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_environment_check_passes_python_and_layout() -> None:
    module = _load_script("validate_environment_module", "scripts/validate_environment.py")
    exit_code = module.main(["--skip-packages"])
    assert exit_code == 0