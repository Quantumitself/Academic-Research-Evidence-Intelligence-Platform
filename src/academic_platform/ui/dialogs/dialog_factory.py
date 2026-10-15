"""Central dialog factory.

The factory provides a single entry point for every standard dialog so
that callers do not assemble widgets ad hoc. Each method either returns
the dialog for the caller to run or runs the dialog and returns the
outcome.

Design decisions
----------------
- The factory is a plain class with static methods. It holds no state.
- The factory never blocks on its own. Methods that return a dialog leave
  the decision of running the dialog to the caller. Methods prefixed with
  ``ask`` or ``show`` run the dialog and return the outcome.
- The factory is the only place that knows which message kind maps to
  which visual treatment. Callers express intent, not visuals.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from academic_platform.ui.dialogs.confirm_dialog import (
    ConfirmDialog,
    ConfirmOutcome,
    ask_confirmation,
)
from academic_platform.ui.dialogs.form_dialog import (
    FormDialog,
    FormField,
    collect_form,
)
from academic_platform.ui.dialogs.message_dialog import (
    MessageDialog,
    MessageKind,
    show_message,
)
from academic_platform.ui.dialogs.progress_dialog import ProgressDialog
from academic_platform.ui.dialogs.prompt_dialog import (
    PromptDialog,
    Validator,
    ask_text,
)


class DialogFactory:
    """Constructs standard dialogs for the application."""

    # ------------------------------------------------------------------
    # Message
    # ------------------------------------------------------------------
    @staticmethod
    def message(
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        kind: MessageKind = MessageKind.INFO,
        details: str = "",
        copyable: bool = False,
    ) -> None:
        """Display a modal message dialog."""
        show_message(
            parent,
            title,
            message,
            kind=kind,
            details=details,
            copyable=copyable,
        )

    @staticmethod
    def info(
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
    ) -> None:
        """Display an informational message."""
        show_message(parent, title, message, kind=MessageKind.INFO, details=details)

    @staticmethod
    def warning(
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
    ) -> None:
        """Display a warning message."""
        show_message(parent, title, message, kind=MessageKind.WARNING, details=details)

    @staticmethod
    def error(
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
    ) -> None:
        """Display an error message with copyable details."""
        show_message(
            parent,
            title,
            message,
            kind=MessageKind.ERROR,
            details=details,
            copyable=bool(details),
        )

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------
    @staticmethod
    def confirm(
        parent: QWidget | None,
        title: str,
        question: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        destructive: bool = False,
        details: str = "",
        offer_do_not_ask_again: bool = False,
        default_to_confirm: bool = False,
    ) -> ConfirmOutcome:
        """Display a modal confirmation and return the outcome."""
        return ask_confirmation(
            parent,
            title,
            question,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            destructive=destructive,
            details=details,
            offer_do_not_ask_again=offer_do_not_ask_again,
            default_to_confirm=default_to_confirm,
        )

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------
    @staticmethod
    def prompt(
        parent: QWidget | None,
        title: str,
        label: str,
        *,
        initial: str = "",
        placeholder: str = "",
        validator: Validator | None = None,
        trim: bool = True,
    ) -> str | None:
        """Display a modal text prompt. Returns the value or None."""
        return ask_text(
            parent,
            title,
            label,
            initial=initial,
            placeholder=placeholder,
            validator=validator,
            trim=trim,
        )

    # ------------------------------------------------------------------
    # Form
    # ------------------------------------------------------------------
    @staticmethod
    def form(
        parent: QWidget | None,
        title: str,
        fields: tuple[FormField, ...],
        *,
        submit_label: str = "OK",
        cancel_label: str = "Cancel",
    ) -> dict[str, Any] | None:
        """Display a modal form. Returns the collected values or None."""
        return collect_form(
            parent,
            title,
            fields,
            submit_label=submit_label,
            cancel_label=cancel_label,
        )

    # ------------------------------------------------------------------
    # Dialog instances
    # ------------------------------------------------------------------
    @staticmethod
    def message_dialog(
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        kind: MessageKind = MessageKind.INFO,
        details: str = "",
        copyable: bool = False,
    ) -> MessageDialog:
        """Construct (but do not run) a message dialog."""
        return MessageDialog(
            title=title,
            message=message,
            kind=kind,
            details=details,
            copyable=copyable,
            parent=parent,
        )

    @staticmethod
    def confirm_dialog(
        parent: QWidget | None,
        title: str,
        question: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        destructive: bool = False,
        details: str = "",
        offer_do_not_ask_again: bool = False,
        default_to_confirm: bool = False,
    ) -> ConfirmDialog:
        """Construct (but do not run) a confirmation dialog."""
        return ConfirmDialog(
            title=title,
            question=question,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            destructive=destructive,
            details=details,
            offer_do_not_ask_again=offer_do_not_ask_again,
            default_to_confirm=default_to_confirm,
            parent=parent,
        )

    @staticmethod
    def prompt_dialog(
        parent: QWidget | None,
        title: str,
        label: str,
        *,
        initial: str = "",
        placeholder: str = "",
        validator: Validator | None = None,
        trim: bool = True,
    ) -> PromptDialog:
        """Construct (but do not run) a text prompt dialog."""
        return PromptDialog(
            title=title,
            label=label,
            initial=initial,
            placeholder=placeholder,
            validator=validator,
            trim=trim,
            parent=parent,
        )

    @staticmethod
    def form_dialog(
        parent: QWidget | None,
        title: str,
        fields: tuple[FormField, ...],
        *,
        submit_label: str = "OK",
        cancel_label: str = "Cancel",
    ) -> FormDialog:
        """Construct (but do not run) a form dialog."""
        return FormDialog(
            title=title,
            fields=fields,
            submit_label=submit_label,
            cancel_label=cancel_label,
            parent=parent,
        )

    @staticmethod
    def progress_dialog(
        parent: QWidget | None,
        title: str,
        *,
        message: str = "",
        total: int,
        cancellable: bool = False,
    ) -> ProgressDialog:
        """Construct (but do not run) a progress dialog."""
        return ProgressDialog(
            title=title,
            message=message,
            total=total,
            cancellable=cancellable,
            parent=parent,
        )