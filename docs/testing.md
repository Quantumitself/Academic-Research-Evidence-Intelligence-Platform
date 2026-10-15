# Testing

## Invocation

Tests are always invoked through the Python module form, not the bare
`pytest` executable:

python -m pytest -q
This guarantees that the active interpreter is the one running the tests,
that src is honored via the pythonpath setting in pyproject.toml, and
that the repository layout does not depend on the ambient shell PATH.

## Test categories

- `tests/unit/` — fast, deterministic tests with no external dependencies.
- `tests/integration/` — tests that exercise real adapters against mock
  servers or recorded fixtures.
- `tests/ui/` — tests that construct Qt widgets in an offscreen context.
  Marked with `@pytest.mark.ui`.
- `tests/scientific_validation/` — tests that verify statistical results
  against trusted reference values. Marked with
  `@pytest.mark.scientific`.
- `tests/fixtures/` — shared fixtures and recorded data used by the above.

## Markers

The following markers are declared in `pyproject.toml` and enforced with
`--strict-markers`:

- `integration` — requires external services or resources.
- `scientific` — validates statistical correctness against references.
- `ui` — constructs Qt widgets.

## Coverage

Coverage is collected with `python -m pytest --cov=academic_platform`. The
configuration omits `__init__.py` files and test modules from the report.
Branch coverage is enabled. Coverage thresholds are not enforced in CI yet;
they will be introduced once the initial feature set stabilizes.

## Conventions

- Every test module states its purpose in a module docstring.

- Fixtures prefer explicit setup over hidden autouse fixtures, except where
resetting process-wide state (for example logging configuration).

- Tests must not depend on network access unless they are marked
@pytest.mark.integration.

- Tests that construct Qt objects must run under the offscreen platform
plugin; the marker is applied at module scope.

- A failing test is a defect in the code or in the test; it is never silenced
with xfail without a documented reason and an issue reference.

## Phase A Verification

Two scripts form the Phase A acceptance harness:

- `scripts/capture_screenshots.py` — captures one PNG per primary
  destination into `docs/screenshots/phase_a/` and writes a manifest. Run
  with `--offscreen` in CI.
- `scripts/validate_phase_a.py` — runs the Phase A acceptance checks in a
  temporary home directory and optionally writes a JSON report.

Both scripts run under the offscreen Qt platform plugin and never touch
the user's data directory. The tests in
`tests/unit/test_phase_a_acceptance.py` mirror the acceptance criteria so
that a broken shell fails the standard test run before the scripts are
invoked.

## Phase B Verification

Two scripts form the Phase B acceptance harness:

- `scripts/validate_phase_b.py` — runs the persistence acceptance checks
  in a temporary directory and optionally writes a JSON report.
- `tests/unit/test_phase_b_acceptance.py` — mirrors the acceptance
  criteria as automated tests.

The validator uses a temporary database file and does not touch the
user's data. Run it with:

python scripts/validate_phase_b.py --report docs/phases/phase_b_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Migration-Head Convention

The head revision moves with every new migration. Tests must not
hard-code it. Tests that need the current head import EXPECTED_HEAD
from tests.unit._migration_head. Tests that name a specific revision
for a targeted operation (downgrade to an intermediate state, for
example) use the literal revision identifier, which is stable by
definition.

The convention is enforced by
tests/unit/test_migration_head_convention.py. The module scans every
test file for string literals matching the current head and fails when
one is found. Adding a new migration cannot break the existing suite, and
the anti-pattern cannot be reintroduced without failing the acceptance
tests.

## Phase C Verification

Two scripts form the Phase C acceptance harness:

- `scripts/validate_phase_c.py` — runs the discovery pipeline checks
  against deterministic stub adapters and a temporary database, and
  optionally writes a JSON report.
- `tests/unit/test_phase_c_acceptance.py` — mirrors the acceptance
  criteria as automated tests.

The validator does not contact a real provider. It registers stub
adapters with a private provider registry, configures sources through
the application service, and exercises the orchestrator, the
publication service, and the saved-search service end to end.

python scripts/validate_phase_c.py --report docs/phases/phase_c_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Phase D Verification

Two scripts form the Phase D acceptance harness:

- `scripts/validate_phase_d.py` — runs the library and reading pipeline
  checks against a temporary directory and an in-memory database, and
  optionally writes a JSON report.
- `tests/unit/test_phase_d_acceptance.py` — mirrors the acceptance
  criteria as automated tests.

The validator does not contact the network and does not touch the
user's data. It exercises the file storage abstraction, the import
coordinator, the PDF extractor, the metadata extractor, the OCR
gating, the FTS5 index, the library service, the reader service, the
annotation service, the in-document search service, the document
linking service, and the reader → assistant handoff, and it verifies
that persistence survives a database reopen.

python scripts/validate_phase_d.py --report docs/phases/phase_d_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Phase E Verification

Two scripts form the Phase E acceptance harness:

- `scripts/validate_phase_e.py` — runs the research project management
  pipeline checks against a temporary directory and an in-memory
  database, and optionally writes a JSON report.
- `tests/unit/test_phase_e_acceptance.py` — mirrors the acceptance
  criteria as automated tests.

The validator does not contact the network and does not touch the
user's data. It exercises the project CRUD service, the collection CRUD
service, smart collections, the task workflow service, the project
export service, and the audit trail. It verifies that persistence
survives a database reopen.


python scripts/validate_phase_e.py --report docs/phases/phase_e_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.