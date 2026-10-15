"""Composable query specifications.

A specification is a predicate over an ORM entity. Specifications compose
with ``&`` (and), ``|`` (or), and ``~`` (not). Each specification yields
a SQLAlchemy expression through ``to_expression``; the repository applies
that expression to a ``select`` statement.

Design decisions
----------------
- Specifications operate on ORM classes and column attributes, not on
  domain objects. They are a persistence-layer concept.
- The combinator classes wrap two specifications and combine their
  expressions with the corresponding SQLAlchemy operator. ``NotSpecification``
  wraps a single specification and negates its expression.
- Specifications are immutable: their instances hold no mutable state and
  their ``to_expression`` method returns a fresh expression on each call.
- The protocol is defined structurally so that any object with a
  compatible ``to_expression`` method is usable, not only instances of
  ``Specification``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy import not_
from sqlalchemy.sql.elements import ColumnElement

EntityT = TypeVar("EntityT")


class Specification(ABC, Generic[EntityT]):
    """A predicate over an ORM entity."""

    @abstractmethod
    def to_expression(self, entity: type[EntityT]) -> ColumnElement[bool]:
        """Return the SQLAlchemy expression this specification represents.

        Parameters
        ----------
        entity:
            The ORM class the expression will be applied to. It is passed
            explicitly so that a specification can be reused across
            entities that share a common mixin without capturing a class
            reference at construction time.
        """

    def __and__(self, other: "Specification[EntityT]") -> "Specification[EntityT]":
        return AndSpecification(self, other)

    def __or__(self, other: "Specification[EntityT]") -> "Specification[EntityT]":
        return OrSpecification(self, other)

    def __invert__(self) -> "Specification[EntityT]":
        return NotSpecification(self)


class AndSpecification(Specification[EntityT]):
    """Conjunction of two specifications."""

    def __init__(
        self,
        left: Specification[EntityT],
        right: Specification[EntityT],
    ) -> None:
        self._left = left
        self._right = right

    def to_expression(self, entity: type[EntityT]) -> ColumnElement[bool]:
        return self._left.to_expression(entity) & self._right.to_expression(entity)


class OrSpecification(Specification[EntityT]):
    """Disjunction of two specifications."""

    def __init__(
        self,
        left: Specification[EntityT],
        right: Specification[EntityT],
    ) -> None:
        self._left = left
        self._right = right

    def to_expression(self, entity: type[EntityT]) -> ColumnElement[bool]:
        return self._left.to_expression(entity) | self._right.to_expression(entity)


class NotSpecification(Specification[EntityT]):
    """Negation of a specification."""

    def __init__(self, inner: Specification[EntityT]) -> None:
        self._inner = inner

    def to_expression(self, entity: type[EntityT]) -> ColumnElement[bool]:
        return not_(self._inner.to_expression(entity))