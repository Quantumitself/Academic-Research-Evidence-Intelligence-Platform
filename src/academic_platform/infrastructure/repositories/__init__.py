"""Repository pattern foundation.

Repositories mediate between the application layer and the persistence
layer. They translate domain-level operations into ORM calls, keep
session handling out of the application layer, and provide a single
place where query composition and validation live.

Public surface
--------------
- ``Repository`` — the typed base class.
- ``Specification`` — a composable query predicate.
- ``AndSpecification``, ``OrSpecification``, ``NotSpecification`` —
  logical combinators.
- ``Page``, ``PageRequest`` — pagination primitives.
- ``RepositoryManager`` — constructs repositories bound to a session.

The package never depends on the presentation layer. It may import from
the ORM and from the domain layer.
"""

from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.manager import RepositoryManager
from academic_platform.infrastructure.repositories.pagination import Page, PageRequest
from academic_platform.infrastructure.repositories.specification import (
    AndSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)

__all__ = [
    "AndSpecification",
    "NotSpecification",
    "OrSpecification",
    "Page",
    "PageRequest",
    "Repository",
    "RepositoryManager",
    "Specification",
]