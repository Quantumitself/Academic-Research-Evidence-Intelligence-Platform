"""Review & Export section.

The section presents a summary of the assistant's work across every
other section. It is a read-only view; it does not modify other
sections. Export is delegated to the project export service when a
project is attached; at this stage the section displays the summary
and offers a placeholder export action that reports its status through
the notification service.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)


class ReviewSection(AssistantSection):
    """Review & Export section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.REVIEW, parent=parent)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        intro = QLabel(
            "Review the state of the research design. Use the Refresh "
            "button to update the summary after changing other sections.",
            content,
        )
        intro.setObjectName("reviewIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._summary = QPlainTextEdit(content)
        self._summary.setObjectName("reviewSummary")
        self._summary.setReadOnly(True)
        self._summary.setMinimumHeight(240)
        layout.addWidget(self._summary, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._refresh_button = QPushButton("Refresh summary", content)
        self._refresh_button.setObjectName("reviewRefresh")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self._on_refresh)
        actions.addWidget(self._refresh_button)

        self._export_button = QPushButton("Export research design…", content)
        self._export_button.setObjectName("reviewExport")
        self._export_button.setAutoDefault(False)
        self._export_button.clicked.connect(self._on_export)
        actions.addWidget(self._export_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        # The summary provider is set by the page; until then the
        # section reports that the summary is not available.
        self._summary_provider = None
        self._on_refresh()

        self._install_content(content)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_summary_provider(self, provider) -> None:
        """Set the callable that produces the summary text.

        The provider is called without arguments and must return a
        string. It is invoked every time the summary is refreshed.
        """
        self._summary_provider = provider
        self._on_refresh()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_refresh(self) -> None:
        if not callable(self._summary_provider):
            self._summary.setPlainText(
                "The summary provider is not available."
            )
            return
        try:
            text = self._summary_provider()
        except Exception as exc:  # noqa: BLE001 - boundary
            self._summary.setPlainText(
                f"Unable to build the summary: {exc}"
            )
            return
        self._summary.setPlainText(text)

    def _on_export(self) -> None:
        DialogFactory.message(
            self,
            "Export research design",
            (
                "Export from the research assistant is delivered in a "
                "later phase. The research plan section currently exposes "
                "the exported fields, and the project export workflow on "
                "the Projects page already covers the plan and its related "
                "entities."
            ),
            kind=MessageKind.INFO,
        )

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def summary(self) -> str:
        text = self._summary.toPlainText().strip()
        if not text:
            return ""
        first_line = text.splitlines()[0]
        return first_line[:80]

    def reset(self) -> None:
        self._on_refresh()