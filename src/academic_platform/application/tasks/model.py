"""Value objects for the research task service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """Lifecycle statuses for a research task."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"

    @property
    def display_name(self) -> str:
        return {
            TaskStatus.OPEN: "Open",
            TaskStatus.IN_PROGRESS: "In progress",
            TaskStatus.BLOCKED: "Blocked",
            TaskStatus.DONE: "Done",
            TaskStatus.CANCELLED: "Cancelled",
        }[self]

    @property
    def is_terminal(self) -> bool:
        return self in {TaskStatus.DONE, TaskStatus.CANCELLED}

    @property
    def is_active(self) -> bool:
        """Return True when the task contributes to active work."""
        return self in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}


class TaskPriority(str, Enum):
    """Priority levels for a research task."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def display_name(self) -> str:
        return {
            TaskPriority.LOW: "Low",
            TaskPriority.NORMAL: "Normal",
            TaskPriority.HIGH: "High",
            TaskPriority.CRITICAL: "Critical",
        }[self]

    @property
    def rank(self) -> int:
        return {
            TaskPriority.LOW: 0,
            TaskPriority.NORMAL: 1,
            TaskPriority.HIGH: 2,
            TaskPriority.CRITICAL: 3,
        }[self]


@dataclass(frozen=True, slots=True)
class TaskView:
    """A task as seen by the presentation layer."""

    identifier: int
    project_key: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    is_milestone: bool
    position: int
    due_at: str | None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    notes: str = ""

    @property
    def display_label(self) -> str:
        marker = "★ " if self.is_milestone else ""
        prefix = {
            TaskStatus.OPEN: "○ ",
            TaskStatus.IN_PROGRESS: "◐ ",
            TaskStatus.BLOCKED: "✖ ",
            TaskStatus.DONE: "✓ ",
            TaskStatus.CANCELLED: "— ",
        }[self.status]
        return f"{marker}{prefix}{self.title}"

    @property
    def is_complete(self) -> bool:
        return self.status is TaskStatus.DONE


@dataclass(frozen=True, slots=True)
class MilestoneView:
    """A milestone as seen by the presentation layer.

    A milestone is a task whose ``is_milestone`` flag is True. The view
    exposes the subset of fields relevant to a milestone together with
    the current status.
    """

    identifier: int
    project_key: str
    title: str
    status: TaskStatus
    due_at: str | None
    completed_at: str | None

    @property
    def display_label(self) -> str:
        return f"★ {self.title}"

    @property
    def is_complete(self) -> bool:
        return self.status is TaskStatus.DONE


@dataclass(frozen=True, slots=True)
class TaskProgressSummary:
    """Aggregated task progress for a project."""

    project_key: str
    total: int = 0
    open: int = 0
    in_progress: int = 0
    blocked: int = 0
    done: int = 0
    cancelled: int = 0
    milestones_total: int = 0
    milestones_done: int = 0
    overdue: int = 0
    tasks: tuple[TaskView, ...] = field(default_factory=tuple)
    milestones: tuple[MilestoneView, ...] = field(default_factory=tuple)

    @property
    def completion_ratio(self) -> float:
        if self.total <= 0:
            return 0.0
        return max(0.0, min(1.0, self.done / self.total))

    @property
    def milestone_ratio(self) -> float:
        if self.milestones_total <= 0:
            return 0.0
        return max(0.0, min(1.0, self.milestones_done / self.milestones_total))

    @property
    def active_count(self) -> int:
        return self.open + self.in_progress + self.blocked