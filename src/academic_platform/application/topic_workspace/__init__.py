"""Topic & Problem workspace.

This subpackage owns the persistent state of the research assistant's
Topic & Problem section:

- ``TopicField`` — the closed set of fields the workspace captures.
- ``TopicDraft`` — an immutable view of the workspace's current state.
- ``TopicCompleteness`` — the completeness report produced by the
  service.
- ``TopicWorkspaceService`` — the application service that creates,
  reads, updates, and clears topic drafts.
- ``TopicWorkspaceError`` and subclasses — typed errors.

The workspace is anchored to a research project. When a project is
attached to the research assistant, the workspace reads and writes the
project's topic fields. When no project is attached, the workspace
holds a draft in memory that can be attached to a project later.

The service never imports Qt. It reads and writes through the research
project repository and writes audit events through the audit
repository.
"""

from academic_platform.application.topic_workspace.errors import (
    TopicWorkspaceError,
    TopicWorkspaceNotAttachedError,
    TopicWorkspaceNotFoundError,
    TopicWorkspaceValidationError,
)
from academic_platform.application.topic_workspace.model import (
    TopicCompleteness,
    TopicDraft,
    TopicField,
)
from academic_platform.application.topic_workspace.service import (
    TopicWorkspaceService,
)

__all__ = [
    "TopicCompleteness",
    "TopicDraft",
    "TopicField",
    "TopicWorkspaceError",
    "TopicWorkspaceNotAttachedError",
    "TopicWorkspaceNotFoundError",
    "TopicWorkspaceService",
    "TopicWorkspaceValidationError",
]