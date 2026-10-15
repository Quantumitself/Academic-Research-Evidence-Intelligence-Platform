# Academic Research & Evidence Intelligence Platform

A desktop-first academic research environment for literature discovery, reading,
research design, evidence extraction, statistical analysis, and traceable
reporting.

## Requirements

- Python 3.11 or newer
- Windows 10/11 (primary), Linux and macOS for development
- SQLite (bundled with Python)

## Installation

python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e ".[dev]"

The editable install exposes the academic-platform console entry point and
places the package on the interpreter's import path without relying on the
repository working directory.

## Running

academic-platform

or

python -m academic_platform

## Repository Layout

- src/academic_platform/ — application source

- docs/ — architecture, audit, dependency, integration, and ADR documentation

- scripts/ — operational scripts (audit, inventory, environment validation,
ADR tooling, development launcher)

- tests/ — automated tests

## Auditing the Repository
 
python scripts/audit_repository.py
python scripts/dependency_inventory.py
python scripts/validate_environment.py

Outputs are written into docs/.

## Architecture Decision Records

Decisions affecting module boundaries, dependencies, persistence, or the
validation strategy are recorded under docs/adr/. Use the ADR tool:

python scripts/adr.py index
python scripts/adr.py list
python scripts/adr.py show 0001
python scripts/adr.py search persistence
python scripts/adr.py validate
python scripts/adr.py new "Adopt structured logging for background tasks"

## Running Tests

Tests are executed as a module so that the repository layout is honored
without requiring an editable install:

python -m pytest -q
python -m pytest -q tests/unit

## Code Quality

python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy src

## Phase A Verification

Regenerate the visual verification record:

python scripts/capture_screenshots.py --offscreen
Validate every Phase A acceptance criterion:

python scripts/validate_phase_a.py --report docs/phases/phase_a_validation.json

The validation report is written as JSON and is safe to archive as
acceptance evidence.

/* --- UPDATE: README.md — document migration tooling --- */

## Database Migrations

Migrations run automatically at application startup. The command-line
tool exposes the same operations for diagnostics:

python scripts/migrate.py upgrade
python scripts/migrate.py current
python scripts/migrate.py head
python scripts/migrate.py downgrade base

## License

Proprietary. See repository policy documentation.