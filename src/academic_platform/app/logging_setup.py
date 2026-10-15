"""Logging configuration for the application.

Design decisions
----------------
- File logging uses a rotating handler so long-running sessions do not
  exhaust disk space. The file handler is optional so that headless runs
  (for example, ``--no-log-file``) do not depend on a writable logs
  directory.
- Console logging is always attached so that command-line usage remains
  useful.
- Third-party libraries that emit verbose logs at DEBUG are pinned to
  WARNING unless the application is explicitly running at DEBUG level.
- The log format includes module, function, and line number, which is
  required for reproducible diagnostics in issue reports.
- Handler installation is idempotent: calling ``configure_logging`` twice
  replaces prior handlers rather than stacking them.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_LOG_FILENAME = "academic_platform.log"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_VERBOSE_LIBRARIES = (
    "httpx",
    "httpcore",
    "urllib3",
    "sqlalchemy.engine",
    "matplotlib",
    "PIL",
)

_configured = False


def _resolve_level(level_override: str | None) -> int:
    if level_override is None:
        return logging.INFO
    candidate = level_override.strip().upper()
    resolved = logging.getLevelName(candidate)
    if isinstance(resolved, int):
        return resolved
    return logging.INFO


def _reset_root_handlers() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # noqa: BLE001 - best-effort close during reset
            pass


def configure_logging(
    logs_dir: Path | None,
    level_override: str | None = None,
    write_to_file: bool = True,
) -> None:
    """Install the application logging configuration.

    Parameters
    ----------
    logs_dir:
        Directory where the rotating log file is written. Ignored when
        ``write_to_file`` is False. May be None only when
        ``write_to_file`` is False.
    level_override:
        Optional textual log level. Unknown values fall back to INFO.
    write_to_file:
        When False, only the console handler is installed. This is used by
        the ``--no-log-file`` command-line flag and by tests that must not
        depend on writable storage.
    """
    global _configured

    level = _resolve_level(level_override)
    formatter = logging.Formatter(fmt=_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    _reset_root_handlers()

    if write_to_file:
        if logs_dir is None:
            raise ValueError("logs_dir must be provided when write_to_file is True")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / _LOG_FILENAME
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root.addHandler(console_handler)

    for name in _VERBOSE_LIBRARIES:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))

    _configured = True
    logging.getLogger(__name__).info(
        "Logging configured at level %s (file=%s)",
        logging.getLevelName(level),
        write_to_file,
    )