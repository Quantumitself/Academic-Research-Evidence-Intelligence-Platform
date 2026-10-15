"""Notification value objects."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class NotificationSeverity(str, Enum):
    """Severity of a notification."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


def _new_identifier() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Notification:
    """Immutable description of a single notification.

    Attributes
    ----------
    identifier:
        Stable identifier. Used to correlate a notification with the
        dismiss or activate callbacks.
    title:
        Short headline.
    message:
        Optional body. May be empty.
    severity:
        Visual and semantic severity.
    timeout_ms:
        Automatic dismissal delay in milliseconds. Zero disables automatic
        dismissal.
    created_at:
        Timestamp of creation. Used for ordering and diagnostics.
    """

    identifier: str = field(default_factory=_new_identifier)
    title: str = ""
    message: str = ""
    severity: NotificationSeverity = NotificationSeverity.INFO
    timeout_ms: int = 6000
    created_at: datetime = field(default_factory=_now)