"""Tests for the ADR command-line tool."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_script():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "adr.py"
    spec = importlib.util.spec_from_file_location("adr_script_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["adr_script_module"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def adr_script():
    return _load_script()


@pytest.fixture(autouse=True)
def _isolate(adr_script, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    monkeypatch.setattr(adr_script, "ADR_DIR", adr_dir)
    monkeypatch.setattr(adr_script, "INDEX_FILE", adr_dir / "README.md")
    yield adr_dir


def test_new_creates_file(adr_script, _isolate) -> None:
    exit_code = adr_script.main(["--quiet", "new", "Test Decision"])
    assert exit_code == 0
    files = list(_isolate.glob("0001-*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Test Decision" in content
    assert "Status: proposed" in content


def test_new_increments_number(adr_script, _isolate) -> None:
    adr_script.main(["--quiet", "new", "First"])
    adr_script.main(["--quiet", "new", "Second"])
    numbers = sorted(path.name[:4] for path in _isolate.glob("*.md") if path.name != "README.md")
    assert numbers == ["0001", "0002"]


def test_list_and_show(adr_script, _isolate, capsys) -> None:
    (adr_script.ADR_DIR / "0001-x.md").write_text(
        "# 0001. X\n\nStatus: accepted\nDate: 2024-01-15\n\n"
        "## Context\n\nc\n\n## Decision\n\nd\n\n## Consequences\n\nk\n",
        encoding="utf-8",
    )
    assert adr_script.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "0001" in out

    assert adr_script.main(["show", "0001"]) == 0
    out = capsys.readouterr().out
    assert "# ADR 0001" in out


def test_validate_detects_bad_file(adr_script, _isolate) -> None:
    (adr_script.ADR_DIR / "0001-bad.md").write_text("# not valid\n", encoding="utf-8")
    exit_code = adr_script.main(["--quiet", "validate"])
    assert exit_code == 1


def test_index_writes_readme(adr_script, _isolate) -> None:
    (adr_script.ADR_DIR / "0001-x.md").write_text(
        "# 0001. X\n\nStatus: accepted\nDate: 2024-01-15\n\n"
        "## Context\n\nc\n\n## Decision\n\nd\n\n## Consequences\n\nk\n",
        encoding="utf-8",
    )
    assert adr_script.main(["--quiet", "index"]) == 0
    assert adr_script.INDEX_FILE.exists()
    assert "0001" in adr_script.INDEX_FILE.read_text(encoding="utf-8")


def test_search_finds_record(adr_script, _isolate, capsys) -> None:
    (adr_script.ADR_DIR / "0001-x.md").write_text(
        "# 0001. Persistence decision\n\nStatus: accepted\nDate: 2024-01-15\n\n"
        "## Context\n\nsqlite\n\n## Decision\n\nd\n\n## Consequences\n\nk\n",
        encoding="utf-8",
    )
    assert adr_script.main(["search", "sqlite"]) == 0
    assert "0001" in capsys.readouterr().out