"""Smart-collection evaluation.

This subpackage owns the evaluation of smart collections:

- ``SmartCollectionFilter`` — an immutable description of a smart
  collection's filter, parsed from the collection's JSON payload.
- ``SmartCollectionEvaluator`` — the application service that evaluates
  a filter and returns the matching items.
- ``SmartCollectionError`` and subclasses — typed errors.

The evaluator never persists anything. It reads through the repository
layer and returns value objects. It never imports Qt.
"""

from academic_platform.application.smart_collections.errors import (
    SmartCollectionError,
    SmartCollectionFilterError,
)
from academic_platform.application.smart_collections.filter import (
    SmartCollectionFilter,
    SmartFilterField,
)
from academic_platform.application.smart_collections.evaluator import (
    SmartCollectionEvaluator,
)

__all__ = [
    "SmartCollectionError",
    "SmartCollectionEvaluator",
    "SmartCollectionFilter",
    "SmartCollectionFilterError",
    "SmartFilterField",
]