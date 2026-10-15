"""Tests for the FormDialog component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.ui.dialogs.form_dialog import (  # noqa: E402
    FormDialog,
    FormField,
    FormFieldKind,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _fields() -> tuple[FormField, ...]:
    return (
        FormField("name", "Name", FormFieldKind.TEXT, initial="Init"),
        FormField("notes", "Notes", FormFieldKind.MULTILINE),
        FormField("active", "Active", FormFieldKind.CHECKBOX, initial="true"),
        FormField(
            "kind",
            "Kind",
            FormFieldKind.SELECT,
            options=(("a", "Alpha"), ("b", "Beta")),
            initial="b",
        ),
    )


def test_values_round_trip(app: QApplication) -> None:
    dialog = FormDialog("T", _fields())
    values = dialog.values()
    assert values["name"] == "Init"
    assert values["notes"] == ""
    assert values["active"] is True
    assert values["kind"] == "b"


def test_validator_blocks_submit(app: QApplication) -> None:
    def validator(value: str) -> str | None:
        return None if value else "Required"

    fields = (FormField("name", "Name", FormFieldKind.TEXT, validator=validator),)
    dialog = FormDialog("T", fields)
    assert not dialog._submit_button.isEnabled()  # noqa: SLF001
    dialog._text_inputs["name"].setText("x")  # noqa: SLF001
    assert dialog._submit_button.isEnabled()  # noqa: SLF001


def test_multiple_validators_block_until_all_pass(app: QApplication) -> None:
    def required(value: str) -> str | None:
        return None if value else "Required"

    fields = (
        FormField("a", "A", FormFieldKind.TEXT, validator=required),
        FormField("b", "B", FormFieldKind.TEXT, validator=required),
    )
    dialog = FormDialog("T", fields)
    dialog._text_inputs["a"].setText("x")  # noqa: SLF001
    assert not dialog._submit_button.isEnabled()  # noqa: SLF001
    dialog._text_inputs["b"].setText("y")  # noqa: SLF001
    assert dialog._submit_button.isEnabled()  # noqa: SLF001


def test_checkbox_label_hidden(app: QApplication) -> None:
    dialog = FormDialog(
        "T",
        (FormField("active", "Active", FormFieldKind.CHECKBOX),),
    )
    from PySide6.QtWidgets import QLabel

    labels = dialog.findChildren(QLabel, "formDialogFieldLabel")
    assert labels
    assert not labels[0].isVisible()