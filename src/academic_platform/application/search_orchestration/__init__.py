"""Search orchestration.

This subpackage owns the coordination of a search request across every
enabled and selected search source. It provides:

- ``SearchOrchestrator`` — the application service.
- ``SearchOrchestrationRequest`` — an immutable description of the search
  to execute.
- ``SearchOrchestrationResponse`` — the outcome of a search, including
  per-source status and the persisted publications.
- ``SourceSelection`` — the set of sources the request targets.
- Typed errors in ``errors``.

The subpackage never imports Qt. It may import from the provider adapter
interface, the source registry service, the publication service, and the
repository layer.
"""

from academic_platform.application.search_orchestration.errors import (
    SearchOrchestrationError,
    SearchOrchestrationConfigurationError,
)
from academic_platform.application.search_orchestration.orchestrator import (
    SearchOrchestrator,
)
from academic_platform.application.search_orchestration.request import (
    SearchOrchestrationRequest,
    SourceSelection,
)
from academic_platform.application.search_orchestration.response import (
    SearchOrchestrationResponse,
    SourceOutcome,
    SourceOutcomeStatus,
)

__all__ = [
    "SearchOrchestrationConfigurationError",
    "SearchOrchestrationError",
    "SearchOrchestrationRequest",
    "SearchOrchestrationResponse",
    "SearchOrchestrator",
    "SourceOutcome",
    "SourceOutcomeStatus",
    "SourceSelection",
]