"""Application service for linking documents to collections and projects.

The service associates a document with collections and projects. It
reuses the collection and project repositories and the
``collection_item`` association. Adding a document to a project creates
a project-linked collection automatically when one does not exist, so
that the association is visible through the collection view as well.

Design decisions
----------------
- A document is identified by its document key. The service never
  resolves the file path; linking is a purely relational operation.
- A project link is implemented as membership in a project-linked
  collection. The service creates the project-linked collection on
  demand and reuses it across subsequent links. This keeps the data
  model consistent: a document belongs to a collection, and a
  project-linked collection belongs to a project.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The service is idempotent: adding a document that is already linked
  does not create a duplicate association, and removing a document
  that is not linked does not fail.
"""

from __future__ import annotations

import logging

from academic_platform.application.document_linking.errors import (
    LinkingError,
    LinkingTargetNotFoundError,
)
from academic_platform.application.document_linking.model import (
    CollectionOption,
    DocumentLinkView,
    LinkTarget,
    LinkingResult,
    ProjectOption,
)
from academic_platform.infrastructure.database.models import (
    Collection,
    CollectionItem,
    ResearchProject,
)
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_PROJECT_COLLECTION_KEY_PREFIX = "project-"


class DocumentLinkingService:
    """Link documents to collections and projects."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_collection_options(self) -> list[CollectionOption]:
        """Return every collection available as a link target."""
        repo = self._repositories.get("collection")
        try:
            collections = repo.find_all(order_by=[Collection.title])
        except RepositoryError as exc:
            raise LinkingError(f"Unable to list collections: {exc}") from exc
        options: list[CollectionOption] = []
        item_repo = self._repositories.get("collection_item")
        for collection in collections:
            try:
                count = len(item_repo.list_for_collection(collection.id))
            except RepositoryError:
                count = 0
            options.append(
                CollectionOption(
                    key=collection.key,
                    title=collection.title,
                    kind=collection.kind,
                    item_count=count,
                )
            )
        return options

    def list_project_options(self) -> list[ProjectOption]:
        """Return every project available as a link target."""
        repo = self._repositories.get("research_project")
        try:
            projects = repo.find_all(order_by=[ResearchProject.title])
        except RepositoryError as exc:
            raise LinkingError(f"Unable to list projects: {exc}") from exc
        return [
            ProjectOption(
                key=project.key,
                title=project.title,
                stage=project.stage,
            )
            for project in projects
        ]

    def links_for_document(self, document_key: str) -> DocumentLinkView:
        """Return the collections and projects a document is linked to."""
        self._require_document(document_key)
        collections = self._collections_for_document(document_key)
        projects = self._projects_for_document(document_key)
        return DocumentLinkView(
            document_key=document_key,
            collections=tuple(collections),
            projects=tuple(projects),
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def link_document_to_collection(
        self,
        document_key: str,
        collection_key: str,
    ) -> LinkingResult:
        """Add a document to a collection."""
        self._require_document(document_key)
        collection = self._require_collection(collection_key)
        added = self._add_collection_item(collection, document_key)
        return LinkingResult(
            document_key=document_key,
            target=LinkTarget.COLLECTION,
            target_key=collection_key,
            linked=True,
            message="Document added to the collection.",
            affected=1 if added else 0,
        )

    def unlink_document_from_collection(
        self,
        document_key: str,
        collection_key: str,
    ) -> LinkingResult:
        """Remove a document from a collection."""
        self._require_document(document_key)
        collection = self._require_collection(collection_key)
        removed = self._remove_collection_item(collection, document_key)
        return LinkingResult(
            document_key=document_key,
            target=LinkTarget.COLLECTION,
            target_key=collection_key,
            linked=False,
            message=(
                "Document removed from the collection."
                if removed
                else "The document was not in the collection."
            ),
            affected=1 if removed else 0,
        )

    def link_document_to_project(
        self,
        document_key: str,
        project_key: str,
    ) -> LinkingResult:
        """Add a document to a project.

        The association is implemented through a project-linked
        collection. The collection is created on demand and reused
        across subsequent links.
        """
        self._require_document(document_key)
        project = self._require_project(project_key)
        collection = self._ensure_project_collection(project)
        added = self._add_collection_item(collection, document_key)
        return LinkingResult(
            document_key=document_key,
            target=LinkTarget.PROJECT,
            target_key=project_key,
            linked=True,
            message="Document added to the project.",
            affected=1 if added else 0,
        )

    def unlink_document_from_project(
        self,
        document_key: str,
        project_key: str,
    ) -> LinkingResult:
        """Remove a document from a project."""
        self._require_document(document_key)
        project = self._require_project(project_key)
        collection = self._find_project_collection(project)
        if collection is None:
            return LinkingResult(
                document_key=document_key,
                target=LinkTarget.PROJECT,
                target_key=project_key,
                linked=False,
                message="The project has no linked collection.",
                affected=0,
            )
        removed = self._remove_collection_item(collection, document_key)
        return LinkingResult(
            document_key=document_key,
            target=LinkTarget.PROJECT,
            target_key=project_key,
            linked=False,
            message=(
                "Document removed from the project."
                if removed
                else "The document was not in the project."
            ),
            affected=1 if removed else 0,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_document(self, document_key: str) -> None:
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise LinkingError(f"Unable to read document: {exc}") from exc
        if row is None:
            raise LinkingError(f"No document with key {document_key!r}")

    def _require_collection(self, key: str) -> Collection:
        repo = self._repositories.get("collection")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise LinkingError(f"Unable to read collection: {exc}") from exc
        if row is None:
            raise LinkingTargetNotFoundError(
                f"No collection with key {key!r}"
            )
        return row

    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise LinkingError(f"Unable to read project: {exc}") from exc
        if row is None:
            raise LinkingTargetNotFoundError(
                f"No project with key {key!r}"
            )
        return row

    def _ensure_project_collection(self, project: ResearchProject) -> Collection:
        existing = self._find_project_collection(project)
        if existing is not None:
            return existing
        repo = self._repositories.get("collection")
        key = f"{_PROJECT_COLLECTION_KEY_PREFIX}{project.key}"
        collection = Collection(
            key=key,
            title=f"{project.title or project.key} — documents",
            description=(
                "Documents associated with the project. Managed "
                "automatically when documents are linked to the project."
            ),
            kind="project",
            project_id=project.id,
        )
        try:
            return repo.add(collection)
        except DuplicateEntityError:
            # A concurrent operation created the collection; re-read.
            existing = self._find_project_collection(project)
            if existing is not None:
                return existing
            raise LinkingError(
                f"Unable to create the project collection for {project.key!r}"
            )

    def _find_project_collection(self, project: ResearchProject) -> Collection | None:
        repo = self._repositories.get("collection")
        try:
            return repo.find_by_key(
                f"{_PROJECT_COLLECTION_KEY_PREFIX}{project.key}"
            )
        except RepositoryError:
            return None

    def _add_collection_item(
        self,
        collection: Collection,
        document_key: str,
    ) -> bool:
        repo = self._repositories.get("collection_item")
        try:
            existing = repo.find_for_target(collection.id, "document", document_key)
        except RepositoryError as exc:
            raise LinkingError(f"Unable to read collection items: {exc}") from exc
        if existing is not None:
            return False
        try:
            repo.add_item(collection.id, "document", document_key)
        except RepositoryError as exc:
            raise LinkingError(f"Unable to add the document: {exc}") from exc
        return True

    def _remove_collection_item(
        self,
        collection: Collection,
        document_key: str,
    ) -> bool:
        repo = self._repositories.get("collection_item")
        try:
            return repo.remove_item(collection.id, "document", document_key)
        except RepositoryError as exc:
            raise LinkingError(f"Unable to remove the document: {exc}") from exc

    def _collections_for_document(self, document_key: str) -> list[CollectionOption]:
        collection_repo = self._repositories.get("collection")
        try:
            collections = collection_repo.find_all(order_by=[Collection.title])
        except RepositoryError as exc:
            raise LinkingError(f"Unable to list collections: {exc}") from exc
        item_repo = self._repositories.get("collection_item")
        results: list[CollectionOption] = []
        for collection in collections:
            # Project-linked collections are represented through the
            # project list, not the collection list.
            if collection.kind == "project":
                continue
            try:
                item = item_repo.find_for_target(
                    collection.id, "document", document_key
                )
            except RepositoryError:
                item = None
            if item is None:
                continue
            results.append(
                CollectionOption(
                    key=collection.key,
                    title=collection.title,
                    kind=collection.kind,
                )
            )
        return results

    def _projects_for_document(self, document_key: str) -> list[ProjectOption]:
        collection_repo = self._repositories.get("collection")
        project_repo = self._repositories.get("research_project")
        try:
            collections = collection_repo.find_all(order_by=[Collection.title])
        except RepositoryError as exc:
            raise LinkingError(f"Unable to list collections: {exc}") from exc
        item_repo = self._repositories.get("collection_item")
        project_ids: set[int] = set()
        for collection in collections:
            if collection.kind != "project" or collection.project_id is None:
                continue
            try:
                item = item_repo.find_for_target(
                    collection.id, "document", document_key
                )
            except RepositoryError:
                item = None
            if item is not None:
                project_ids.add(collection.project_id)
        results: list[ProjectOption] = []
        for project_id in project_ids:
            try:
                project = project_repo.get(project_id)
            except RepositoryError:
                project = None
            if project is None:
                continue
            results.append(
                ProjectOption(
                    key=project.key,
                    title=project.title,
                    stage=project.stage,
                )
            )
        results.sort(key=lambda option: option.title.lower())
        return results