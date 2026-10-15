# Phase D Acceptance

This document records the acceptance evidence for Phase D: the personal
library, document import, PDF extraction, OCR, full-text indexing, the
library page, the reader, annotations, in-document search, document
linking, and the reader → assistant handoff.

## Scope of Phase D

- File storage abstraction.
- File picker and import dialog.
- PDF text extraction (PyMuPDF).
- PDF metadata extraction from embedded metadata and front matter.
- Optional OCR integration.
- FTS5 full-text indexing.
- Library page.
- Document reader shell.
- Bookmarks and annotations.
- In-document search.
- Reader ↔ collection/project linking.
- Reader → research assistant handoff (stub).

## Acceptance criteria

A criterion is satisfied when the corresponding automated test passes
and the validator reports success.

| # | Criterion | Verification |
| --- | --- | --- |
| 1 | File storage copies files atomically, verifies checksums, and refuses writes outside the managed root. | `test_validate_phase_d_script.py::test_full_validation_passes` |
| 2 | The import coordinator validates files, detects duplicates, and persists document records. | `test_phase_d_acceptance.py::test_import_persists_document` |
| 3 | PDF text extraction returns page-level text, page count, and blocks. | `test_phase_d_acceptance.py::test_extraction_indexes_and_searches` |
| 4 | PDF metadata extraction returns a title, authors, and year from a synthetic paper. | `test_validate_phase_d_script.py::test_all_checks_pass_individually` |
| 5 | OCR is correctly gated by availability. | `test_validate_phase_d_script.py::test_full_validation_passes` |
| 6 | The FTS5 index is populated on extraction and searchable. | `test_phase_d_acceptance.py::test_extraction_indexes_and_searches` |
| 7 | The library service lists, filters, and searches documents. | `test_library_service.py` |
| 8 | The library page's data model exposes every entry the service returns. | `test_library_page.py` |
| 9 | The reader service opens a document and renders pages as PNG bytes. | `test_phase_d_acceptance.py::test_reader_renders_pages` |
| 10 | Annotations persist, are searchable, and can be exported. | `test_phase_d_acceptance.py::test_annotation_round_trip` |
| 11 | In-document search finds literal and regex matches. | `test_phase_d_acceptance.py::test_in_document_search_literal` |
| 12 | Document linking adds and removes documents from collections and projects. | `test_phase_d_acceptance.py::test_document_linking` |
| 13 | The reader → assistant handoff composes and stores a payload. | `test_phase_d_acceptance.py::test_assistant_handoff_round_trip` |
| 14 | Persistence survives a database reopen. | `test_phase_d_acceptance.py::test_persistence_survives_reopen` |

## Automated acceptance

The Phase D validator is `scripts/validate_phase_d.py`. It runs every
acceptance check against a temporary directory and an in-memory
database, prints a per-check report, and writes a JSON document when
`--report` is supplied.

python scripts/validate_phase_d.py --report docs/phases/phase_d_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Known limitations

- The reader → assistant handoff stores payloads in an in-process
store. Persistence is delivered when the assistant destination is
implemented.

- OCR is optional and gated by a library setting. When Tesseract is not
installed on the host, OCR is reported as unavailable and the
extraction service records the failure state without failing the
extraction.

- The reader renders one page at a time. A background render pipeline
is delivered in a later phase if needed.

- In-document search operates on the extracted text, not on the PDF's
rendered content. A page that failed extraction will not produce
matches.

- Document linking to a project is implemented through a project-linked
collection. The relationship is visible in the collections view.

## Files added or changed in Phase D

- src/academic_platform/infrastructure/file_storage/.

- src/academic_platform/infrastructure/document_processing/.

- src/academic_platform/infrastructure/full_text_search/.

- src/academic_platform/infrastructure/database/models/fts.py.

- src/academic_platform/application/library_import/.

- src/academic_platform/application/document_extraction/.

- src/academic_platform/application/library/.

- src/academic_platform/application/document_reading/.

- src/academic_platform/application/annotations/.

- src/academic_platform/application/document_search/.

- src/academic_platform/application/document_linking/.

- src/academic_platform/application/assistant_handoff/.

- src/academic_platform/ui/dialogs/import_dialog.py.

- src/academic_platform/ui/dialogs/link_document_dialog.py.

- src/academic_platform/ui/dialogs/assistant_handoff_dialog.py.

- src/academic_platform/ui/pages/library/.

- src/academic_platform/ui/pages/reader/.

- scripts/validate_phase_d.py.