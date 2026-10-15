"""Research project application service.

This subpackage owns the lifecycle of research projects:

- ``ProjectStage`` — the closed set of lifecycle stages.
- ``ProjectView`` — an immutable summary of a project.
- ``ProjectQuestionView`` — an immutable summary of a research question.
- ``ProjectTaskView`` — an immutable summary of a research task.
- ``ProjectService`` — the application service that creates, reads,
  updates, deletes, versions, and manages projects and their questions
  and tasks.
- ``ProjectError`` and subclasses — typed errors.

The service never imports Qt. It reads and writes through the research
project, research question, research task, collection, and audit
repositories.
"""

from academic_platform.application.projects.errors import (
    ProjectError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from academic_platform.application.projects.model import (
    ProjectQuestionView,
    ProjectStage,
    ProjectTaskView,
    ProjectView,
)
from academic_platform.application.projects.service import ProjectService

__all__ = [
    "ProjectError",
    "ProjectNotFoundError",
    "ProjectQuestionView",
    "ProjectService",
    "ProjectStage",
    "ProjectTaskView",
    "ProjectValidationError",
    "ProjectView",
]