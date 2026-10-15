"""Application entry point.

Responsibilities
----------------
- Normalize the import path so the package is importable from a source
  checkout without an editable install.
- Resolve runtime directories (config, data, logs, cache).
- Initialize logging before any subsystem emits records.
- Fail loudly and safely when the environment is not usable.
- Delegate to the application bootstrap which constructs the UI.

This module must remain free of UI imports at module scope so that running
``python -m academic_platform --audit`` can execute without a display.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Import-path bootstrap. When executed via ``python -m academic_platform``
# from a source checkout, the ``src`` directory is not on sys.path unless the
# package has been installed. Inserting it here keeps the module usable in
# development without an editable install and is a no-op after installation.
if __package__ in {None, ""}:
    _SRC_ROOT = Path(__file__).resolve().parent.parent
    if _SRC_ROOT.is_dir() and str(_SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(_SRC_ROOT))

from academic_platform import __version__
from academic_platform.app.configuration import (
    AppDirectories,
    ConfigurationError,
    load_runtime_directories,
)
from academic_platform.app.logging_setup import configure_logging

EXIT_SUCCESS = 0
EXIT_CONFIGURATION_ERROR = 2
EXIT_UI_UNAVAILABLE = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="academic-platform",
        description="Academic Research & Evidence Intelligence Platform",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Print resolved runtime directories and exit without starting the UI.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the application version and exit.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override the configured log level (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable the rotating file log; console output remains enabled.",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Print the resolved configuration path and effective settings, then exit.",
    )
    return parser


def _print_audit(directories: AppDirectories) -> None:
    print("Resolved runtime directories:")
    print(f"  config : {directories.config_dir}")
    print(f"  data   : {directories.data_dir}")
    print(f"  logs   : {directories.logs_dir}")
    print(f"  cache  : {directories.cache_dir}")

def _print_settings(directories: AppDirectories) -> int:
    """Print the effective settings and exit.

    Returns EXIT_SUCCESS on a valid configuration and EXIT_CONFIGURATION_ERROR
    on a failure, matching the behaviour of the other diagnostic flags.
    """
    import json

    from academic_platform.app.settings import SettingsError, SettingsService

    service = SettingsService(directories.config_file)
    try:
        result = service.load()
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    print(f"Configuration file: {result.path}")
    print(f"Created with defaults: {result.created}")
    if result.migrated_from is not None:
        print(f"Migrated from schema version: {result.migrated_from}")
    print("Effective settings:")
    print(json.dumps(result.settings.model_dump(mode="json"), indent=2, sort_keys=True))
    return EXIT_SUCCESS

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return EXIT_SUCCESS

    try:
        directories = load_runtime_directories()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    configure_logging(
        directories.logs_dir,
        level_override=args.log_level,
        write_to_file=not args.no_log_file,
    )

    if args.audit:
        _print_audit(directories)
        return EXIT_SUCCESS

    if args.settings:
        return _print_settings(directories)

    from academic_platform.app.bootstrap import run_application

    return run_application(directories)


if __name__ == "__main__":
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    raise SystemExit(main())