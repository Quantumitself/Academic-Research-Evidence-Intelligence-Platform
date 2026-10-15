"""Application service for project export.

The service composes a self-contained document from a project and its
related entities. It supports JSON and Markdown output.

Design decisions
----------------
- The service is a pure read operation over the project, question,
  task, collection, and document repositories. It never writes to the
  database.
- Output is written to a file the caller supplies. The caller is
  responsible for picking the destination and for confirming
  overwrites.
- The JSON schema is stable and versioned. Adding new fields is
  forward-compatible; removing fields requires a version increment.
- The Markdown output is human-readable and source-linked. Linked
  documents carry their keys so that the reader can trace a reference.
- Milestones are included in both the tasks section and the milestones
  section when both are selected, because a milestone is a task with a
  flag. The duplication is deliberate: the tasks section shows every
  task, the milestones section highlights milestones.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from academic_platform.application.project_export.errors import (
    ProjectExportError,
    ProjectExportNotFoundError,
)
from academic_platform.application.project_export.model import (
    ExportFormat,
    ExportOptions,
    ExportResult,
    ExportSection,
)
from academic_platform.infrastructure.database.models import (
    Collection,
    CollectionItem,
    DocumentAsset,
    DocumentMetadata,
    ResearchProject,
    ResearchQuestion,
    ResearchTask,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_PROJECT_COLLECTION_PREFIX = "project-"


class ProjectExportService:
    """Application service for project export."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def export(
        self,
        project_key: str,
        output_path: Path,
        *,
        options: ExportOptions | None = None,
        overwrite: bool = False,
    ) -> ExportResult:
        """Export a project to the given path.

        Parameters
        ----------
        project_key:
            The project to export.
        output_path:
            The destination path. The caller is responsible for
            supplying a path whose parent directory exists.
        options:
            Inclusion options. Defaults to JSON with every section.
        overwrite:
            When True, an existing file at the destination is replaced.
            When False, an existing file causes an error.

        Raises
        ------
        ProjectExportNotFoundError
            If the project does not exist.
        ProjectExportError
            If the file cannot be written or if the payload cannot be
            serialized.
        """
        options = options or ExportOptions()
        project = self._require_project(project_key)
        if output_path.exists() and not overwrite:
            raise ProjectExportError(
                f"Destination already exists: {output_path}. "
                "Pass overwrite=True to replace it."
            )
        payload = self._build_payload(project, options)
        if options.format is ExportFormat.JSON:
            content = _render_json(payload)
        else:
            content = _render_markdown(payload, options)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ProjectExportError(
                f"Unable to write the export file: {exc}"
            ) from exc
        bytes_written = len(content.encode("utf-8"))
        _logger.info(
            "Exported project %s to %s (%d bytes)",
            project_key,
            output_path,
            bytes_written,
        )
        return ExportResult(
            project_key=project_key,
            format=options.format,
            output_path=str(output_path),
            bytes_written=bytes_written,
            sections=tuple(sorted(options.sections, key=lambda s: s.value)),
        )

    def build_json(self, project_key: str, options: ExportOptions | None = None) -> str:
        """Return the JSON representation of a project without writing it."""
        options = options or ExportOptions(format=ExportFormat.JSON)
        project = self._require_project(project_key)
        payload = self._build_payload(project, options)
        return _render_json(payload)

    def build_markdown(
        self, project_key: str, options: ExportOptions | None = None
    ) -> str:
        """Return the Markdown representation of a project without writing it."""
        options = options or ExportOptions(format=ExportFormat.MARKDOWN)
        project = self._require_project(project_key)
        payload = self._build_payload(project, options)
        return _render_markdown(payload, options)

    def suggested_filename(self, project_key: str, export_format: ExportFormat) -> str:
        """Return a suggested filename for the export."""
        project = self._require_project(project_key)
        stem = _safe_filename_stem(project.key or project.title or "project")
        return f"{stem}{export_format.extension}"

    # ------------------------------------------------------------------
    # Payload composition
    # ------------------------------------------------------------------
    def _build_payload(
        self,
        project: ResearchProject,
        options: ExportOptions,
    ) -> dict:
        payload: dict = {
            "schema_version": _SCHEMA_VERSION,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "project_key": project.key,
        }
        if options.includes_project_fields:
            payload["project"] = self._project_fields(project)
        if options.includes_research_questions:
            payload["research_questions"] = self._research_questions(project.id)
        if options.includes_tasks:
            payload["tasks"] = self._tasks(project.id)
        if options.includes_milestones:
            payload["milestones"] = self._milestones(project.id)
        if options.includes_collections:
            payload["collections"] = self._collections(project.key)
        if options.includes_linked_documents:
            payload["linked_documents"] = self._linked_documents(project.key)
        return payload

    def _project_fields(self, project: ResearchProject) -> dict:
        return {
            "key": project.key,
            "title": project.title,
            "topic": project.topic,
            "stage": project.stage,
            "project_metadata": project.project_metadata,
            "created_at": project.created_at.isoformat()
            if project.created_at
            else None,
            "updated_at": project.updated_at.isoformat()
            if project.updated_at
            else None,
            "version": project.version,
        }

    def _research_questions(self, project_id: int) -> list[dict]:
        repo = self._repositories.get("research_question")
        try:
            rows = repo.list_for_project(project_id)
        except RepositoryError as exc:
            raise ProjectExportError(
                f"Unable to read research questions: {exc}"
            ) from exc
        return [
            {
                "id": row.id,
                "text": row.text,
                "kind": row.kind,
                "is_primary": bool(row.is_primary),
                "position": row.position,
                "created_at": row.created_at.isoformat()
                if row.created_at
                else None,
                "updated_at": row.updated_at.isoformat()
                if row.updated_at
                else None,
            }
            for row in rows
        ]

    def _tasks(self, project_id: int) -> list[dict]:
        repo = self._repositories.get("research_task")
        try:
            rows = repo.list_for_project(project_id)
        except RepositoryError as exc:
            raise ProjectExportError(f"Unable to read tasks: {exc}") from exc
        return [_task_payload(row) for row in rows]

    def _milestones(self, project_id: int) -> list[dict]:
        return [
            task
            for task in self._tasks(project_id)
            if bool(task.get("is_milestone"))
        ]

    def _collections(self, project_key: str) -> list[dict]:
        repo = self._repositories.get("collection")
        try:
            collections = repo.find_all(order_by=[Collection.title])
        except RepositoryError as exc:
            raise ProjectExportError(
                f"Unable to read collections: {exc}"
            ) from exc
        result: list[dict] = []
        item_repo = self._repositories.get("collection_item")
        for collection in collections:
            if collection.kind != "project":
                continue
            if not collection.key.startswith(_PROJECT_COLLECTION_PREFIX):
                continue
            expected = f"{_PROJECT_COLLECTION_PREFIX}{project_key}"
            if collection.key != expected:
                continue
            try:
                items = item_repo.list_for_collection(collection.id)
            except RepositoryError:
                items = []
            result.append(
                {
                    "key": collection.key,
                    "title": collection.title,
                    "description": collection.description,
                    "kind": collection.kind,
                    "item_count": len(items),
                }
            )
        return result

    def _linked_documents(self, project_key: str) -> list[dict]:
        collection_repo = self._repositories.get("collection")
        collection_key = f"{_PROJECT_COLLECTION_PREFIX}{project_key}"
        try:
            collection = collection_repo.find_by_key(collection_key)
        except RepositoryError:
            collection = None
        if collection is None:
            return []
        item_repo = self._repositories.get("collection_item")
        try:
            items = item_repo.list_for_collection(collection.id)
        except RepositoryError as exc:
            raise ProjectExportError(
                f"Unable to read collection items: {exc}"
            ) from exc
        document_repo = self._repositories.get("document_asset")
        metadata_repo = self._repositories.get("document_metadata")
        results: list[dict] = []
        for item in items:
            if item.item_type != "document":
                continue
            try:
                document = document_repo.find_by_key(item.item_identifier)
            except RepositoryError:
                document = None
            if document is None:
                results.append(
                    {
                        "document_key": item.item_identifier,
                        "missing_from_library": True,
                        "note": item.note,
                    }
                )
                continue
            try:
                metadata = metadata_repo.find_for_document(document.id)
            except RepositoryError:
                metadata = None
            results.append(
                {
                    "document_key": document.key,
                    "display_name": document.display_name,
                    "storage_mode": document.storage_mode,
                    "processing_state": document.processing_state,
                    "page_count": document.page_count,
                    "title": metadata.title if metadata else None,
                    "year": metadata.year if metadata else None,
                    "doi": metadata.doi if metadata else None,
                    "note": item.note,
                }
            )
        return results

    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise ProjectExportError(
                f"Unable to read the project: {exc}"
            ) from exc
        if row is None:
            raise ProjectExportNotFoundError(f"No project with key {key!r}")
        return row


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def _task_payload(row: ResearchTask) -> dict:
    status = getattr(row, "status", None) or (
        "done" if row.completed else "open"
    )
    priority = getattr(row, "priority", None) or "normal"
    is_milestone = bool(getattr(row, "is_milestone", 0))
    notes = getattr(row, "notes", "") or ""
    completed_at = getattr(row, "completed_at", None)
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "status": status,
        "priority": priority,
        "is_milestone": is_milestone,
        "notes": notes,
        "position": row.position,
        "completed": bool(row.completed),
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _render_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _render_markdown(payload: dict, options: ExportOptions) -> str:
    lines: list[str] = []
    project = payload.get("project") or {}
    title = project.get("title") or payload.get("project_key") or "Project"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(
        f"_Generated {payload.get('generated_at', '')} — schema version "
        f"{payload.get('schema_version', '?')}_"
    )
    lines.append("")

    if options.includes_project_fields and project:
        lines.append("## Project")
        lines.append("")
        for field in (
            "key",
            "title",
            "topic",
            "stage",
            "created_at",
            "updated_at",
            "version",
        ):
            value = project.get(field)
            if value is None or value == "":
                continue
            lines.append(f"- **{field.replace('_', ' ').title()}:** {value}")
        metadata = project.get("project_metadata")
        if metadata:
            lines.append("")
            lines.append("### Metadata")
            lines.append("")
            lines.append("```")
            lines.append(metadata)
            lines.append("```")
        lines.append("")

    if options.includes_research_questions:
        questions = payload.get("research_questions") or []
        lines.append("## Research questions")
        lines.append("")
        if not questions:
            lines.append("_None recorded._")
            lines.append("")
        else:
            for question in questions:
                prefix = "**Primary** — " if question.get("is_primary") else ""
                lines.append(
                    f"- {prefix}{question.get('text', '')}"
                    f" _({question.get('kind', 'main')})_"
                )
            lines.append("")

    if options.includes_tasks:
        tasks = payload.get("tasks") or []
        lines.append("## Tasks")
        lines.append("")
        if not tasks:
            lines.append("_None recorded._")
            lines.append("")
        else:
            for task in tasks:
                marker = "★ " if task.get("is_milestone") else ""
                lines.append(
                    f"- {marker}[{task.get('status', 'open')}] "
                    f"{task.get('title', '')}"
                )
                description = task.get("description")
                if description:
                    lines.append(f"  - {description}")
                if task.get("due_at"):
                    lines.append(f"  - _Due: {task['due_at']}_")
            lines.append("")

    if options.includes_milestones:
        milestones = payload.get("milestones") or []
        lines.append("## Milestones")
        lines.append("")
        if not milestones:
            lines.append("_None recorded._")
            lines.append("")
        else:
            for milestone in milestones:
                lines.append(
                    f"- **{milestone.get('title', '')}** — "
                    f"{milestone.get('status', 'open')}"
                )
            lines.append("")

    if options.includes_collections:
        collections = payload.get("collections") or []
        lines.append("## Collections")
        lines.append("")
        if not collections:
            lines.append("_None linked to the project._")
            lines.append("")
        else:
            for collection in collections:
                lines.append(
                    f"- **{collection.get('title', '')}** "
                    f"(`{collection.get('key', '')}`) — "
                    f"{collection.get('item_count', 0)} item(s)"
                )
            lines.append("")

    if options.includes_linked_documents:
        documents = payload.get("linked_documents") or []
        lines.append("## Linked documents")
        lines.append("")
        if not documents:
            lines.append("_No documents linked to the project._")
            lines.append("")
        else:
            for document in documents:
                if document.get("missing_from_library"):
                    lines.append(
                        f"- `{document.get('document_key', '')}` "
                        "_— missing from the library_"
                    )
                    continue
                title_part = document.get("title") or document.get("display_name", "")
                year = document.get("year")
                year_part = f" ({year})" if year else ""
                lines.append(f"- {title_part}{year_part}")
                if document.get("doi"):
                    lines.append(f"  - DOI: {document['doi']}")
                note = document.get("note")
                if note:
                    lines.append(f"  - _Note: {note}_")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _safe_filename_stem(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned or "project"