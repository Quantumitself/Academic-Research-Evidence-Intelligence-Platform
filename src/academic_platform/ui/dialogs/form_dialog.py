"""Multi-field form dialog.

The dialog renders a set of fields from a declarative description and
returns the collected values as a dictionary. Each field has a kind that
determines the widget used. Validation is per-field and synchronous.

Design decisions
----------------
- Field definitions are immutable dataclasses. The dialog does not own the
  schema; the caller defines it.
- The OK button is enabled only when every field passes its validator.
- Values are returned as strings for text and multiline fields, as booleans
  for checkboxes, and as the string identifier for select fields.
- The dialog does not persist anything. The caller is responsible for
  converting the values into domain objects.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class FormFieldKind(str, Enum):
    """Supported field kinds."""

    TEXT = "text"
    MULTILINE = "multiline"
    CHECKBOX = "checkbox"
    SELECT = "select"


@dataclass(frozen=True, slots=True)
class FormField:
    """Declarative description of a single form field."""

    identifier: str
    label: str
    kind: FormFieldKind
    initial: str = ""
    placeholder: str = ""
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    validator: Callable[[str], "str | None"] | None = None
    help_text: str = ""


class FormDialog(QDialog):
    """Modal dialog presenting a set of fields and returning their values."""

    def __init__(
        self,
        title: str,
        fields: tuple[FormField, ...],
        *,
        submit_label: str = "OK",
        cancel_label: str = "Cancel",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("formDialog")
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        self._fields = fields
        self._text_inputs: dict[str, QLineEdit] = {}
        self._multiline_inputs: dict[str, QPlainTextEdit] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._selects: dict[str, QComboBox] = {}
        self._error_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        for form_field in fields:
            layout.addWidget(self._build_field(form_field))

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("formDialogButtonBox")
        self._submit_button = button_box.addButton(
            submit_label, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = button_box.addButton(
            cancel_label, QDialogButtonBox.ButtonRole.RejectRole
        )
        self._submit_button.setObjectName("formDialogSubmit")
        self._cancel_button.setObjectName("formDialogCancel")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._revalidate_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def values(self) -> dict[str, object]:
        """Return the collected field values as a dictionary."""
        result: dict[str, object] = {}
        for form_field in self._fields:
            if form_field.kind is FormFieldKind.TEXT:
                result[form_field.identifier] = self._text_inputs[form_field.identifier].text()
            elif form_field.kind is FormFieldKind.MULTILINE:
                result[form_field.identifier] = self._multiline_inputs[form_field.identifier].toPlainText()
            elif form_field.kind is FormFieldKind.CHECKBOX:
                result[form_field.identifier] = self._checkboxes[form_field.identifier].isChecked()
            elif form_field.kind is FormFieldKind.SELECT:
                combo = self._selects[form_field.identifier]
                data = combo.currentData()
                result[form_field.identifier] = str(data) if data is not None else ""
        return result

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_field(self, form_field: FormField) -> QWidget:
        container = QWidget(self)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        label = QLabel(form_field.label, container)
        label.setObjectName("formDialogFieldLabel")
        container_layout.addWidget(label)

        if form_field.kind is FormFieldKind.TEXT:
            input_widget = QLineEdit(form_field.initial, container)
            input_widget.setObjectName(f"formDialogInput_{form_field.identifier}")
            input_widget.setPlaceholderText(form_field.placeholder)
            input_widget.textChanged.connect(
                lambda _text, fid=form_field.identifier: self._revalidate_field(fid)
            )
            container_layout.addWidget(input_widget)
            self._text_inputs[form_field.identifier] = input_widget

        elif form_field.kind is FormFieldKind.MULTILINE:
            input_widget = QPlainTextEdit(form_field.initial, container)
            input_widget.setObjectName(f"formDialogMultiline_{form_field.identifier}")
            input_widget.setPlaceholderText(form_field.placeholder)
            input_widget.setMinimumHeight(100)
            input_widget.textChanged.connect(
                lambda fid=form_field.identifier: self._revalidate_field(fid)
            )
            container_layout.addWidget(input_widget)
            self._multiline_inputs[form_field.identifier] = input_widget

        elif form_field.kind is FormFieldKind.CHECKBOX:
            checkbox = QCheckBox(form_field.label, container)
            checkbox.setObjectName(f"formDialogCheckbox_{form_field.identifier}")
            checkbox.setChecked(form_field.initial.lower() in {"1", "true", "yes", "on"})
            checkbox.toggled.connect(
                lambda _checked, fid=form_field.identifier: self._revalidate_field(fid)
            )
            container_layout.addWidget(checkbox)
            self._checkboxes[form_field.identifier] = checkbox
            # The label is redundant for a checkbox; hide the standalone label.
            label.setVisible(False)

        elif form_field.kind is FormFieldKind.SELECT:
            combo = QComboBox(container)
            combo.setObjectName(f"formDialogSelect_{form_field.identifier}")
            for identifier, display in form_field.options:
                combo.addItem(display, identifier)
            if form_field.initial:
                for index in range(combo.count()):
                    if combo.itemData(index) == form_field.initial:
                        combo.setCurrentIndex(index)
                        break
            combo.currentIndexChanged.connect(
                lambda _index, fid=form_field.identifier: self._revalidate_field(fid)
            )
            container_layout.addWidget(combo)
            self._selects[form_field.identifier] = combo

        if form_field.help_text:
            help_label = QLabel(form_field.help_text, container)
            help_label.setObjectName("formDialogFieldHelp")
            help_label.setWordWrap(True)
            container_layout.addWidget(help_label)

        error_label = QLabel("", container)
        error_label.setObjectName(f"formDialogFieldError_{form_field.identifier}")
        error_label.setWordWrap(True)
        error_label.setVisible(False)
        container_layout.addWidget(error_label)
        self._error_labels[form_field.identifier] = error_label

        return container

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _field_value(self, form_field: FormField) -> str:
        if form_field.kind is FormFieldKind.TEXT:
            return self._text_inputs[form_field.identifier].text()
        if form_field.kind is FormFieldKind.MULTILINE:
            return self._multiline_inputs[form_field.identifier].toPlainText()
        if form_field.kind is FormFieldKind.CHECKBOX:
            return "true" if self._checkboxes[form_field.identifier].isChecked() else ""
        if form_field.kind is FormFieldKind.SELECT:
            combo = self._selects[form_field.identifier]
            data = combo.currentData()
            return str(data) if data is not None else ""
        return ""

    def _revalidate_field(self, identifier: str) -> None:
        form_field = next((f for f in self._fields if f.identifier == identifier), None)
        if form_field is None:
            return
        error_label = self._error_labels[identifier]
        if form_field.validator is None:
            error_label.setText("")
            error_label.setVisible(False)
            self._refresh_submit_state()
            return
        problem = form_field.validator(self._field_value(form_field))
        if problem is None:
            error_label.setText("")
            error_label.setVisible(False)
        else:
            error_label.setText(problem)
            error_label.setVisible(True)
        self._refresh_submit_state()

    def _revalidate_all(self) -> None:
        for form_field in self._fields:
            self._revalidate_field(form_field.identifier)

    def _refresh_submit_state(self) -> None:
        any_error = any(
            label.text() and label.isVisibleTo(self)
            for label in self._error_labels.values()
        )
        self._submit_button.setEnabled(not any_error)


def collect_form(
    parent: QWidget | None,
    title: str,
    fields: tuple[FormField, ...],
    *,
    submit_label: str = "OK",
    cancel_label: str = "Cancel",
) -> dict[str, object] | None:
    """Display a modal form. Returns the collected values or None."""
    dialog = FormDialog(
        title=title,
        fields=fields,
        submit_label=submit_label,
        cancel_label=cancel_label,
        parent=parent,
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.values()
    return None