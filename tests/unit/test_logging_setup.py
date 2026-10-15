"""Tests for logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from academic_platform.app import logging_setup


@pytest.fixture(autouse=True)
def _reset_logging_state() -> None:
    logging_setup._configured = False  # noqa: SLF001 - test reset
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    logging_setup._configured = False  # noqa: SLF001 - test reset


def test_logging_writes_file(tmp_path: Path) -> None:
    logging_setup.configure_logging(tmp_path, level_override="DEBUG")
    logger = logging.getLogger("test_logging_writes_file")
    logger.info("hello")
    for handler in logging.getLogger().handlers:
        handler.flush()
    log_file = tmp_path / "academic_platform.log"
    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")


def test_unknown_level_falls_back_to_info(tmp_path: Path) -> None:
    logging_setup.configure_logging(tmp_path, level_override="NOTALEVEL")
    assert logging.getLogger().level == logging.INFO


def test_console_only_mode_creates_no_file(tmp_path: Path) -> None:
    logging_setup.configure_logging(
        logs_dir=None,
        level_override="INFO",
        write_to_file=False,
    )
    log_file = tmp_path / "academic_platform.log"
    assert not log_file.exists()


def test_reconfiguration_does_not_stack_handlers(tmp_path: Path) -> None:
    logging_setup.configure_logging(tmp_path)
    first = len(logging.getLogger().handlers)
    logging_setup._configured = False  # noqa: SLF001 - test reset
    logging_setup.configure_logging(tmp_path)
    second = len(logging.getLogger().handlers)
    assert first == second


def test_write_to_file_requires_directory() -> None:
    with pytest.raises(ValueError):
        logging_setup.configure_logging(logs_dir=None, write_to_file=True)