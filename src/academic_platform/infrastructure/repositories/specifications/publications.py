"""Specifications for the publication repository."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import Publication
from academic_platform.infrastructure.repositories.specification import Specification


class PublicationByDoi(Specification[Publication]):
    """Matches the publication with the given DOI."""

    def __init__(self, doi: str) -> None:
        self._doi = doi

    def to_expression(self, entity: type[Publication]):
        return entity.doi == self._doi


class PublicationOpenAccess(Specification[Publication]):
    """Matches open-access publications."""

    def to_expression(self, entity: type[Publication]):
        return entity.is_open_access == 1


class PublicationTitleContains(Specification[Publication]):
    """Matches publications whose title contains a fragment."""

    def __init__(self, fragment: str) -> None:
        self._fragment = fragment

    def to_expression(self, entity: type[Publication]):
        return entity.title.ilike(f"%{self._fragment}%")


class PublicationInYearRange(Specification[Publication]):
    """Matches publications within an inclusive year range."""

    def __init__(self, start_year: int, end_year: int) -> None:
        self._start = start_year
        self._end = end_year

    def to_expression(self, entity: type[Publication]):
        return (entity.year >= self._start) & (entity.year <= self._end)