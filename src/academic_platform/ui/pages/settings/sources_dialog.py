"""Source management dialog.

The dialog presents the full set of configured search sources as a list
of ``SearchSourceRow`` instances. It exposes actions for adding a new
source, editing an existing one, testing connectivity, enabling or
disabling a source, and removing a user-defined source. Built-in sources
may be disabled but not removed; the dialog disables the Remove action
for them.

Design decisions
----------------
- The dialog is modal. Source management is not a background activity.
- The dialog reads sources through the application-layer
  ``SearchSourceService``. It never reads the database directly.
- Testing a source executes synchronously. For the dialog this is
  acceptable because a user-initiated test is bounded by the source's
  configured timeout and by the number of sources the user chooses to
  test. The dialog displays a busy cursor while the test runs.
- Removing a source and adding a source are guarded by the confirm and
  prompt dialogs from Phase 8. Editing a source uses the form dialog
  from Phase 8.
- The dialog emits ``sources_changed`` when a change has been persisted
  so that the parent page can refresh its view.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.search_sources.errors import (
    SourceError,
    SourceNotFoundError,
    SourceValidationError,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)
from academic_platform.application.search_sources.source_config import (
    SourceConfig,
    SourceRecord,
)
from academic_platform.ui.components.search_source_row import (
    SearchSourceRow,
    SearchSourceSummary,
    SourceType,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.form_dialog import FormField, FormFieldKind
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.notifications.service import NotificationService

_logger = logging.getLogger(__name__)


class SourcesDialog(QDialog):
    """Modal dialog for managing search sources."""

    sources_changed = Signal()

    def __init__(
        self,
        service: SearchSourceService,
        *,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._notification_service = notification_service
        self.setObjectName("sourcesDialog")
        self.setWindowTitle("Search sources")
        self.setModal(True)
        self.setMinimumSize(640, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel(
            "Enable or disable the sources the application queries. "
            "Built-in sources may be disabled but not removed.",
            self,
        )
        heading.setObjectName("sourcesDialogHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget(scroll)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self._add_button = QPushButton("Add source", self)
        self._add_button.setObjectName("sourcesDialogAdd")
        self._add_button.setAutoDefault(False)
        self._add_button.clicked.connect(self._on_add)
        actions.addWidget(self._add_button)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("sourcesDialogRefresh")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self._refresh)
        actions.addWidget(self._refresh_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close, self
        )
        button_box.setObjectName("sourcesDialogButtonBox")
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload the source list from the service."""
        self._refresh()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._clear_list()
        try:
            records = self._service.list_sources()
        except SourceError as exc:
            self._show_error("Unable to read sources", str(exc))
            return
        if not records:
            placeholder = QLabel("No sources configured yet.", self._list_container)
            placeholder.setObjectName("sourcesDialogPlaceholder")
            self._list_layout.addWidget(placeholder)
            return
        for record in records:
            row = self._build_row(record)
            self._list_layout.addWidget(row)
        self._list_layout.addStretch(1)

    def _build_row(self, record: SourceRecord) -> SearchSourceRow:
        config = record.config
        last_test_ok: bool | None = None
        if config.last_tested_at:
            last_test_ok = not bool(config.last_error)
        summary = SearchSourceSummary(
            identifier=config.key,
            name=config.display_name,
            source_type=(
                SourceType.BUILT_IN
                if config.is_builtin
                else SourceType.USER_DEFINED
            ),
            enabled=config.enabled,
            last_test_ok=last_test_ok,
            last_error=config.last_error or "",
            supports_filters=tuple(sorted(_supported_filter_labels(config))),
        )
        row = SearchSourceRow(summary, parent=self._list_container)
        row.enable_test()
        row.test_requested.connect(self._on_test)
        row.enable_edit()
        row.edit_requested.connect(self._on_edit)
        if not config.is_builtin:
            row.enable_remove()
            row.remove_requested.connect(self._on_remove)
        row.enabled_toggled.connect(self._on_enabled_toggled)
        return row

    def _on_test(self, key: str) -> None:
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report = self._service.test_connection(key)
        except SourceNotFoundError:
            self._show_error(
                "Source not found",
                f"No source with key {key!r} is configured.",
            )
            return
        except SourceError as exc:
            self._show_error("Test failed", str(exc))
            return
        finally:
            QGuiApplication.restoreOverrideCursor()

        if report.status.value == "ok":
            self._notify("Connection succeeded", f"{key}: reachable")
        else:
            self._show_error(
                "Connection failed",
                f"{key}: {report.message or 'no further detail'}",
            )
        self._refresh()

    def _on_add(self) -> None:
        fields = _source_form_fields()
        values = DialogFactory.form(
            self,
            "Add search source",
            fields,
            submit_label="Add",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            config = _config_from_form_values(values)
        except ValueError as exc:
            self._show_error("Invalid source", str(exc))
            return
        try:
            self._service.create(config)
        except SourceValidationError as exc:
            self._show_error("Source rejected", "; ".join(exc.issues))
            return
        except SourceError as exc:
            self._show_error("Unable to add source", str(exc))
            return
        self.sources_changed.emit()
        self._notify("Source added", config.display_name)
        self._refresh()

    def _on_edit(self, key: str) -> None:
        try:
            record = self._service.get_by_key(key)
        except SourceNotFoundError:
            self._show_error(
                "Source not found",
                f"No source with key {key!r} is configured.",
            )
            return
        fields = _edit_form_fields(record.config)
        values = DialogFactory.form(
            self,
            f"Edit source: {record.config.display_name}",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            changes = _changes_from_form_values(values)
        except ValueError as exc:
            self._show_error("Invalid changes", str(exc))
            return
        try:
            self._service.update(key, changes)
        except SourceValidationError as exc:
            self._show_error("Source rejected", "; ".join(exc.issues))
            return
        except SourceError as exc:
            self._show_error("Unable to update source", str(exc))
            return
        self.sources_changed.emit()
        self._notify("Source updated", record.config.display_name)
        self._refresh()

    def _on_remove(self, key: str) -> None:
        try:
            record = self._service.get_by_key(key)
        except SourceNotFoundError:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove source",
            f"Remove the source {record.config.display_name!r}? "
            "This action cannot be undone.",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result.value != "confirmed":
            return
        try:
            self._service.remove(key)
        except SourceValidationError as exc:
            self._show_error("Source not removed", "; ".join(exc.issues))
            return
        except SourceError as exc:
            self._show_error("Unable to remove source", str(exc))
            return
        self.sources_changed.emit()
        self._notify("Source removed", record.config.display_name)
        self._refresh()

    def _on_enabled_toggled(self, key: str, enabled: bool) -> None:
        try:
            self._service.set_enabled(key, enabled)
        except SourceNotFoundError:
            return
        except SourceError as exc:
            self._show_error("Unable to change state", str(exc))
            self._refresh()
            return
        self.sources_changed.emit()
        self._refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _clear_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(
            self,
            title,
            message,
            kind=MessageKind.ERROR,
        )

    def _notify(self, title: str, message: str) -> None:
        if self._notification_service is None:
            return
        self._notification_service.success(title, message)


# ----------------------------------------------------------------------
# Form helpers
# ----------------------------------------------------------------------
def _supported_filter_labels(config: SourceConfig) -> tuple[str, ...]:
    capabilities = config.capabilities or {}
    labels: list[str] = []
    for key, label in (
        ("pagination", "pagination"),
        ("cursor_pagination", "cursor pagination"),
        ("abstract_in_results", "abstracts"),
        ("citation_counts", "citation counts"),
        ("open_access_flag", "open access"),
    ):
        if capabilities.get(key):
            labels.append(label)
    return tuple(labels)


def _source_form_fields() -> tuple[FormField, ...]:
    return (
        FormField(
            identifier="key",
            label="Key",
            kind=FormFieldKind.TEXT,
            placeholder="lowercase-with-hyphens",
            validator=_validate_key,
        ),
        FormField(
            identifier="provider_key",
            label="Provider",
            kind=FormFieldKind.TEXT,
            placeholder="provider identifier registered with the application",
            validator=_validate_required("provider_key"),
        ),
        FormField(
            identifier="display_name",
            label="Display name",
            kind=FormFieldKind.TEXT,
            validator=_validate_required("display_name"),
        ),
        FormField(
            identifier="base_url",
            label="Base URL",
            kind=FormFieldKind.TEXT,
            placeholder="https://api.example.invalid",
            validator=_validate_required("base_url"),
        ),
        FormField(
            identifier="endpoint",
            label="Endpoint",
            kind=FormFieldKind.TEXT,
            placeholder="search",
        ),
        FormField(
            identifier="timeout_seconds",
            label="Timeout (seconds)",
            kind=FormFieldKind.TEXT,
            initial="30",
            validator=_validate_integer_range("timeout_seconds", 1, 180),
        ),
        FormField(
            identifier="result_limit",
            label="Results per request",
            kind=FormFieldKind.TEXT,
            initial="50",
            validator=_validate_integer_range("result_limit", 1, 500),
        ),
    )


def _edit_form_fields(config: SourceConfig) -> tuple[FormField, ...]:
    return (
        FormField(
            identifier="display_name",
            label="Display name",
            kind=FormFieldKind.TEXT,
            initial=config.display_name,
            validator=_validate_required("display_name"),
        ),
        FormField(
            identifier="base_url",
            label="Base URL",
            kind=FormFieldKind.TEXT,
            initial=config.base_url,
            validator=_validate_required("base_url"),
        ),
        FormField(
            identifier="endpoint",
            label="Endpoint",
            kind=FormFieldKind.TEXT,
            initial=config.endpoint,
        ),
        FormField(
            identifier="timeout_seconds",
            label="Timeout (seconds)",
            kind=FormFieldKind.TEXT,
            initial=str(config.timeout_seconds),
            validator=_validate_integer_range("timeout_seconds", 1, 180),
        ),
        FormField(
            identifier="result_limit",
            label="Results per request",
            kind=FormFieldKind.TEXT,
            initial=str(config.result_limit),
            validator=_validate_integer_range("result_limit", 1, 500),
        ),
    )


def _config_from_form_values(values: dict) -> SourceConfig:
    key = str(values.get("key") or "").strip()
    provider_key = str(values.get("provider_key") or "").strip()
    display_name = str(values.get("display_name") or "").strip()
    base_url = str(values.get("base_url") or "").strip()
    endpoint = str(values.get("endpoint") or "").strip()
    timeout_seconds = int(values.get("timeout_seconds") or 30)
    result_limit = int(values.get("result_limit") or 50)
    return SourceConfig(
        key=key,
        provider_key=provider_key,
        display_name=display_name,
        source_type="user_defined",
        base_url=base_url,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        result_limit=result_limit,
    )


def _changes_from_form_values(values: dict) -> dict:
    changes: dict = {}
    for field in ("display_name", "base_url", "endpoint"):
        value = values.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            changes[field] = text
    for field in ("timeout_seconds", "result_limit"):
        value = values.get(field)
        if value is None:
            continue
        try:
            changes[field] = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer") from exc
    return changes


def _validate_key(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return "Key must not be empty"
    if not cleaned[0].isalnum():
        return "Key must start with a letter or digit"
    for character in cleaned:
        if not (character.isalnum() or character in "-_"):
            return "Key may contain letters, digits, hyphens, and underscores"
    if cleaned != cleaned.lower():
        return "Key must be lowercase"
    return None


def _validate_required(field: str) -> object:
    def _validator(value: str) -> str | None:
        if not value.strip():
            return f"{field.replace('_', ' ').capitalize()} must not be empty"
        return None

    return _validator


def _validate_integer_range(field: str, minimum: int, maximum: int) -> object:
    def _validator(value: str) -> str | None:
        text = value.strip()
        if not text:
            return f"{field.replace('_', ' ').capitalize()} must not be empty"
        try:
            parsed = int(text)
        except ValueError:
            return f"{field.replace('_', ' ').capitalize()} must be an integer"
        if parsed < minimum or parsed > maximum:
            return (
                f"{field.replace('_', ' ').capitalize()} must be between "
                f"{minimum} and {maximum}"
            )
        return None

    return _validator