"""Research tasks and milestones.

This subpackage owns the workflow semantics of research tasks:

- ``TaskStatus`` — the closed set of task statuses.
- ``TaskPriority`` — the closed set of task priorities.
- ``TaskView`` — an immutable summary of a task.
- ``MilestoneView`` — an immutable summary of a milestone.
- ``TaskProgressSummary`` — the aggregated progress of a project.
- ``TaskService`` — the application service.
- ``TaskError`` and subclasses — typed errors.

The service never imports Qt. It reads and writes through the research
task repository and writes audit events through the audit repository.
"""

from academic_platform.application.tasks.errors import (
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
)
from academic_platform.application.tasks.model import (
    MilestoneView,
    TaskPriority,
    TaskProgressSummary,
    TaskStatus,
    TaskView,
)
from academic_platform.application.tasks.service import TaskService

__all__ = [
    "MilestoneView",
    "TaskError",
    "TaskNotFoundError",
    "TaskPriority",
    "TaskProgressSummary",
    "TaskService",
    "TaskStatus",
    "TaskValidationError",
    "TaskView",
]