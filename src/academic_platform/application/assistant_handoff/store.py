"""In-process store for handoff payloads.

The store holds the most recent handoff per document. It is a
process-local dictionary guarded by a lock; the desktop application is
single-process. Later phases that run the assistant in a separate
process will replace this store with a persistent one. The store's
interface is deliberately narrow so that replacement is straightforward.

Design decisions
----------------
- The store is not persistent. It holds state for the lifetime of the
  process so that the reader can hand off a payload and the assistant
  can retrieve it in the same session.
- The store is safe for concurrent access. The desktop application is
  single-threaded for UI work, but the store does not assume that.
- The store is bounded: it keeps at most ``max_entries`` payloads and
  evicts the oldest when the bound is exceeded.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from academic_platform.application.assistant_handoff.model import (
    AssistantHandoff,
)


class HandoffStore:
    """In-process store for the most recent handoff per document."""

    def __init__(self, max_entries: int = 32) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, AssistantHandoff] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, handoff: AssistantHandoff) -> None:
        """Store a handoff, replacing any previous one for the document."""
        with self._lock:
            self._entries[handoff.document_key] = handoff
            self._entries.move_to_end(handoff.document_key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def get(self, document_key: str) -> AssistantHandoff | None:
        """Return the most recent handoff for a document, or ``None``."""
        with self._lock:
            handoff = self._entries.get(document_key)
            if handoff is not None:
                self._entries.move_to_end(document_key)
            return handoff

    def latest(self) -> AssistantHandoff | None:
        """Return the most recently stored handoff, or ``None``."""
        with self._lock:
            if not self._entries:
                return None
            key = next(reversed(self._entries))
            return self._entries[key]

    def clear(self) -> None:
        """Remove every stored handoff."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_DEFAULT_STORE: HandoffStore | None = None


def default_handoff_store() -> HandoffStore:
    """Return the process-wide handoff store."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = HandoffStore()
    return _DEFAULT_STORE