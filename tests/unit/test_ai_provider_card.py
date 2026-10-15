"""Tests for the AIProviderCard component."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton  # noqa: E402

from academic_platform.ui.components.ai_provider_card import (  # noqa: E402
    AIProviderCard,
    AIProviderSummary,
    ProviderKind,
    ProviderStatus,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _summary() -> AIProviderSummary:
    return AIProviderSummary(
        identifier="prov1",
        name="Local Llama",
        kind=ProviderKind.LOCAL_GGUF,
        endpoint="http://127.0.0.1:8080",
        model_count=2,
        enabled=True,
        status=ProviderStatus.OK,
    )


def test_enabled_toggled_signal(app: QApplication) -> None:
    card = AIProviderCard(_summary())
    received: list[tuple[str, bool]] = []
    card.enabled_toggled.connect(lambda i, e: received.append((i, e)))
    checkbox = card.findChild(QCheckBox, "aiProviderCardEnabled")
    assert checkbox is not None
    checkbox.setChecked(False)
    assert received == [("prov1", False)]


def test_set_enabled_does_not_emit(app: QApplication) -> None:
    card = AIProviderCard(_summary())
    received: list[tuple[str, bool]] = []
    card.enabled_toggled.connect(lambda i, e: received.append((i, e)))
    card.set_enabled(False)
    assert received == []


def test_actions_disabled_by_default(app: QApplication) -> None:
    card = AIProviderCard(_summary())
    for name in ("aiProviderCardTest", "aiProviderCardEdit", "aiProviderCardRemove"):
        button = card.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()


def test_test_signal_after_enable(app: QApplication) -> None:
    card = AIProviderCard(_summary())
    card.enable_test()
    received: list[str] = []
    card.test_requested.connect(received.append)
    button = card.findChild(QPushButton, "aiProviderCardTest")
    assert button is not None
    button.click()
    assert received == ["prov1"]