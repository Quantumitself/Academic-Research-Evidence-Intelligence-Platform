"""Specifications for the annotation repository."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import Annotation
from academic_platform.infrastructure.repositories.specification import Specification


class AnnotationByDocument(Specification[Annotation]):
    """Matches annotations belonging to a document."""

    def __init__(self, document_id: int) -> None:
        self._document_id = document_id

    def to_expression(self, entity: type[Annotation]):
        return entity.document_id == self._document_id


class AnnotationByKind(Specification[Annotation]):
    """Matches annotations of a specific kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def to_expression(self, entity: type[Annotation]):
        return entity.kind == self._kind


class AnnotationOnPage(Specification[Annotation]):
    """Matches annotations on a specific page of a document."""

    def __init__(self, document_id: int, page_number: int) -> None:
        self._document_id = document_id
        self._page_number = page_number

    def to_expression(self, entity: type[Annotation]):
        return (entity.document_id == self._document_id) & (
            entity.page_number == self._page_number
        )