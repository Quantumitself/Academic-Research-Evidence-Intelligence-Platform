"""Tests for the Alembic environment module's helper functions.

The environment module is designed to be executed by Alembic, which sets
up ``alembic.context`` before importing it. To test the helper functions
in isolation, this test loads the module's source and extracts the two
pure functions (``resolve_database_url`` and ``_load_target_metadata``)
without executing the Alembic-specific module-level code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _source_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "migrations" / "env.py"


def _extract_function_source(name: str) -> str:
    """Return the source of a single top-level function by name."""
    source = _source_path().read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"Function {name} not found in migrations/env.py")


def test_env_module_parses() -> None:
    """The environment module must be syntactically valid."""
    source = _source_path().read_text(encoding="utf-8")
    ast.parse(source)


def test_resolve_database_url_honours_override() -> None:
    """``resolve_database_url`` must return the override verbatim."""
    namespace: dict = {}
    exec(
        "from __future__ import annotations\n"
        + _extract_function_source("resolve_database_url"),
        namespace,
    )
    resolve = namespace["resolve_database_url"]
    assert resolve("sqlite://") == "sqlite://"
    assert resolve("sqlite:///tmp/x.sqlite3") == "sqlite:///tmp/x.sqlite3"


def test_resolve_database_url_uses_runtime_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an override, the URL must derive from the runtime directories."""

    class _StubConfig:
        @staticmethod
        def get_main_option(_name: str) -> str:
            return ""

    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    namespace: dict = {"config": _StubConfig()}
    exec(
        "from __future__ import annotations\n"
        "from academic_platform.app.configuration import AppDirectories, "
        "load_runtime_directories\n"
        + _extract_function_source("resolve_database_url"),
        namespace,
    )
    resolve = namespace["resolve_database_url"]
    url = resolve()
    assert url.startswith("sqlite:///")
    assert "academic_platform.sqlite3" in url