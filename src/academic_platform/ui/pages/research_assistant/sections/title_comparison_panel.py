"""Title comparison panel.

The panel presents the title candidates as a list of cards. Each card
shows the candidate's title, pattern, alignment, strengths, problems,
and assumptions. The panel exposes selection actions (accept, reject,
archive, restore, edit title, use as working title) that write through
the title builder service.

Design decisions
----------------
- The panel is a self-contained widget. It reads through the title
  builder service and emits ``working_title_selected`` when the user
  requests to use a candidate as the working title. The section that
  hosts the panel wires the signal to its working-title field.
- The list is rendered as a ``QListWidget`` whose items carry the
  candidate as ``UserRole`` data. Each item's widget is a custom card
  that renders the candidate's fields.
- The panel refreshes whenever the section activates or the user
  performs an action. It never recomputes the candidate's rationale;
  the service is the single source of truth.
- Editing a candidate's title uses the standard prompt dialog.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.title_builder.errors import (
    TitleBuilderError,
    TitleBuilderNotFoundError,
    TitleBuilderValidationError,
)
from academic_platform.application.title_builder.model import (
    TitleCandidate,
    TitleState,
)
from academic_platform.application.title_builder.service import (
    TitleBuilderService,
)
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind

_logger = logging.getLogger(__name__)


class _TitleCandidateCard(QFrame):
    """Card rendering a single title candidate. Not part of the public API."""

    def __init__(self, candidate: TitleCandidate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleCandidateCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setProperty("state", candidate.state.value)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        title = QLabel(candidate.title or "(untitled)", self)
        title.setObjectName("titleCandidateCardTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)

        state = QLabel(candidate.state.display_name, self)
        state.setObjectName("titleCandidateCardState")
        state.setProperty("state", candidate.state.value)
        header.addWidget(state, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        meta = QLabel(
            f"Pattern: {candidate.pattern.display_name} · "
            f"{candidate.alignment.summary}",
            self,
        )
        meta.setObjectName("titleCandidateCardMeta")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        rationale = QLabel(candidate.rationale or "", self)
        rationale.setObjectName("titleCandidateCardRationale")
        rationale.setWordWrap(True)
        layout.addWidget(rationale)

        for label, value in (
            ("Strengths", candidate.strengths),
            ("Problems", candidate.problems),
            ("Assumptions", candidate.assumptions),
        ):
            if not value:
                continue
            block = QLabel(f"{label}: {value}", self)
            block.setObjectName(f"titleCandidateCard{label}")
            block.setWordWrap(True)
            layout.addWidget(block)


class TitleComparisonPanel(QWidget):
    """Side-by-side comparison workspace for title candidates."""

    #: Emitted when the user requests to use a candidate as the working
    #: title. Carries the candidate's title.
    working_title_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleComparisonPanel")
        self._service: TitleBuilderService | None = None
        self._project_key: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        heading = QLabel("Candidate titles", self)
        heading.setObjectName("titleComparisonHeading")
        header.addWidget(heading, 1)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("titleComparisonRefresh")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh)
        header.addWidget(self._refresh_button)

        layout.addLayout(header)

        self._list = QListWidget(self)
        self._list.setObjectName("titleComparisonList")
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._accept_button = QPushButton("Accept", self)
        self._accept_button.setObjectName("titleComparisonAccept")
        self._accept_button.setAutoDefault(False)
        self._accept_button.setEnabled(False)
        self._accept_button.clicked.connect(self._on_accept)
        actions.addWidget(self._accept_button)

        self._reject_button = QPushButton("Reject", self)
        self._reject_button.setObjectName("titleComparisonReject")
        self._reject_button.setAutoDefault(False)
        self._reject_button.setEnabled(False)
        self._reject_button.clicked.connect(self._on_reject)
        actions.addWidget(self._reject_button)

        self._archive_button = QPushButton("Archive", self)
        self._archive_button.setObjectName("titleComparisonArchive")
        self._archive_button.setAutoDefault(False)
        self._archive_button.setEnabled(False)
        self._archive_button.clicked.connect(self._on_archive)
        actions.addWidget(self._archive_button)

        self._restore_button = QPushButton("Restore", self)
        self._restore_button.setObjectName("titleComparisonRestore")
        self._restore_button.setAutoDefault(False)
        self._restore_button.setEnabled(False)
        self._restore_button.clicked.connect(self._on_restore)
        actions.addWidget(self._restore_button)

        layout.addLayout(actions)

        secondary = QHBoxLayout()
        secondary.setContentsMargins(0, 0, 0, 0)
        secondary.setSpacing(6)

        self._edit_button = QPushButton("Edit title…", self)
        self._edit_button.setObjectName("titleComparisonEdit")
        self._edit_button.setAutoDefault(False)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._on_edit)
        secondary.addWidget(self._edit_button)

        self._use_button = QPushButton("Use as working title", self)
        self._use_button.setObjectName("titleComparisonUse")
        self._use_button.setAutoDefault(False)
        self._use_button.setEnabled(False)
        self._use_button.clicked.connect(self._on_use)
        secondary.addWidget(self._use_button)

        secondary.addStretch(1)
        layout.addLayout(secondary)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(
        self,
        service: TitleBuilderService,
        project_key: str,
    ) -> None:
        """Attach the title builder service and the target project."""
        self._service = service
        self._project_key = project_key
        self.refresh()

    def set_project(self, project_key: str) -> None:
        """Change the project whose candidates are shown."""
        self._project_key = project_key
        self.refresh()

    def refresh(self) -> None:
        """Reload the candidates from the service."""
        self._list.clear()
        self._update_actions(None)
        if self._service is None or not self._project_key:
            return
        try:
            candidates = self._service.comparison_report(self._project_key)
        except TitleBuilderError as exc:
            _logger.warning("Unable to load title candidates: %s", exc)
            return
        for candidate in candidates:
            item = QListWidgetItem(self._list)
            item.setData(Qt.ItemDataRole.UserRole, candidate)
            card = _TitleCandidateCard(candidate, self._list)
            item.setSizeHint(card.sizeHint())
            self._list.setItemWidget(item, card)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        candidate = self._selected_candidate()
        self._update_actions(candidate)

    def _on_accept(self) -> None:
        self._apply_state(TitleState.ACCEPTED)

    def _on_reject(self) -> None:
        self._apply_state(TitleState.REJECTED)

    def _on_archive(self) -> None:
        self._apply_state(TitleState.ARCHIVED)

    def _on_restore(self) -> None:
        self._apply_state(TitleState.PROPOSED)

    def _on_edit(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self._service is None or not self._project_key:
            return
        new_title = DialogFactory.prompt(
            self,
            "Edit title",
            "Title",
            initial=candidate.title,
            validator=_nonempty_validator("Title"),
        )
        if new_title is None:
            return
        try:
            self._service.update_title(
                self._project_key,
                _row_id(candidate),
                new_title.strip(),
            )
        except TitleBuilderValidationError as exc:
            self._show_error("Invalid title", "; ".join(exc.issues))
            return
        except TitleBuilderNotFoundError as exc:
            self._show_error("Candidate not found", str(exc))
            return
        except TitleBuilderError as exc:
            self._show_error("Unable to update the title", str(exc))
            return
        self.refresh()

    def _on_use(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        self.working_title_selected.emit(candidate.title)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _selected_candidate(self) -> TitleCandidate | None:
        item = self._list.currentItem()
        if item is None:
            return None
        candidate = item.data(Qt.ItemDataRole.UserRole)
        return candidate if isinstance(candidate, TitleCandidate) else None

    def _apply_state(self, state: TitleState) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self._service is None or not self._project_key:
            return
        if state is not TitleState.PROPOSED and candidate.state is state:
            return
        if state is TitleState.PROPOSED and candidate.state is TitleState.PROPOSED:
            return
        try:
            self._service.set_state(
                self._project_key, _row_id(candidate), state
            )
        except TitleBuilderNotFoundError as exc:
            self._show_error("Candidate not found", str(exc))
            return
        except TitleBuilderError as exc:
            self._show_error("Unable to update the candidate", str(exc))
            return
        self.refresh()

    def _update_actions(self, candidate: TitleCandidate | None) -> None:
        has_selection = candidate is not None
        state = candidate.state if candidate is not None else None
        self._accept_button.setEnabled(
            has_selection and state is not TitleState.ACCEPTED
        )
        self._reject_button.setEnabled(
            has_selection and state is not TitleState.REJECTED
        )
        self._archive_button.setEnabled(
            has_selection and state is not TitleState.ARCHIVED
        )
        self._restore_button.setEnabled(
            has_selection and state is not TitleState.PROPOSED
        )
        self._edit_button.setEnabled(has_selection)
        self._use_button.setEnabled(has_selection)

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)


def _row_id(candidate: TitleCandidate) -> int:
    identifier = candidate.identifier
    if identifier.startswith("row."):
        try:
            return int(identifier.split(".", 1)[1])
        except (ValueError, IndexError):
            return 0
    return 0


def _nonempty_validator(field: str):
    def _validator(value: str) -> str | None:
        return None if value.strip() else f"{field} must not be empty"

    return _validator