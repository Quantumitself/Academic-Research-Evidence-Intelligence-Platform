# 0003. Use SQLite with SQLAlchemy for persistence

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

The application stores research projects, documents metadata, annotations,
search sessions, evidence records, analysis runs, and settings. The desktop
product must operate entirely offline, support full-text search, and be
backup-friendly. A server database would introduce an installation and
operational burden that is inappropriate for a single-user desktop tool.

## Decision

SQLite is the persistence engine. Access goes through SQLAlchemy 2.x with an
explicit session lifecycle managed by the application bootstrap. Schema
evolution is handled by Alembic migrations. Full-text search uses SQLite
FTS5. Secrets and API credentials are stored outside SQLite, in the operating
system's secure credential store.

The presentation layer never issues SQL. Persistence is accessed exclusively
through repository classes that live in the infrastructure layer.

## Consequences

- The application runs entirely offline with no external service dependency.
- The database is a single file, which simplifies backup and recovery, and
  matches the product specification's requirement for a documented backup
  method.
- FTS5 provides adequate local full-text search without an external index
  service.
- Contributors must add migrations for schema changes; direct schema edits
  are prohibited.
- Concurrent multi-process writes are not supported, which is acceptable
  because the desktop application is single-user and single-process.

## Alternatives

- **PostgreSQL**: rejected because it requires an external service and would
  violate the offline-first requirement.
- **Raw sqlite3 module**: rejected because manual SQL increases the risk of
  schema drift and injection issues. SQLAlchemy provides typed access and
  migrations.
- **A document store such as MongoDB**: rejected because it requires an
  external service and provides no advantage for the relational data model
  the product requires.

## References

- Product specification, section 16 (Data Model and Persistence).