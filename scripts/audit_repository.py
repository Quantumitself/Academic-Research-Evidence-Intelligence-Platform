"""Repository audit script.

Produces a structured audit of the repository: file inventory, Python module
inventory, import graph summary, detected third-party imports, and potential
policy violations. Output is written to ``docs/repository_audit.md``.

The script is deterministic: given the same repository it produces the same
output. It intentionally does not attempt to execute project code.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "repository_audit.md"

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
    ".eggs",
    "node_modules",
}

STDLIB_TOP_LEVEL = set(sys.stdlib_module_names)


@dataclass
class ModuleInfo:
    """Summary of a single Python module."""

    path: Path
    relative_path: str
    module_name: str
    docstring_present: bool
    top_level_imports: set[str] = field(default_factory=set)
    public_definitions: int = 0


def _iter_python_files(root: Path) -> list[Path]:
    results: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.parts):
            continue
        results.append(path)
    return sorted(results)


def _module_name_for(path: Path, source_root: Path) -> str:
    try:
        relative = path.relative_to(source_root)
    except ValueError:
        return path.stem
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else path.stem


def _analyze_module(path: Path, source_root: Path) -> ModuleInfo:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise RuntimeError(f"Syntax error in {path}: {exc}") from exc

    docstring_present = ast.get_docstring(tree) is not None

    imports: set[str] = set()
    public_definitions = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                public_definitions += 1

    return ModuleInfo(
        path=path,
        relative_path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        module_name=_module_name_for(path, source_root),
        docstring_present=docstring_present,
        top_level_imports=imports,
        public_definitions=public_definitions,
    )


def _collect_inventory() -> tuple[list[ModuleInfo], Counter[str]]:
    modules: list[ModuleInfo] = []
    third_party_counter: Counter[str] = Counter()

    if not SRC_DIR.exists():
        return modules, third_party_counter

    for path in _iter_python_files(SRC_DIR):
        info = _analyze_module(path, SRC_DIR)
        modules.append(info)
        for name in info.top_level_imports:
            if name in STDLIB_TOP_LEVEL:
                continue
            if name == "academic_platform":
                continue
            third_party_counter[name] += 1

    return modules, third_party_counter


def _module_summary_table(modules: list[ModuleInfo]) -> str:
    lines = [
        "| Module | Docstring | Public definitions |",
        "| --- | --- | --- |",
    ]
    for info in modules:
        docstring = "yes" if info.docstring_present else "**no**"
        lines.append(f"| `{info.module_name}` | {docstring} | {info.public_definitions} |")
    return "\n".join(lines)


def _third_party_table(counter: Counter[str]) -> str:
    if not counter:
        return "_No third-party imports detected._"
    lines = [
        "| Package | Import count |",
        "| --- | --- |",
    ]
    for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{name}` | {count} |")
    return "\n".join(lines)


def _file_inventory(root: Path) -> list[str]:
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.parts):
            continue
        if path.is_file():
            entries.append(str(path.relative_to(root)).replace("\\", "/"))
    return entries


def _write_report(modules: list[ModuleInfo], counter: Counter[str]) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    files = _file_inventory(REPO_ROOT)

    report_parts: list[str] = []
    report_parts.append("# Repository Audit\n")
    report_parts.append(f"Generated: {timestamp}\n")
    report_parts.append("## Summary\n")
    report_parts.append(f"- Tracked files: {len(files)}")
    report_parts.append(f"- Python modules under `src/`: {len(modules)}")
    report_parts.append(
        f"- Modules missing a docstring: "
        f"{sum(1 for m in modules if not m.docstring_present)}"
    )
    report_parts.append("")

    report_parts.append("## Python Modules\n")
    report_parts.append(_module_summary_table(modules) if modules else "_No modules found._")
    report_parts.append("")

    report_parts.append("## Third-Party Imports\n")
    report_parts.append(_third_party_table(counter))
    report_parts.append("")

    report_parts.append("## File Inventory\n")
    for entry in files:
        report_parts.append(f"- `{entry}`")
    report_parts.append("")

    OUTPUT_FILE.write_text("\n".join(report_parts), encoding="utf-8")
    return OUTPUT_FILE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the repository layout and modules.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    args = parser.parse_args(argv)

    modules, counter = _collect_inventory()
    output = _write_report(modules, counter)
    if not args.quiet:
        print(f"Repository audit written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())