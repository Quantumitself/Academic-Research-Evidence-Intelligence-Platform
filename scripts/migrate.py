"""Migration command-line tool.

Subcommands
-----------
- ``upgrade``: upgrade the database to the latest revision. Optional
  ``--revision`` targets a specific revision.
- ``downgrade REVISION``: downgrade the database to the named revision.
  Use ``base`` to revert every migration.
- ``current``: print the current revision.
- ``head``: print the head revision declared in the migrations directory.

The tool operates on the application database by default. The ``--url``
flag overrides the URL, which is useful for inspecting a temporary
database.

Exit codes
----------
- 0: success.
- 1: migration or inspection failure.
- 2: usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _resolve_url(override: str | None) -> str:
    if override:
        return override
    from academic_platform.app.configuration import load_runtime_directories

    directories = load_runtime_directories()
    return f"sqlite:///{directories.database_file.as_posix()}"


def _cmd_upgrade(args: argparse.Namespace) -> int:
    from academic_platform.infrastructure.database.migrations import (
        DatabaseMigrationError,
        upgrade_to_head,
    )

    url = _resolve_url(args.url)
    try:
        result = upgrade_to_head(url)
    except DatabaseMigrationError as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        if result.changed:
            print(
                f"Upgraded from {result.previous_revision or '<none>'} "
                f"to {result.current_revision or '<none>'} "
                f"(head={result.head_revision or '<none>'})"
            )
        else:
            print(
                f"Already at revision {result.current_revision or '<none>'}"
            )
    return 0


def _cmd_downgrade(args: argparse.Namespace) -> int:
    from academic_platform.infrastructure.database.migrations import (
        DatabaseMigrationError,
        downgrade,
    )

    url = _resolve_url(args.url)
    try:
        result = downgrade(url, args.revision)
    except DatabaseMigrationError as exc:
        print(f"Downgrade failed: {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(
            f"Downgraded from {result.previous_revision or '<none>'} "
            f"to {result.current_revision or '<none>'}"
        )
    return 0


def _cmd_current(args: argparse.Namespace) -> int:
    from academic_platform.infrastructure.database.migrations import current_revision

    url = _resolve_url(args.url)
    print(current_revision(url) or "<none>")
    return 0


def _cmd_head(args: argparse.Namespace) -> int:
    from academic_platform.infrastructure.database.migrations import head_revision

    url = _resolve_url(args.url)
    print(head_revision(url) or "<none>")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate",
        description="Manage database migrations.",
    )
    parser.add_argument("--url", default=None, help="Override the database URL.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade to head.")
    upgrade_parser.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    upgrade_parser.add_argument("--url", default=None, help="Override the database URL.")
    upgrade_parser.set_defaults(func=_cmd_upgrade)

    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade to a revision.")
    downgrade_parser.add_argument("revision", help="Target revision or 'base'.")
    downgrade_parser.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    downgrade_parser.add_argument("--url", default=None, help="Override the database URL.")
    downgrade_parser.set_defaults(func=_cmd_downgrade)

    current_parser = subparsers.add_parser("current", help="Print the current revision.")
    current_parser.add_argument("--url", default=None, help="Override the database URL.")
    current_parser.set_defaults(func=_cmd_current)

    head_parser = subparsers.add_parser("head", help="Print the head revision.")
    head_parser.add_argument("--url", default=None, help="Override the database URL.")
    head_parser.set_defaults(func=_cmd_head)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Subcommand-level flags use ``argparse.SUPPRESS`` as their default so
    # they do not overwrite a top-level value. If a top-level flag was not
    # given either, provide the default here.
    if not hasattr(args, "quiet"):
        args.quiet = False
    if not hasattr(args, "url"):
        args.url = None
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())