"""Command-line tool for the ADR subsystem.

Subcommands
-----------
- ``index``: regenerate ``docs/adr/README.md`` from the ADR files.
- ``list``: print a one-line summary per ADR to stdout.
- ``show NUMBER``: print the full record for a single ADR.
- ``search QUERY``: print matching ADRs.
- ``validate``: parse all ADRs and exit non-zero when any file fails.
- ``new TITLE``: create a new ADR file with the next available number.

The tool is safe to invoke from CI. Exit codes:

- 0: success.
- 1: validation failure (unparseable or invalid ADR files).
- 2: usage error or missing repository layout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
ADR_DIR = REPO_ROOT / "docs" / "adr"
INDEX_FILE = ADR_DIR / "README.md"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from academic_platform.app.adr.model import ADRStatus  # noqa: E402
from academic_platform.app.adr.registry import ADRRegistry  # noqa: E402
from academic_platform.app.adr.renderer import (  # noqa: E402
    render_detail,
    render_index,
)

_NEW_ADR_TEMPLATE = """# {number}. {title}

Status: proposed
Date: {date}
Deciders: 

## Context

Describe the situation that requires a decision. Include forces at play,
constraints, and the specific problem being addressed.

## Decision

State the decision in the present tense. Be specific enough that a reader
can tell what was chosen and what was not.

## Consequences

Describe the outcomes of the decision: benefits, drawbacks, follow-up work,
and any new constraints introduced.

## Alternatives

List the options considered and rejected, with the reason each was rejected.

## References

- Add references here (documents, links, prior ADRs).
"""


def _load_registry() -> ADRRegistry:
    if not ADR_DIR.is_dir():
        print(f"ADR directory does not exist: {ADR_DIR}", file=sys.stderr)
        raise SystemExit(2)
    return ADRRegistry.from_directory(ADR_DIR)


def _cmd_index(args: argparse.Namespace) -> int:
    registry = _load_registry()
    rendered = render_index(registry)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(rendered, encoding="utf-8")
    if not args.quiet:
        print(f"ADR index written to {INDEX_FILE}")
    return 1 if registry.errors else 0


def _cmd_list(args: argparse.Namespace) -> int:
    registry = _load_registry()
    for record in registry.records:
        print(f"{record.number}  {record.status.value:<10}  {record.title}")
    for path, message in registry.errors:
        print(f"ERROR  {path.name}: {message}", file=sys.stderr)
    return 1 if registry.errors else 0


def _cmd_show(args: argparse.Namespace) -> int:
    registry = _load_registry()
    record = registry.get(args.number)
    if record is None:
        print(f"No ADR with number {args.number}", file=sys.stderr)
        return 2
    print(render_detail(record))
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    registry = _load_registry()
    matches = registry.search(args.query)
    if not matches:
        print("No matching ADRs.")
        return 0
    for record in matches:
        print(f"{record.number}  {record.status.value:<10}  {record.title}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    registry = _load_registry()
    if not registry.errors:
        if not args.quiet:
            print(f"All {len(registry.records)} ADR(s) valid.")
        return 0
    for path, message in registry.errors:
        print(f"{path.name}: {message}", file=sys.stderr)
    return 1


def _next_number(registry: ADRRegistry) -> str:
    used = {record.number for record in registry.records}
    for candidate in range(1, 10000):
        number = f"{candidate:04d}"
        if number not in used:
            return number
    raise SystemExit("ADR number space exhausted")


def _slugify(title: str) -> str:
    lower = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    return slug or "decision"


def _cmd_new(args: argparse.Namespace) -> int:
    registry = _load_registry()
    number = _next_number(registry)
    slug = _slugify(args.title)
    target = ADR_DIR / f"{number}-{slug}.md"
    if target.exists():
        print(f"File already exists: {target}", file=sys.stderr)
        return 2
    date_value = dt.date.today().isoformat()
    content = _NEW_ADR_TEMPLATE.format(number=number, title=args.title, date=date_value)
    target.write_text(content, encoding="utf-8")
    if not args.quiet:
        print(f"Created {target}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adr",
        description="Architecture Decision Record tooling.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Regenerate the ADR index.")
    index_parser.set_defaults(func=_cmd_index)

    list_parser = subparsers.add_parser("list", help="List all ADRs.")
    list_parser.set_defaults(func=_cmd_list)

    show_parser = subparsers.add_parser("show", help="Show a single ADR.")
    show_parser.add_argument("number", help="Zero-padded ADR number, e.g. 0001.")
    show_parser.set_defaults(func=_cmd_show)

    search_parser = subparsers.add_parser("search", help="Search ADRs.")
    search_parser.add_argument("query", help="Text to search for.")
    search_parser.set_defaults(func=_cmd_search)

    validate_parser = subparsers.add_parser("validate", help="Validate all ADRs.")
    validate_parser.set_defaults(func=_cmd_validate)

    new_parser = subparsers.add_parser("new", help="Create a new ADR.")
    new_parser.add_argument("title", help="Title of the new ADR.")
    new_parser.set_defaults(func=_cmd_new)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())