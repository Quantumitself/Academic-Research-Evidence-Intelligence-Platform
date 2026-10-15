# Phase B Acceptance

This document records the acceptance evidence for Phase B: the
persistence layer, the repository pattern, and the schema boundary.

## Scope of Phase B

- Database engine and session management.
- Alembic migration baseline and the migration runner.
- Core entity schemas: user profile, app settings, audit event.
- Repository pattern foundation.
- Settings persistence wiring.
- Project and collection models.
- Document asset models.
- Search source and search session models.
- AI provider and model configuration models.
- Evidence and analysis models.
- Knowledge, guide, achievement, and research-plan models.

## Acceptance criteria

A criterion is satisfied when the corresponding automated test passes and
the validator reports success.

| # | Criterion | Verification |
| --- | --- | --- |
| 1 | The migration head is discoverable without a database URL. | `test_migration_head_convention.py::test_expected_head_is_a_string` |
| 2 | Migrations run from an empty database to the head and are idempotent. | `test_phase_b_acceptance.py::test_upgrade_from_empty_reaches_head`, `::test_upgrade_is_idempotent` |
| 3 | Downgrade to `base` reverts every migration cleanly. | `test_phase_b_acceptance.py::test_downgrade_to_base_then_re_upgrade` |
| 4 | Every table registered on `Base.metadata` is present after upgrade. | `test_phase_b_acceptance.py::test_every_registered_table_exists_after_upgrade` |
| 5 | Every repository registered with the factory constructs against a live session. | `test_phase_b_acceptance.py::test_repositories_construct_against_live_session` |
| 6 | Every Pydantic schema in the persistence schemas package is importable. | `test_phase_b_acceptance.py::test_every_exported_schema_is_importable` |
| 7 | Round-trip persistence survives a session close and reload. | `test_phase_b_acceptance.py::test_round_trip_survives_session_close` |
| 8 | Foreign-key cascade behaviour matches the schema declaration. | `test_phase_b_acceptance.py::test_cascade_delete_of_research_project` |
| 9 | Append-only contracts are enforced by the audit repository. | `test_phase_b_acceptance.py::test_append_only_contract_for_audit_events` |
| 10 | No test hard-codes the current head revision as a literal. | `test_migration_head_convention.py::test_no_test_hard_codes_current_head_as_literal` |
| 11 | The full acceptance validator passes end to end. | `test_validate_phase_b_script.py::test_full_validation_passes` |

## Automated acceptance

The Phase B validator is `scripts/validate_phase_b.py`. It runs every
acceptance check in a temporary directory, prints a per-check report, and
writes a JSON document when `--report` is supplied.

python scripts/validate_phase_b.py --report docs/phases/phase_b_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Migration-head convention

The head revision moves with every new migration. Tests must not
hard-code it. Tests that need the current head import EXPECTED_HEAD
from tests.unit._migration_head. Tests that name a specific revision
for a targeted operation (downgrade to an intermediate state, for
example) use the literal revision identifier, which is stable by
definition.

The migration-head convention is enforced by
tests/unit/test_migration_head_convention.py, which scans every test
file for string literals matching the current head and fails when one is
found. This makes the convention self-enforcing: adding a new migration
cannot break the existing suite, and a future contributor cannot
reintroduce the anti-pattern without failing the acceptance tests.

## Known limitations

- The database does not yet provide full-text search indices. FTS5 is
introduced in a later phase, when the library reader is implemented.

- Provider-level credential storage is deferred to the AI provider
implementation phase. The schema records the reference; the keyring
integration is delivered alongside the provider adapters.

- Smart-collection filter evaluation is deferred to the collections
page implementation phase. The schema stores the filter; the
evaluation is performed by the application layer.

- Audit events are stored but not yet surfaced in the UI. The activity
feed on the dashboard consumes UserActivity records; audit events
are consumed by support diagnostics.

## Files added or changed in Phase B

Phase B added or changed the following groups of files:

- src/academic_platform/infrastructure/database/ — engine, base,
migrations, models, schemas.

- src/academic_platform/infrastructure/repositories/ — base,
specifications, manager, factory, and one repository module per entity.

- migrations/versions/ — revisions 0001 through 0008.

- src/academic_platform/app/bootstrap.py — database open, migration
run, settings reconciliation.

- src/academic_platform/application/settings_persistence.py — bridge
between the file-backed settings and the database.

- scripts/migrate.py — migration command-line tool.

- scripts/validate_phase_b.py — Phase B validator.

- tests/unit/ — one test module per model, schema, repository, and
migration, plus the acceptance modules.

- tests/unit/_migration_head.py — single source of truth for the head.

- docs/architecture.md, docs/code_style.md, docs/security.md,
docs/testing.md, docs/phases/phase_b_acceptance.md.