"""Architecture Decision Records (ADR) subsystem.

This subpackage provides:

- A parser for ADR markdown files stored under ``docs/adr/``.
- A validator that enforces the ADR template structure.
- A generator that produces ``docs/adr/README.md`` (the index).
- A query interface used by the ``scripts/adr.py`` command-line tool and by
  application diagnostics.

The parser is deliberately strict: an ADR that does not conform to the
template is reported as invalid rather than silently accepted. This guarantees
that the index and the query interface operate on well-formed records only.
"""

from academic_platform.app.adr.model import (
    ADR,
    ADRStatus,
    ADRValidationError,
    ADRValidationIssue,
)
from academic_platform.app.adr.parser import parse_adr_file, parse_adr_directory
from academic_platform.app.adr.registry import ADRRegistry
from academic_platform.app.adr.validator import validate_adr

__all__ = [
    "ADR",
    "ADRStatus",
    "ADRValidationError",
    "ADRValidationIssue",
    "ADRRegistry",
    "parse_adr_file",
    "parse_adr_directory",
    "validate_adr",
]