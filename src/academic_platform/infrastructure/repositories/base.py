"""Typed base repository.

``Repository`` provides the standard operations shared by every concrete
repository: get by primary key, list, count, exists, create, update,
delete, and paginated listing with optional specifications and ordering.

Design decisions
----------------
- The base class is generic over the ORM entity type. Concrete
  repositories subclass ``Repository[SomeModel]`` and inherit the full
  set of operations without duplicating them.
- The session is supplied at construction. Repositories do not own a
  session factory; they operate on the session they are given. This makes
  it possible to compose multiple repositories into a single unit of work
  and to test them against an in-memory session.
- The base class does not commit. Commits are the caller's responsibility
  and are performed through ``Database.session()``. Repositories flush
  when they need to materialize server-generated values.
- ``create`` accepts a Pydantic ``Create`` schema when one is provided.
  Concrete repositories declare the schema type; the base class
  instantiates the ORM model from the validated payload.
- ``update`` accepts a Pydantic ``Update`` schema. Only fields explicitly
  set on the schema are applied; unset fields are left unchanged.
- Uniqueness constraint violations are translated into
  ``DuplicateEntityError``. Absence is translated into
  ``EntityNotFoundError`` only when the caller requests strict semantics.
- Errors raised from the database are translated into the repository's
  typed exceptions. Callers never see SQLAlchemy exceptions.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, delete as sa_delete, func, select, update as sa_update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    RepositoryValidationError,
)
from academic_platform.infrastructure.repositories.pagination import Page, PageRequest
from academic_platform.infrastructure.repositories.specification import Specification

_logger = logging.getLogger(__name__)

EntityT = TypeVar("EntityT", bound=Base)
CreateSchemaT = TypeVar("CreateSchemaT", bound=BaseModel)
UpdateSchemaT = TypeVar("UpdateSchemaT", bound=BaseModel)


class Repository(Generic[EntityT]):
    """Base class for repositories bound to a single ORM entity."""

    #: The ORM entity class managed by this repository. Concrete
    #: subclasses must set this attribute.
    entity: type[EntityT]

    def __init__(self, session: Session) -> None:
        if not hasattr(type(self), "entity"):
            raise RepositoryError(
                f"{type(self).__name__} must declare an 'entity' attribute"
            )
        self._session = session

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def session(self) -> Session:
        """Return the session this repository is bound to."""
        return self._session

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def get(self, identifier: Any) -> EntityT | None:
        """Return the entity with the given primary key, or ``None``."""
        try:
            return self._session.get(self.entity, identifier)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"get failed: {exc}") from exc

    def get_or_raise(self, identifier: Any) -> EntityT:
        """Return the entity with the given primary key.

        Raises
        ------
        EntityNotFoundError
            If no entity matches the identifier.
        """
        instance = self.get(identifier)
        if instance is None:
            raise EntityNotFoundError(
                f"{self.entity.__name__} with id {identifier!r} not found"
            )
        return instance

    def find_one(self, specification: Specification[EntityT]) -> EntityT | None:
        """Return the first entity matching the specification, or ``None``."""
        statement = select(self.entity).where(specification.to_expression(self.entity))
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_one failed: {exc}") from exc

    def find_all(
        self,
        specification: Specification[EntityT] | None = None,
        *,
        order_by: Sequence[Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[EntityT]:
        """Return all entities matching the specification.

        Parameters
        ----------
        specification:
            Optional predicate. When None, every row is returned.
        order_by:
            Optional sequence of column expressions or ORM attributes to
            order by. Applied in the given order.
        limit:
            Optional row limit.
        offset:
            Optional row offset.
        """
        statement = self._build_select(specification, order_by, limit, offset)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_all failed: {exc}") from exc

    def find_page(
        self,
        request: PageRequest,
        specification: Specification[EntityT] | None = None,
        *,
        order_by: Sequence[Any] | None = None,
    ) -> Page[EntityT]:
        """Return a page of entities matching the specification."""
        total = self.count(specification)
        items = self.find_all(
            specification,
            order_by=order_by,
            limit=request.limit,
            offset=request.offset,
        )
        return Page(items=items, request=request, total=total)

    def count(self, specification: Specification[EntityT] | None = None) -> int:
        """Return the number of entities matching the specification."""
        statement = select(func.count()).select_from(self.entity)
        if specification is not None:
            statement = statement.where(specification.to_expression(self.entity))
        try:
            result = self._session.execute(statement).scalar()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"count failed: {exc}") from exc
        return int(result or 0)

    def exists(self, specification: Specification[EntityT] | None = None) -> bool:
        """Return True when at least one entity matches the specification."""
        statement = select(self.entity)
        if specification is not None:
            statement = statement.where(specification.to_expression(self.entity))
        statement = statement.limit(1)
        try:
            return self._session.execute(statement).scalars().first() is not None
        except SQLAlchemyError as exc:
            raise RepositoryError(f"exists failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    def add(self, entity: EntityT) -> EntityT:
        """Add a fully constructed ORM entity to the session.

        The entity is flushed so that server-generated values such as
        primary keys and defaults are materialized before the method
        returns.
        """
        try:
            self._session.add(entity)
            self._session.flush()
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Unable to add {self.entity.__name__}: {exc.orig}"
            ) from exc
        except SQLAlchemyError as exc:
            raise RepositoryError(f"add failed: {exc}") from exc
        return entity

    def create(self, payload: BaseModel) -> EntityT:
        """Create an entity from a validated Pydantic payload.

        The payload must be an instance of a Pydantic model. Its
        ``model_dump`` result is passed as keyword arguments to the ORM
        entity constructor. Fields that are ``None`` are included so that
        explicit nulls are preserved; use the schema's ``model_dump``
        with ``exclude_unset=True`` at the call site if unset fields must
        be omitted.
        """
        if not isinstance(payload, BaseModel):
            raise RepositoryValidationError(
                "create expects a Pydantic model instance"
            )
        try:
            entity = self.entity(**payload.model_dump())
        except TypeError as exc:
            raise RepositoryValidationError(
                f"Unable to construct {self.entity.__name__}: {exc}"
            ) from exc
        return self.add(entity)

    def update(self, entity: EntityT, payload: BaseModel) -> EntityT:
        """Apply a validated Pydantic payload to an existing entity.

        Only fields present in ``payload.model_fields_set`` are applied.
        Fields absent from the payload are left unchanged.
        """
        if not isinstance(payload, BaseModel):
            raise RepositoryValidationError(
                "update expects a Pydantic model instance"
            )
        changes = payload.model_dump(exclude_unset=True)
        for field_name, value in changes.items():
            if not hasattr(entity, field_name):
                raise RepositoryValidationError(
                    f"{self.entity.__name__} has no field {field_name!r}"
                )
            setattr(entity, field_name, value)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Unable to update {self.entity.__name__}: {exc.orig}"
            ) from exc
        except SQLAlchemyError as exc:
            raise RepositoryError(f"update failed: {exc}") from exc
        return entity

    def delete(self, entity: EntityT) -> None:
        """Delete the entity from the session."""
        try:
            self._session.delete(entity)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"delete failed: {exc}") from exc

    def delete_by_id(self, identifier: Any) -> bool:
        """Delete the entity with the given primary key.

        Returns True when a row was deleted and False when no row matched.
        """
        try:
            result = self._session.execute(
                sa_delete(self.entity).where(self.entity.id == identifier)
            )
        except SQLAlchemyError as exc:
            raise RepositoryError(f"delete_by_id failed: {exc}") from exc
        return bool(result.rowcount)

    def update_fields(self, identifier: Any, **changes: Any) -> EntityT:
        """Apply field changes to an entity identified by primary key.

        Returns the refreshed entity. Raises ``EntityNotFoundError`` when
        no row matches the identifier.
        """
        try:
            self._session.execute(
                sa_update(self.entity)
                .where(self.entity.id == identifier)
                .values(**changes)
            )
            self._session.flush()
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Unable to update {self.entity.__name__}: {exc.orig}"
            ) from exc
        except SQLAlchemyError as exc:
            raise RepositoryError(f"update_fields failed: {exc}") from exc
        return self.get_or_raise(identifier)

    def add_all(self, entities: Iterable[EntityT]) -> list[EntityT]:
        """Add multiple entities in a single flush."""
        materialized = list(entities)
        try:
            self._session.add_all(materialized)
            self._session.flush()
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Unable to add batch to {self.entity.__name__}: {exc.orig}"
            ) from exc
        except SQLAlchemyError as exc:
            raise RepositoryError(f"add_all failed: {exc}") from exc
        return materialized

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_select(
        self,
        specification: Specification[EntityT] | None,
        order_by: Sequence[Any] | None,
        limit: int | None,
        offset: int | None,
    ) -> Select:
        statement = select(self.entity)
        if specification is not None:
            statement = statement.where(specification.to_expression(self.entity))
        if order_by:
            statement = statement.order_by(*order_by)
        if limit is not None:
            statement = statement.limit(limit)
        if offset is not None:
            statement = statement.offset(offset)
        return statement