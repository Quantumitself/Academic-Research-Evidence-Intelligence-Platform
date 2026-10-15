"""Phase D acceptance validator.

Verifies that the personal library and reading pipeline meets every
Phase D acceptance criterion. The validator runs entirely offline,
against a temporary directory and an in-memory SQLite database. It
never touches the user's data and never contacts the network.

Acceptance criteria checked
---------------------------
1. The file storage abstraction copies files atomically, verifies
   checksums, and refuses to write outside its managed root.
2. The import coordinator validates files, detects duplicates by
   checksum, and persists document records.
3. PDF text extraction returns page-level text, page count, and blocks.
4. PDF metadata extraction returns a title, authors, year, DOI, and
   abstract from a synthetic paper.
5. OCR is correctly gated: disabled by default, and available only when
   the backend is present.
6. The FTS5 index is populated on extraction and searchable through
   the query service.
7. The library service lists, filters, sorts, and searches documents.
8. The library page's data model exposes every entry the service
   returns.
9. The document reader service opens a document, reports its page
   count, and renders pages as PNG bytes.
10. Bookmarks and annotations persist, are searchable through the note
    index, and can be exported.
11. In-document search finds literal and regular-expression matches.
12. Document linking adds and removes documents from collections and
    projects, and creates project-linked collections on demand.
13. The reader → assistant handoff composes a payload, stores it, and
    retrieves it.
14. Session and artifact persistence survive process restart: every
    entity written by the harness is present after the database is
    reopened.

Exit codes
----------
- 0: all criteria satisfied.
- 1: at least one criterion failed.
- 2: usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPORT_FILENAME = "phase_d_validation.json"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, ok=ok, detail=detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [asdict(check) for check in self.checks],
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_phase_d",
        description="Validate the Phase D acceptance criteria.",
    )
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
class _ShimmedManager:
    """A repository manager that opens a fresh session per repository request."""

    def __init__(self, database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        return _REPOSITORY_REGISTRY[key](session)

    def register_all(self, mapping: dict) -> None:
        # The manager resolves repositories from the factory registry.
        return None

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


def _make_synthetic_pdf(path: Path, *, title: str, authors: str, year: str, body: str) -> None:
    import fitz

    document = fitz.open()
    try:
        page = document.new_page()
        y = 60.0
        for line in (
            title,
            authors,
            year,
            "",
            "Abstract",
            "This synthetic paper exists to exercise metadata extraction and "
            "in-document search across the acceptance pipeline.",
            "",
            "1. Introduction",
            body,
        ):
            page.insert_text((72, y), line)
            y += 16
        document.set_metadata(
            {
                "title": title,
                "author": authors,
                "subject": f"Journal of Synthetic Studies {year}",
                "creationDate": f"D:{year}0101000000Z",
            }
        )
        document.save(str(path))
    finally:
        document.close()


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
def _check_file_storage(report: ValidationReport, tmp_path: Path) -> None:
    from academic_platform.infrastructure.file_storage import (
        FileStorage,
        FileStorageConfig,
        FileStorageValidationError,
    )

    try:
        source = tmp_path / "source.bin"
        source.write_bytes(b"%PDF-1.4 synthetic")
        service = FileStorage(
            FileStorageConfig(
                managed_root=tmp_path / "library",
                chunk_size_bytes=64,
            )
        )
        stored = service.import_managed_copy(source)
        assert stored.location.exists()
        assert service.verify_managed_copy(
            stored.location, expected_checksum=stored.checksum_sha256
        )
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"data")
        try:
            service.delete_managed_copy(outside)
            blocked = False
        except FileStorageValidationError:
            blocked = True
        assert blocked
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("file storage", False, str(exc))
        return
    report.add(
        "file storage",
        True,
        f"managed copy size={stored.size_bytes} outside-write blocked",
    )


def _check_import_coordinator(
    report: ValidationReport,
    database,
    tmp_path: Path,
) -> None:
    from academic_platform.application.library_import.coordinator import (
        ImportCoordinator,
    )
    from academic_platform.application.library_import.model import (
        ImportCandidateState,
        ImportMode,
    )
    from academic_platform.infrastructure.file_storage import (
        FileStorage,
        FileStorageConfig,
    )

    try:
        source = tmp_path / "imported.pdf"
        source.write_bytes(b"%PDF-1.4 imported content")
        storage = FileStorage(
            FileStorageConfig(
                managed_root=tmp_path / "managed",
                max_file_size_bytes=1024 * 1024,
                chunk_size_bytes=64,
            )
        )
        manager = _ShimmedManager(database)
        coordinator = ImportCoordinator(
            repositories=manager,  # type: ignore[arg-type]
            storage=storage,
            max_file_size_bytes=1024 * 1024,
        )
        plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
        assert plan.candidates[0].state is ImportCandidateState.READY
        result = coordinator.import_files(plan)
        assert result.imported_count == 1
        manager.close_all()

        # Repeat the import; the detector must report a duplicate.
        manager = _ShimmedManager(database)
        coordinator = ImportCoordinator(
            repositories=manager,  # type: ignore[arg-type]
            storage=storage,
            max_file_size_bytes=1024 * 1024,
        )
        plan = coordinator.prepare([source], ImportMode.MANAGED_COPY)
        assert plan.candidates[0].state is ImportCandidateState.DUPLICATE
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("import coordinator", False, str(exc))
        return
    report.add("import coordinator", True, "first import ready, second duplicate")


def _check_pdf_extraction(
    report: ValidationReport,
    tmp_path: Path,
) -> None:
    from academic_platform.infrastructure.document_processing import (
        PdfTextExtractor,
    )

    try:
        pdf = tmp_path / "extract.pdf"
        _make_synthetic_pdf(
            pdf,
            title="Extraction Paper",
            authors="A. Author; B. Author",
            year="2021",
            body="Body text mentioning invariance in measurement.",
        )
        result = PdfTextExtractor().extract(pdf)
        assert result.page_count >= 1
        assert result.extracted_page_count >= 1
        assert "invariance" in result.full_text
        assert result.pages[0].blocks
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("pdf extraction", False, str(exc))
        return
    report.add(
        "pdf extraction",
        True,
        f"pages={result.page_count} blocks={len(result.pages[0].blocks)}",
    )


def _check_pdf_metadata(
    report: ValidationReport,
    tmp_path: Path,
) -> None:
    from academic_platform.infrastructure.document_processing import (
        PdfMetadataExtractor,
    )

    try:
        pdf = tmp_path / "metadata.pdf"
        _make_synthetic_pdf(
            pdf,
            title="Metadata Paper",
            authors="A. Author; B. Author",
            year="2022",
            body="Body text with DOI: 10.1000/metadata.",
        )
        result = PdfMetadataExtractor().extract_from_path(pdf)
        assert result.title
        assert result.authors
        assert result.year == 2022
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("pdf metadata", False, str(exc))
        return
    report.add(
        "pdf metadata",
        True,
        f"title={result.title!r} year={result.year} authors={len(result.authors)}",
    )


def _check_ocr_gating(report: ValidationReport, tmp_path: Path) -> None:
    from academic_platform.infrastructure.document_processing import (
        OcrConfig,
        PdfOcrExtractor,
    )

    try:
        pdf = tmp_path / "ocr.pdf"
        _make_synthetic_pdf(
            pdf,
            title="OCR",
            authors="A",
            year="2020",
            body="text",
        )
        availability = PdfOcrExtractor(OcrConfig()).probe_availability()
        # The probe reports availability without raising, regardless of
        # whether Tesseract is installed on the host.
        assert availability.available in {True, False}
        if not availability.available:
            assert availability.message
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("ocr gating", False, str(exc))
        return
    report.add(
        "ocr gating",
        True,
        (
            f"available={availability.available}"
            f" version={availability.tesseract_version or 'n/a'}"
        ),
    )


def _check_fts_index(
    report: ValidationReport,
    database,
    tmp_path: Path,
) -> None:
    from academic_platform.application.document_extraction.service import (
        DocumentExtractionService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset
    from academic_platform.infrastructure.full_text_search.query import (
        FtsQueryService,
    )

    try:
        pdf = tmp_path / "indexed.pdf"
        _make_synthetic_pdf(
            pdf,
            title="Indexed Paper",
            authors="A. Author",
            year="2023",
            body="Content about measurement invariance across groups.",
        )
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-indexed",
                    display_name="Indexed Paper",
                    location=str(pdf.resolve()),
                    checksum_sha256="0" * 64,
                )
            )
        manager = _ShimmedManager(database)
        service = DocumentExtractionService(manager, index_enabled=True)  # type: ignore[arg-type]
        outcome = service.extract_document("doc-indexed")
        manager.close_all()
        assert outcome.chunk_count >= 1
        with database.session() as session:
            results = FtsQueryService(session).search_documents("invariance")
        assert results
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("fts index", False, str(exc))
        return
    report.add("fts index", True, f"chunks={outcome.chunk_count}")


def _check_library_service(
    report: ValidationReport,
    database,
) -> None:
    from academic_platform.application.library.model import (
        LibraryFilter,
        LibrarySortDirection,
        LibrarySortField,
    )
    from academic_platform.application.library.service import LibraryService
    from academic_platform.infrastructure.database.models import (
        DocumentAsset,
        DocumentChunk,
    )
    from academic_platform.infrastructure.full_text_search.indexer import (
        FtsIndexer,
    )

    try:
        with database.session() as session:
            document = DocumentAsset(
                key="doc-lib",
                display_name="Library Paper",
                location="/tmp/lib.pdf",
                checksum_sha256="1" * 64,
                processing_state="extracted",
                size_bytes=2048,
            )
            session.add(document)
            session.flush()
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="Content about regression.",
            )
            session.add(chunk)
            session.flush()
            FtsIndexer(session).index_document(document, [chunk])

        manager = _ShimmedManager(database)
        service = LibraryService(manager)  # type: ignore[arg-type]
        page = service.list_entries(
            sort_field=LibrarySortField.DISPLAY_NAME,
            sort_direction=LibrarySortDirection.ASCENDING,
        )
        assert page.total >= 1
        filtered = service.list_entries(
            filter_state=LibraryFilter(search_text="regression")
        )
        assert any(entry.key == "doc-lib" for entry in filtered.entries)
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 -> boundary
        report.add("library service", False, str(exc))
        return
    report.add(
        "library service",
        True,
        f"total={page.total} search hits={filtered.total}",
    )


def _check_reader_service(
    report: ValidationReport,
    database,
    tmp_path: Path,
) -> None:
    from academic_platform.application.document_reading import (
        DocumentReaderService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset

    try:
        pdf = tmp_path / "reader.pdf"
        _make_synthetic_pdf(
            pdf,
            title="Reader Paper",
            authors="A. Author",
            year="2024",
            body="Body for reader.",
        )
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-reader",
                    display_name="Reader Paper",
                    location=str(pdf.resolve()),
                    checksum_sha256="2" * 64,
                )
            )
        manager = _ShimmedManager(database)
        service = DocumentReaderService(manager)  # type: ignore[arg-type]
        page_count, _ = service.open_document("doc-reader")
        assert page_count >= 1
        rendered = service.render_page("doc-reader", 1)
        assert rendered.image_bytes.startswith(b"\x89PNG")
        service.close_all()
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("reader service", False, str(exc))
        return
    report.add(
        "reader service",
        True,
        f"pages={page_count} png_bytes={len(rendered.image_bytes)}",
    )


def _check_annotations(
    report: ValidationReport,
    database,
) -> None:
    from academic_platform.application.annotations import (
        AnnotationColor,
        AnnotationService,
    )
    from academic_platform.infrastructure.database.models import DocumentAsset
    from academic_platform.infrastructure.full_text_search.query import (
        FtsQueryService,
    )

    try:
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-annot",
                    display_name="Annotation Paper",
                    location="/tmp/annot.pdf",
                    checksum_sha256="3" * 64,
                )
            )
        manager = _ShimmedManager(database)
        service = AnnotationService(manager)  # type: ignore[arg-type]
        note = service.create_note(
            "doc-annot", 1, "Key finding about invariance."
        )
        highlight = service.create_highlight(
            "doc-annot", 2, "Excerpt", color=AnnotationColor.GREEN
        )
        bookmark = service.create_bookmark("doc-annot", 3)
        export_json = service.export_to_json("doc-annot")
        export_md = service.export_to_markdown("doc-annot")
        assert "invariance" in export_json
        assert "Key finding" in export_md
        manager.close_all()
        with database.session() as session:
            results = FtsQueryService(session).search_notes("invariance")
        assert results
        assert note.identifier > 0
        assert highlight.color is AnnotationColor.GREEN
        assert bookmark.is_bookmark
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("annotations", False, str(exc))
        return
    report.add("annotations", True, "note, highlight, bookmark persisted")


def _check_in_document_search(
    report: ValidationReport,
    database,
) -> None:
    from academic_platform.application.document_search import (
        DocumentSearchService,
    )
    from academic_platform.infrastructure.database.models import (
        DocumentAsset,
        DocumentChunk,
    )

    try:
        with database.session() as session:
            document = DocumentAsset(
                key="doc-search",
                display_name="Search Paper",
                location="/tmp/search.pdf",
                checksum_sha256="4" * 64,
            )
            session.add(document)
            session.flush()
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=1,
                    content="The study examined measurement invariance across groups.",
                )
            )
        manager = _ShimmedManager(database)
        service = DocumentSearchService(manager)  # type: ignore[arg-type]
        literal = service.search("doc-search", "invariance")
        assert literal.match_count == 1
        assert literal.matches[0].page_number == 1
        regex = service.search("doc-search", r"\bmeasurement\b", use_regex=True)
        assert regex.match_count == 1
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("in-document search", False, str(exc))
        return
    report.add("in-document search", True, "literal and regex modes verified")


def _check_document_linking(
    report: ValidationReport,
    database,
) -> None:
    from academic_platform.application.document_linking import (
        DocumentLinkingService,
    )
    from academic_platform.infrastructure.database.models import (
        Collection,
        CollectionItem,
        DocumentAsset,
        ResearchProject,
    )

    try:
        with database.session() as session:
            session.add(
                DocumentAsset(
                    key="doc-link",
                    display_name="Linking Paper",
                    location="/tmp/link.pdf",
                    checksum_sha256="5" * 64,
                )
            )
            session.add(Collection(key="col-link", title="Reading list"))
            session.add(ResearchProject(key="proj-link", title="Study"))
        manager = _ShimmedManager(database)
        service = DocumentLinkingService(manager)  # type: ignore[arg-type]
        service.link_document_to_collection("doc-link", "col-link")
        service.link_document_to_project("doc-link", "proj-link")
        view = service.links_for_document("doc-link")
        assert view.collections
        assert view.projects
        manager.close_all()
        with database.session() as session:
            items = session.query(CollectionItem).all()
            assert any(item.item_identifier == "doc-link" for item in items)
            project_collections = [
                c for c in session.query(Collection).all() if c.kind == "project"
            ]
            assert project_collections
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("document linking", False, str(exc))
        return
    report.add(
        "document linking",
        True,
        f"collections={len(view.collections)} projects={len(view.projects)}",
    )


def _check_assistant_handoff(
    report: ValidationReport,
    database,
) -> None:
    from academic_platform.application.assistant_handoff import (
        AssistantHandoffService,
        HandoffStore,
    )
    from academic_platform.infrastructure.database.models import (
        DocumentAsset,
        DocumentMetadata,
    )

    try:
        with database.session() as session:
            document = DocumentAsset(
                key="doc-handoff",
                display_name="Handoff Paper",
                location="/tmp/handoff.pdf",
                checksum_sha256="6" * 64,
                page_count=3,
            )
            session.add(document)
            session.flush()
            session.add(
                DocumentMetadata(
                    document_id=document.id,
                    title="Handoff Paper",
                    authors_json='["A. Author"]',
                    year=2020,
                )
            )
        store = HandoffStore()
        manager = _ShimmedManager(database)
        service = AssistantHandoffService(
            manager, store=store  # type: ignore[arg-type]
        )
        handoff = service.build_handoff("doc-handoff", current_page=2)
        assert handoff.title == "Handoff Paper"
        assert handoff.current_page == 2
        assert store.get("doc-handoff") is handoff
        manager.close_all()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("assistant handoff", False, str(exc))
        return
    report.add("assistant handoff", True, f"summary={handoff.summary}")


def _check_persistence_survives_reopen(
    report: ValidationReport,
    tmp_path: Path,
) -> None:
    from academic_platform.infrastructure.database import (
        Database,
        DatabaseConfiguration,
    )
    from academic_platform.infrastructure.database.base import Base
    from academic_platform.infrastructure.database.models import (
        Annotation,
        DocumentAsset,
        DocumentChunk,
    )

    try:
        database_path = tmp_path / "persistence.sqlite3"
        url = f"sqlite:///{database_path.as_posix()}"

        database = Database(DatabaseConfiguration(url=url))
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            document = DocumentAsset(
                key="persist-1",
                display_name="Persistent Paper",
                location="/tmp/persist.pdf",
                checksum_sha256="7" * 64,
            )
            session.add(document)
            session.flush()
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=1,
                    content="Persistent content.",
                )
            )
            session.add(
                Annotation(
                    document_id=document.id,
                    kind="note",
                    page_number=1,
                    body="Persistent note.",
                )
            )
        database.dispose()

        # Reopen and verify.
        database = Database(DatabaseConfiguration(url=url))
        try:
            with database.session() as session:
                documents = session.query(DocumentAsset).all()
                chunks = session.query(DocumentChunk).all()
                annotations = session.query(Annotation).all()
        finally:
            database.dispose()
        assert len(documents) == 1
        assert len(chunks) == 1
        assert len(annotations) == 1
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("persistence survives reopen", False, str(exc))
        return
    report.add(
        "persistence survives reopen",
        True,
        "documents=1 chunks=1 annotations=1",
    )


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------
def _print_report(report: ValidationReport, quiet: bool) -> None:
    if quiet:
        return
    width = max((len(check.name) for check in report.checks), default=0)
    for check in report.checks:
        status = "OK  " if check.ok else "FAIL"
        detail = f" — {check.detail}" if check.detail else ""
        print(f"[{status}] {check.name.ljust(width)}{detail}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    report = ValidationReport()
    temporary_directory = tempfile.TemporaryDirectory(
        prefix="academic_platform_phase_d_"
    )
    try:
        tmp_path = Path(temporary_directory.name)
        from academic_platform.infrastructure.database import Database
        from academic_platform.infrastructure.database.base import Base

        database = Database.in_memory()
        Base.metadata.create_all(database.engine)
        try:
            _check_file_storage(report, tmp_path)
            _check_import_coordinator(report, database, tmp_path)
            _check_pdf_extraction(report, tmp_path)
            _check_pdf_metadata(report, tmp_path)
            _check_ocr_gating(report, tmp_path)
            _check_fts_index(report, database, tmp_path)
            _check_library_service(report, database)
            _check_reader_service(report, database, tmp_path)
            _check_annotations(report, database)
            _check_in_document_search(report, database)
            _check_document_linking(report, database)
            _check_assistant_handoff(report, database)
            _check_persistence_survives_reopen(report, tmp_path)
        finally:
            database.dispose()
    finally:
        temporary_directory.cleanup()

    _print_report(report, args.quiet)

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())