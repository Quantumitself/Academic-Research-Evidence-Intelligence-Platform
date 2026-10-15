"""Search source registry service.

This subpackage owns everything the application layer needs to manage
configurable search sources:

- ``SourceConfig`` — the immutable value object describing a source's
  persisted configuration.
- ``SourceRecord`` — the typed view of a row from the ``search_source``
  table.
- ``SourceResolver`` — resolves a persisted source to a provider adapter
  using the provider registry.
- ``SearchSourceService`` — the application service that lists, enables,
  disables, tests, and queries sources.
- ``SourceValidationError`` — the typed error surfaced to callers.

The subpackage never imports Qt. It may import from the application
layer's settings service, the infrastructure provider registry, and the
repository layer.
"""

from academic_platform.application.search_sources.errors import (
    SourceNotFoundError,
    SourceValidationError,
)
from academic_platform.application.search_sources.source_config import (
    SourceConfig,
    SourceRecord,
)
from academic_platform.application.search_sources.source_resolver import (
    SourceResolver,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)

__all__ = [
    "SearchSourceService",
    "SourceConfig",
    "SourceNotFoundError",
    "SourceRecord",
    "SourceResolver",
    "SourceValidationError",
]