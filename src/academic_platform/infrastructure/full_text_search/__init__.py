"""Full-text search infrastructure built on SQLite FTS5.

This subpackage owns the FTS5 index:

- ``FtsIndexer`` — writes document, publication, and note content into
  the FTS5 tables.
- ``FtsQueryService`` — executes MATCH queries and returns ranked hits
  with snippets.
- ``FtsRebuilder`` — reconstructs the FTS5 index from the database.
- ``FtsSearchResult`` — a value object describing a single hit.
- ``FtsError`` and its subclasses — typed errors.

The subpackage never imports Qt. It may import the ORM models, the
database engine, and the FTS5 table definitions.
"""

from academic_platform.infrastructure.full_text_search.errors import (
    FtsError,
    FtsIndexError,
    FtsQueryError,
    FtsRebuildError,
)
from academic_platform.infrastructure.full_text_search.indexer import FtsIndexer
from academic_platform.infrastructure.full_text_search.query import (
    FtsQueryService,
    FtsSearchResult,
    FtsSnippet,
)
from academic_platform.infrastructure.full_text_search.rebuilder import (
    FtsRebuilder,
    FtsRebuildReport,
)

__all__ = [
    "FtsError",
    "FtsIndexError",
    "FtsIndexer",
    "FtsQueryError",
    "FtsRebuildError",
    "FtsRebuildReport",
    "FtsRebuilder",
    "FtsQueryService",
    "FtsSearchResult",
    "FtsSnippet",
]