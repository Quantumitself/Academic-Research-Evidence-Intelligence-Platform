"""Dependency inventory script.

Reads ``pyproject.toml`` to enumerate declared dependencies and their
constraints, then writes ``docs/dependency_inventory.md`` containing the
declared set, the development extras, and the detected third-party imports
from the source tree. The purpose is to keep the declared dependency list and
the actual usage aligned.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import sys
import tomllib
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SRC_DIR = REPO_ROOT / "src"
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "dependency_inventory.md"

EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}

STDLIB_TOP_LEVEL = set(sys.stdlib_module_names)


def _load_pyproject() -> dict:
    if not PYPROJECT.exists():
        raise SystemExit(f"Missing pyproject.toml at {PYPROJECT}")
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _project_dependencies(data: dict) -> list[str]:
    project = data.get("project", {})
    deps = list(project.get("dependencies", []))
    return [str(item) for item in deps]


def _dev_dependencies(data: dict) -> list[str]:
    project = data.get("project", {})
    optional = project.get("optional-dependencies", {})
    dev = optional.get("dev", [])
    return [str(item) for item in dev]


def _detected_imports(root: Path) -> Counter[str]:
    counter: Counter[str] = Counter()
    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in STDLIB_TOP_LEVEL or name == "academic_platform":
                        continue
                    counter[name] += 1
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    name = node.module.split(".")[0]
                    if name in STDLIB_TOP_LEVEL or name == "academic_platform":
                        continue
                    counter[name] += 1
    return counter


def _format_dependency_list(items: list[str]) -> str:
    if not items:
        return "_None declared._"
    return "\n".join(f"- `{item}`" for item in items)


def _format_detected(counter: Counter[str]) -> str:
    if not counter:
        return "_No third-party imports detected._"
    lines = [
        "| Import name | Occurrences |",
        "| --- | --- |",
    ]
    for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{name}` | {count} |")
    return "\n".join(lines)


def _write_report(
    runtime_deps: list[str],
    dev_deps: list[str],
    detected: Counter[str],
) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    parts: list[str] = []
    parts.append("# Dependency Inventory\n")
    parts.append(f"Generated: {timestamp}\n")

    parts.append("## Declared Runtime Dependencies\n")
    parts.append(_format_dependency_list(runtime_deps))
    parts.append("")

    parts.append("## Declared Development Dependencies\n")
    parts.append(_format_dependency_list(dev_deps))
    parts.append("")

    parts.append("## Detected Third-Party Imports\n")
    parts.append(_format_detected(detected))
    parts.append("")

    parts.append("## Policy\n")
    parts.append(
        "Every detected third-party import must correspond to a declared "
        "dependency. Additions require a documented purpose in "
        "`docs/architecture.md` and, where relevant, a license review entry."
    )
    parts.append("")

    OUTPUT_FILE.write_text("\n".join(parts), encoding="utf-8")
    return OUTPUT_FILE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate dependency inventory.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    data = _load_pyproject()
    runtime_deps = _project_dependencies(data)
    dev_deps = _dev_dependencies(data)
    detected = _detected_imports(SRC_DIR) if SRC_DIR.exists() else Counter()

    output = _write_report(runtime_deps, dev_deps, detected)
    if not args.quiet:
        print(f"Dependency inventory written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())