"""AI provider configuration card.

Displays a provider's name, kind, endpoint summary, model count, and
connection status. Emits typed signals for testing, editing, toggling
enabled state, and removal.

Design decisions
----------------
- The card never stores credentials. It only carries a provider identifier
  and a display summary. Credential management belongs to the settings
  service.
- The enable toggle is a checkbox whose state is owned by the caller. The
  card emits ``enabled_toggled(identifier, enabled)``; the caller applies
  the change and calls ``set_enabled`` to reflect the outcome. This avoids
  the card drifting out of sync with persisted state.
- The connection status is a badge whose tone encodes the last test result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.stat_badge import StatBadge, StatBadgeTone


class ProviderKind(str, Enum):
    """The kind of AI provider configured."""

    LOCAL_GGUF = "local_gguf"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    OTHER = "other"


class ProviderStatus(str, Enum):
    """The outcome of the last connection test."""

    UNKNOWN = "unknown"
    OK = "ok"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AIProviderSummary:
    """Presentation payload for an AI provider card."""

    identifier: str
    name: str
    kind: ProviderKind
    endpoint: str = ""
    model_count: int = 0
    enabled: bool = True
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_error: str = ""


_KIND_LABELS: dict[ProviderKind, str] = {
    ProviderKind.LOCAL_GGUF: "Local GGUF",
    ProviderKind.OPENAI_COMPATIBLE: "OpenAI-compatible",
    ProviderKind.ANTHROPIC: "Anthropic",
    ProviderKind.OTHER: "Other",
}

_STATUS_TONES: dict[ProviderStatus, StatBadgeTone] = {
    ProviderStatus.UNKNOWN: StatBadgeTone.NEUTRAL,
    ProviderStatus.OK: StatBadgeTone.POSITIVE,
    ProviderStatus.FAILED: StatBadgeTone.DANGER,
}

_STATUS_LABELS: dict[ProviderStatus, str] = {
    ProviderStatus.UNKNOWN: "Not tested",
    ProviderStatus.OK: "Connected",
    ProviderStatus.FAILED: "Failed",
}


class AIProviderCard(QFrame):
    """AI provider configuration card."""

    test_requested = Signal(str)
    edit_requested = Signal(str)
    remove_requested = Signal(str)
    enabled_toggled = Signal(str, bool)

    def __init__(
        self,
        provider: AIProviderSummary,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("aiProviderCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._provider = provider

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._enabled_checkbox = QCheckBox(self)
        self._enabled_checkbox.setObjectName("aiProviderCardEnabled")
        self._enabled_checkbox.setChecked(provider.enabled)
        self._enabled_checkbox.setToolTip(
            "Enable or disable this provider. Disabled providers are not used "
            "for any task."
        )
        self._enabled_checkbox.toggled.connect(
            lambda checked: self.enabled_toggled.emit(provider.identifier, checked)
        )
        header.addWidget(self._enabled_checkbox)

        name = QLabel(provider.name, self)
        name.setObjectName("aiProviderCardName")
        name.setWordWrap(True)
        header.addWidget(name, 1)

        header.addWidget(
            StatBadge("Kind", _KIND_LABELS[provider.kind], parent=self),
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        header.addWidget(
            StatBadge(
                "Status",
                _STATUS_LABELS[provider.status],
                tone=_STATUS_TONES[provider.status],
                parent=self,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addLayout(header)

        details: list[str] = []
        if provider.endpoint:
            details.append(f"Endpoint: {provider.endpoint}")
        if provider.model_count:
            details.append(f"Models: {provider.model_count}")
        if provider.last_error:
            details.append(f"Last error: {provider.last_error}")
        if details:
            detail_label = QLabel("\n".join(details), self)
            detail_label.setObjectName("aiProviderCardDetails")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._test_button = QPushButton("Test connection", self)
        self._test_button.setObjectName("aiProviderCardTest")
        self._test_button.setEnabled(False)
        self._test_button.clicked.connect(
            lambda: self.test_requested.emit(provider.identifier)
        )
        actions.addWidget(self._test_button)

        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("aiProviderCardEdit")
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(
            lambda: self.edit_requested.emit(provider.identifier)
        )
        actions.addWidget(self._edit_button)

        self._remove_button = QPushButton("Remove", self)
        self._remove_button.setObjectName("aiProviderCardRemove")
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(
            lambda: self.remove_requested.emit(provider.identifier)
        )
        actions.addWidget(self._remove_button)

        actions.addStretch(1)
        layout.addLayout(actions)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enable_test(self, enabled: bool = True) -> None:
        self._test_button.setEnabled(enabled)

    def enable_edit(self, enabled: bool = True) -> None:
        self._edit_button.setEnabled(enabled)

    def enable_remove(self, enabled: bool = True) -> None:
        self._remove_button.setEnabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        """Reflect the persisted enabled state without re-emitting the signal."""
        self._enabled_checkbox.blockSignals(True)
        self._enabled_checkbox.setChecked(enabled)
        self._enabled_checkbox.blockSignals(False)

    @property
    def identifier(self) -> str:
        return self._provider.identifier

    @property
    def provider(self) -> AIProviderSummary:
        return self._provider