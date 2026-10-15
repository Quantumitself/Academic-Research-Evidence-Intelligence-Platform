"""Standard dialogs and confirmation prompts.

This package provides:

- ``DialogFactory`` — central constructor for every standard dialog so that
  callers do not assemble ``QMessageBox`` instances ad hoc.
- ``MessageDialog`` — informational dialog with a title, body, and optional
  details pane.
- ``ConfirmDialog`` — yes/no confirmation with a configurable default and
  an optional "do not ask again" checkbox.
- ``PromptDialog`` — single-line text prompt with validation.
- ``FormDialog`` — multi-field dialog constructed from a declarative field
  list.
- ``ProgressDialog`` — modal progress dialog with cancellation.

The dialogs are presentation-only. They never perform the action they
confirm; they return the user's decision to the caller.

Notifications live in ``academic_platform.ui.notifications``.
"""

from academic_platform.ui.dialogs.confirm_dialog import ConfirmDialog, ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.form_dialog import FormDialog, FormField, FormFieldKind
from academic_platform.ui.dialogs.message_dialog import MessageDialog, MessageKind
from academic_platform.ui.dialogs.progress_dialog import ProgressDialog
from academic_platform.ui.dialogs.prompt_dialog import PromptDialog

__all__ = [
    "ConfirmDialog",
    "ConfirmResult",
    "DialogFactory",
    "FormDialog",
    "FormField",
    "FormFieldKind",
    "MessageDialog",
    "MessageKind",
    "ProgressDialog",
    "PromptDialog",
]