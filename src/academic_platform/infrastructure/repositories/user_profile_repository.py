"""Repository for user profiles.

The user profile table is small and its access pattern is trivial:
lookup by stable key, listing, and creation. The repository exposes those
operations plus the standard base operations. It adds no query
specification types because every access pattern is by primary key or by
the unique ``key`` column.
"""

from __future__ import annotations

from sqlalchemy import select

from academic_platform.infrastructure.database.models import UserProfile
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError
from sqlalchemy.exc import SQLAlchemyError


class UserProfileRepository(Repository[UserProfile]):
    """Repository for the ``user_profile`` table."""

    entity = UserProfile

    def find_by_key(self, key: str) -> UserProfile | None:
        """Return the profile with the given stable key, or ``None``.

        The ``key`` column is unique and indexed; the query is a single
        indexed lookup.
        """
        statement = select(UserProfile).where(UserProfile.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def get_or_create_by_key(self, key: str, **defaults) -> tuple[UserProfile, bool]:
        """Return the profile with the given key, creating it when absent.

        Returns a tuple ``(profile, created)``. When the profile already
        exists, ``created`` is ``False`` and the defaults are ignored.
        Defaults are applied only on creation.
        """
        existing = self.find_by_key(key)
        if existing is not None:
            return existing, False
        profile = UserProfile(key=key, **defaults)
        return self.add(profile), True

    def list_keys(self) -> list[str]:
        """Return every profile key, sorted alphabetically."""
        statement = select(UserProfile.key).order_by(UserProfile.key)
        try:
            return [row for row in self._session.execute(statement).scalars().all()]
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_keys failed: {exc}") from exc