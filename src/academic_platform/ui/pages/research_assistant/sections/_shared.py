"""Shared helpers for the research assistant sections.

The helpers here provide small, reusable form widgets that multiple
sections rely on. The helpers are private to the sections package and
are not imported by any other module.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


def make_multiline_field(
    parent: QWidget,
    label: str,
    *,
    placeholder: str = "",
    minimum_height: int = 120,
) -> QPlainTextEdit:
    """Return a labelled multiline field appended to the parent layout."""
    layout = parent.layout()
    if not isinstance(layout, QVBoxLayout):
        raise RuntimeError("Parent widget must have a QVBoxLayout")
    field_label = QLabel(label, parent)
    field_label.setObjectName(f"fieldLabel_{label}")
    layout.addWidget(field_label)
    editor = QPlainTextEdit(parent)
    editor.setObjectName(f"field_{label}")
    editor.setPlaceholderText(placeholder)
    editor.setMinimumHeight(minimum_height)
    layout.addWidget(editor)
    return editor


def make_line_field(
    parent: QWidget,
    label: str,
    *,
    placeholder: str = "",
) -> QLineEdit:
    """Return a labelled single-line field appended to the parent layout."""
    layout = parent.layout()
    if not isinstance(layout, QVBoxLayout):
        raise RuntimeError("Parent widget must have a QVBoxLayout")
    field_label = QLabel(label, parent)
    field_label.setObjectName(f"fieldLabel_{label}")
    layout.addWidget(field_label)
    editor = QLineEdit(parent)
    editor.setObjectName(f"field_{label}")
    editor.setPlaceholderText(placeholder)
    layout.addWidget(editor)
    return editor


def make_form(parent: QWidget) -> QFormLayout:
    """Return a QFormLayout added to the parent's layout."""
    layout = parent.layout()
    if not isinstance(layout, QVBoxLayout):
        raise RuntimeError("Parent widget must have a QVBoxLayout")
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(8)
    container = QWidget(parent)
    container.setLayout(form)
    layout.addWidget(container)
    return form