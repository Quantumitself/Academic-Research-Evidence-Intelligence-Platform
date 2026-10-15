# Phase E Acceptance

This document records the acceptance evidence for Phase E: research
project management, collections, smart collections, research tasks and
milestones, and basic project export.

## Scope of Phase E

- Research project CRUD service.
- Projects page.
- Collection CRUD service.
- Collections page.
- Smart collections.
- Research tasks and milestones.
- Basic project export.

## Acceptance criteria

A criterion is satisfied when the corresponding automated test passes
and the validator reports success.

| # | Criterion | Verification |
| --- | --- | --- |
| 1 | The project service creates, reads, updates, and deletes projects and manages their research questions. | `test_phase_e_acceptance.py::test_project_full_lifecycle` |
| 2 | The project service manages tasks through its task operations. | `test_project_service.py` |
| 3 | The project service creates and synchronizes the project-linked collection. | `test_phase_e_acceptance.py::test_project_full_lifecycle` |
| 4 | The collection service creates, reads, updates, deletes, and lists collections. | `test_collection_service.py` |
| 5 | The collection service manages items: add, remove, reorder, and note updates. | `test_phase_e_acceptance.py::test_collection_full_lifecycle` |
| 6 | The collection service enforces the collection kind and the project-link invariant. | `test_collection_service.py` |
| 7 | Smart collections parse their filter payload, reject malformed payloads, and evaluate correctly against the library. | `test_phase_e_acceptance.py::test_smart_collection_end_to_end` |
| 8 | The task service manages task status, priority, and milestones. | `test_phase_e_acceptance.py::test_task_workflow_end_to_end` |
| 9 | The task service computes progress summaries with overdue detection. | `test_phase_e_acceptance.py::test_task_overdue_detection` |
| 10 | The project export service writes JSON and Markdown documents with independent selectable sections. | `test_phase_e_acceptance.py::test_project_export_round_trip` |
| 11 | The project export service refuses to overwrite an existing file unless the caller requests it. | `test_project_export_service.py::test_export_rejects_existing_file_without_overwrite` |
| 12 | Audit events are recorded for every project, collection, and task mutation. | `test_phase_e_acceptance.py::test_audit_trail_spanning_services` |
| 13 | Persistence survives a database reopen. | `test_phase_e_acceptance.py::test_persistence_round_trip` |

## Automated acceptance

The Phase E validator is `scripts/validate_phase_e.py`. It runs every
acceptance check against a temporary directory and an in-memory
database, prints a per-check report, and writes a JSON document when
`--report` is supplied.

python scripts/validate_phase_e.py --report docs/phases/phase_e_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Known limitations

- The task status column is added by migration
0010_task_workflow_columns. Projects created before the migration
are backfilled from the legacy completed flag; tasks with a
non-boolean completion state that predates the migration cannot be
recovered exactly.

- Smart collections evaluate a bounded set of filter fields. Additional
fields require an extension to the filter model and to the evaluator.

- The project export includes references to linked documents but not
their content. Document files are not embedded.

- The projects page hosts the milestones panel as a third tab; a
dedicated milestone view is delivered in a later phase if needed.

- Task assignments and cross-project task views are out of scope at
this stage.

## Files added or changed in Phase E

- src/academic_platform/application/projects/.

- src/academic_platform/application/collections/.

- src/academic_platform/application/smart_collections/.

- src/academic_platform/application/tasks/.

- src/academic_platform/application/project_export/.

- src/academic_platform/ui/pages/projects/.

- src/academic_platform/ui/pages/collections/.

- src/academic_platform/ui/dialogs/project_export_dialog.py.

- src/academic_platform/infrastructure/database/models/research_plan.py
(workflow columns added to ResearchTask).

- migrations/versions/0010_task_workflow_columns.py.

- scripts/validate_phase_e.py.