"""Tests for the handoff store."""

from __future__ import annotations

import pytest

from academic_platform.application.assistant_handoff.model import (
    AssistantHandoff,
)
from academic_platform.application.assistant_handoff.store import (
    HandoffStore,
    default_handoff_store,
)


def test_rejects_zero_max_entries() -> None:
    with pytest.raises(ValueError):
        HandoffStore(max_entries=0)


def test_put_and_get() -> None:
    store = HandoffStore()
    handoff = AssistantHandoff(document_key="doc-1", title="T")
    store.put(handoff)
    assert store.get("doc-1") is handoff
    assert store.get("missing") is None


def test_latest_returns_most_recent() -> None:
    store = HandoffStore()
    store.put(AssistantHandoff(document_key="doc-1", title="First"))
    store.put(AssistantHandoff(document_key="doc-2", title="Second"))
    latest = store.latest()
    assert latest is not None
    assert latest.document_key == "doc-2"


def test_replace_updates_order() -> None:
    store = HandoffStore()
    store.put(AssistantHandoff(document_key="doc-1", title="Old"))
    store.put(AssistantHandoff(document_key="doc-2", title="Other"))
    store.put(AssistantHandoff(document_key="doc-1", title="New"))
    latest = store.latest()
    assert latest is not None
    assert latest.title == "New"


def test_bounded_store_evicts_oldest() -> None:
    store = HandoffStore(max_entries=2)
    store.put(AssistantHandoff(document_key="a", title="A"))
    store.put(AssistantHandoff(document_key="b", title="B"))
    store.put(AssistantHandoff(document_key="c", title="C"))
    assert store.get("a") is None
    assert store.get("b") is not None
    assert store.get("c") is not None


def test_clear() -> None:
    store = HandoffStore()
    store.put(AssistantHandoff(document_key="doc-1", title="T"))
    store.clear()
    assert len(store) == 0
    assert store.latest() is None


def test_default_store_is_singleton() -> None:
    assert default_handoff_store() is default_handoff_store()