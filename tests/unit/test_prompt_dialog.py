"""Tests for the PromptDialog component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.dialogs.prompt_dialog import PromptDialog  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_value_trimmed_by_default(app: QApplication) -> None:
    dialog = PromptDialog("T", "L", initial="  hello  ")
    assert dialog.value() == "hello"


def test_value_preserved_when_trim_false(app: QApplication) -> None:
    dialog = PromptDialog("T", "L", initial="  hello  ", trim=False)
    assert dialog.value() == "  hello  "


def test_validator_blocks_ok(app: QApplication) -> None:
    def validator(value: str) -> str | None:
        return None if value else "Required"

    dialog = PromptDialog("T", "L", validator=validator)
    assert not dialog._ok_button.isEnabled()  # noqa: SLF001
    dialog.set_value("ok")
    assert dialog._ok_button.isEnabled()  # noqa: SLF001


def test_validator_error_message_shown(app: QApplication) -> None:
    def validator(value: str) -> str | None:
        return None if len(value) >= 3 else "Too short"

    dialog = PromptDialog("T", "L", validator=validator)
    dialog.set_value("ab")
    assert dialog._error_label.isVisibleTo(dialog)  # noqa: SLF001
    assert dialog._error_label.text() == "Too short"  # noqa: SLF001


def test_no_validator_always_enabled(app: QApplication) -> None:
    dialog = PromptDialog("T", "L")
    assert dialog._ok_button.isEnabled()  # noqa: SLF001