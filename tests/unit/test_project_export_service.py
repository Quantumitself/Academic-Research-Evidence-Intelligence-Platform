"""Tests for the project export service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from academic_platform.application.project_export.errors import (
    ProjectExportError,
    ProjectExportNotFoundError,
)
from academic_platform.application.project_export.model import (
    ExportFormat,
    ExportOptions,
    ExportSection,
)
from academic_platform.application.project_export.service import (
    ProjectExportService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Collection,
    CollectionItem,
    DocumentAsset,
    DocumentMetadata,
    ResearchProject,
    ResearchQuestion,
    ResearchTask,
)
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(
            key="study-1",
            title="Study One",
            topic="Measurement",
            stage="design",
        )
        session.add(project)
        session.flush()
        session.add(
            ResearchQuestion(
                project_id=project.id,
                text="What is the effect?",
                kind="main",
                is_primary=1,
                position=0,
            )
        )
        task_a = ResearchTask(
            project_id=project.id,
            title="Read papers",
            description="Read the key references.",
            position=0,
        )
        task_a.status = "done"
        task_a.priority = "high"
        task_a.is_milestone = 0
        task_a.notes = "Reviewed the main papers."
        task_a.completed = 1
        session.add(task_a)
        task_b = ResearchTask(
            project_id=project.id,
            title="Complete literature review",
            position=1,
        )
        task_b.status = "in_progress"
        task_b.priority = "normal"
        task_b.is_milestone = 1
        task_b.notes = ""
        session.add(task_b)

        collection = Collection(
            key="project-study-1",
            title="Study One — documents",
            description="Documents associated with the project.",
            kind="project",
            project_id=project.id,
        )
        session.add(collection)
        session.flush()

        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            original_filename="paper.pdf",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
            storage_mode="managed_copy",
            processing_state="extracted",
            page_count=10,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentMetadata(
                document_id=document.id,
                title="A Study",
                year=2023,
                doi="10.1000/xyz",
            )
        )
        session.add(
            CollectionItem(
                collection_id=collection.id,
                item_type="document",
                item_identifier="doc-1",
                note="Primary reference.",
                position=0,
            )
        )


def _service(database: Database) -> ProjectExportService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return ProjectExportService(repositories)


def test_export_json_to_file(database: Database, tmp_path: Path) -> None:
    _seed(database)
    service = _service(database)
    output = tmp_path / "project.json"
    result = service.export("study-1", output)
    assert result.project_key == "study-1"
    assert result.format is ExportFormat.JSON
    assert result.bytes_written > 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"]["title"] == "Study One"
    assert payload["research_questions"]
    assert payload["tasks"]
    assert payload["milestones"]
    assert payload["collections"]
    assert payload["linked_documents"]


def test_export_markdown_to_file(database: Database, tmp_path: Path) -> None:
    _seed(database)
    service = _service(database)
    output = tmp_path / "project.md"
    result = service.export(
        "study-1",
        output,
        options=ExportOptions(format=ExportFormat.MARKDOWN),
    )
    assert result.format is ExportFormat.MARKDOWN
    text = output.read_text(encoding="utf-8")
    assert "# Study One" in text
    assert "## Research questions" in text
    assert "What is the effect?" in text
    assert "## Milestones" in text
    assert "Complete literature review" in text


def test_export_rejects_existing_file_without_overwrite(
    database: Database, tmp_path: Path
) -> None:
    _seed(database)
    service = _service(database)
    output = tmp_path / "project.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(ProjectExportError):
        service.export("study-1", output)


def test_export_overwrites_when_requested(
    database: Database, tmp_path: Path
) -> None:
    _seed(database)
    service = _service(database)
    output = tmp_path / "project.json"
    output.write_text("existing", encoding="utf-8")
    result = service.export("study-1", output, overwrite=True)
    assert result.bytes_written > 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"]["key"] == "study-1"


def test_export_unknown_project_raises(database: Database, tmp_path: Path) -> None:
    service = _service(database)
    with pytest.raises(ProjectExportNotFoundError):
        service.export("missing", tmp_path / "out.json")


def test_export_with_sections_filter(database: Database, tmp_path: Path) -> None:
    _seed(database)
    service = _service(database)
    output = tmp_path / "project.json"
    options = ExportOptions(
        format=ExportFormat.JSON,
        sections=frozenset(
            {ExportSection.PROJECT_FIELDS, ExportSection.RESEARCH_QUESTIONS}
        ),
    )
    service.export("study-1", output, options=options)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "project" in payload
    assert "research_questions" in payload
    assert "tasks" not in payload
    assert "milestones" not in payload
    assert "collections" not in payload
    assert "linked_documents" not in payload


def test_build_json(database: Database) -> None:
    _seed(database)
    service = _service(database)
    text = service.build_json("study-1")
    payload = json.loads(text)
    assert payload["project"]["key"] == "study-1"


def test_build_markdown(database: Database) -> None:
    _seed(database)
    service = _service(database)
    text = service.build_markdown("study-1")
    assert "# Study One" in text
    assert "## Linked documents" in text


def test_suggested_filename(database: Database) -> None:
    _seed(database)
    service = _service(database)
    assert service.suggested_filename("study-1", ExportFormat.JSON).endswith(".json")
    assert service.suggested_filename(
        "study-1", ExportFormat.MARKDOWN
    ).endswith(".md")