# Architecture

## Overview

The application is a modular monolith written in Python. The desktop
application and the optional external API layer share the same domain and
application services. There are no independently deployed microservices.

## Layers

1. **Presentation** (`academic_platform.ui`): PySide6 widgets, pages, dialogs,
   and view models. No SQL, no provider-specific HTTP, no statistical
   formulas.
2. **Application** (`academic_platform.application`): use cases that coordinate
   domain logic and infrastructure.
3. **Domain** (`academic_platform.domain`): core concepts and rules that are
   independent of Qt, HTTP clients, file dialogs, and AI vendors.
4. **Infrastructure** (`academic_platform.infrastructure`): adapters for
   persistence, file storage, search providers, AI providers, statistical
   libraries, and credential storage.
5. **API** (`academic_platform.api`): the optional external REST surface,
   versioned under `/api/v1/`.
6. **Platform** (`academic_platform.platform`): platform-specific services.

## Rules

- Domain modules must not import from `ui`, `api`, or platform modules.
- Application services may import domain and infrastructure interfaces, but
  not concrete provider implementations beyond registered adapters.
- The presentation layer must not execute SQL directly.
- Statistical calculations live exclusively in the statistical engine.
- AI providers never produce statistical outputs.

## Runtime directories

Resolved once at startup by `academic_platform.app.configuration`. On Windows
the config directory is `%APPDATA%\AcademicResearchPlatform\config` and the
data directory is `%APPDATA%\AcademicResearchPlatform\data`. The environment
variable `ACADEMIC_PLATFORM_HOME` relocates the entire tree.

## Logging

Configured once by `academic_platform.app.logging_setup`. A rotating file
handler is installed alongside a console handler. Third-party libraries that
emit verbose logs are pinned to WARNING unless the application itself runs at
DEBUG.

## Architecture Decision Records

Decisions that affect module boundaries, dependency choices, persistence, or
the validation strategy are recorded as Architecture Decision Records under
`docs/adr/`. The index is regenerated with:

python scripts/adr.py index

The tool also supports listing, searching, validating, and creating ADRs:

python scripts/adr.py list
python scripts/adr.py show 0001
python scripts/adr.py search persistence
python scripts/adr.py validate
python scripts/adr.py new "Adopt structured logging for background tasks"

An ADR that fails to parse causes the index command to exit non-zero, which
allows CI to fail when a record is malformed. New ADRs must use the template
at docs/adr/TEMPLATE.md.

## Build and Packaging

The project uses a `src/` layout with setuptools as the build backend. The
authoritative configuration is `pyproject.toml`.

- Package discovery is restricted to `academic_platform*` under `src/`.
- Package data includes the UI resource tree (stylesheets, icons, fonts)
  so that packaged builds contain the same assets as a source checkout.
- A single console script, `academic-platform`, is exposed and dispatches to
  `academic_platform.main:main`.
- Tests are configured with `pythonpath = ["src"]` so that invoking
  `python -m pytest` from the repository root works without an editable
  install.
- Ruff, mypy, and pytest configurations are declared in the same file so
  that CI and local runs use identical settings.

### Import-path bootstrap

`academic_platform.main` inserts the `src` directory onto `sys.path` only
when the module is executed as `__main__` and `__package__` is empty. This
allows `python src/academic_platform/main.py` and
`python -m academic_platform` to work from a source checkout without
polluting the environment after an editable install.

## Settings Service

The persistent application configuration lives in
`<config_dir>/config.toml`. It is managed by
`academic_platform.app.settings.SettingsService`. The service:

- Creates the file with schema defaults on first run.
- Validates every load against `SettingsSchema`, a Pydantic v2 model.
- Rejects unknown fields and sections (`extra="forbid"`).
- Records a `schema_version` integer on disk.
- Migrates older schema versions to the current version before validation.
- Refuses to load files written by a newer application version.
- Persists changes atomically: a temporary file in the same directory is
  written, fsynced, and renamed over the target. The previous file is
  retained as `config.toml.bak`.
- Notifies registered observers after each successful save. Observers are
  isolated: a raising observer does not prevent other observers from being
  notified.

The service never stores secrets. Credentials live in the operating system
keyring and are referenced from settings by identifier only.

The `MainWindow` subscribes to settings changes and re-applies the
stylesheet when appearance settings change. No other component reads the
configuration file directly; all access goes through the service.

### Diagnostics

The `--settings` command-line flag prints the resolved configuration path
and the effective configuration as JSON and exits. It is used for
troubleshooting and for capturing configuration state in issue reports.

## UI Shell

The application shell consists of the main window, the navigation sidebar,
the page stack, and the page lifecycle contract.

### Page lifecycle

Every page inherits `academic_platform.ui.pages.base_page.BasePage`. The
base class provides:

- A standardized header (title, subtitle, header-actions region).
- A content stack with two slots: primary content and an optional empty
  state. Pages switch between the two with `show_content` and
  `show_empty_state`.
- Three lifecycle hooks invoked by the shell:

  - `on_activated` — called each time the page becomes the visible page.
    Refreshing pages override this.
  - `on_deactivated` — called each time the page stops being the visible
    page. Pages that own timers or background work override this.
  - `can_close` — consulted during application shutdown. Returning False
    vetoes closure.

### Page factory

`academic_platform.ui.pages.create_page` constructs a page for a given
destination identifier. Implemented destinations return their concrete page;
unimplemented destinations return a `PlaceholderPage` that states the
destination's purpose without pretending to be complete.

Adding a new implemented destination requires:

1. Writing a `BasePage` subclass.
2. Registering the subclass in `create_page`.

No other module needs to change.

### Navigation

The navigation sidebar emits a destination identifier whenever the selection
changes. The main window owns navigation: it activates and deactivates pages
according to the lifecycle contract, updates the status bar, and enforces
that only registered destinations can be selected.

Keyboard shortcuts for every destination are declared on the destination
registry (`DESTINATIONS`). They are installed as application-wide
`QShortcut` instances and duplicated in the `View` menu.

### Placeholder policy

A placeholder page must:

- Use the destination's label as its title.
- Use the destination's purpose as its subtitle.
- State clearly that the destination is under development.
- Contain no interactive control that pretends to perform the destination's
  work.

Placeholder pages are the only permitted representation of unimplemented
functionality.

## Component Library

Reusable presentation components live in `academic_platform.ui.components`.
They are presentation-only: no component imports from repositories, HTTP
clients, or statistical libraries. Components emit signals and expose
properties; the shell or a page controller wires them to application
services.

### Inventory (part 1)

- `SectionCard` — titled card with a body state stack (content, loading,
  empty, error). Callers install content once and switch states by calling
  `show_content`, `show_loading`, `show_empty`, or `show_error`.
- `EmptyState` — panel for empty regions. Carries a title, a message, an
  optional glyph, and an optional action button. The action signal
  `action_requested` is emitted only when the button is enabled; an
  unconnected action button is disabled.
- `ErrorState` — panel for failure regions. Distinct styling and semantics
  from `EmptyState`. Carries a message and an optional retry button whose
  `retry_requested` signal mirrors `EmptyState.action_requested`.
- `LoadingIndicator` — indeterminate or determinate progress with a message.
  In determinate mode, `set_progress` clamps values to the valid range.
- `ProgressBar` — determinate progress with an optional label and an
  optional cancel button. Emits `cancel_requested`.
- `SearchBar` — input with submit, clear, optional scope selector. Emits
  `submitted(text, scope)`, `cleared()`, `scope_changed(scope)`, and
  `text_changed(text)`.
- `FilterPanel` — collapsible panel rendering filter fields from a
  declarative description. Emits `filters_changed(state)` with a dictionary
  keyed by field identifier.
- `PageHeader` — standalone header with title, subtitle, and actions
  region. `BasePage` delegates to this component so that header rendering
  is unified.

### Component policies

- A component never executes application logic. It renders what it is
  given and emits the intent the user expressed.
- A control that has no handler connected must be disabled. A live control
  that does nothing is not permitted.
- Object names are stable and used by both the stylesheet and UI tests.
  Renaming an object name is a breaking change and must be reflected in
  both `styles.py` and the corresponding tests.
- State is stored in the component, not in the caller, when the state is
  purely visual (for example, whether the filter panel is collapsed). State
  that represents user data (for example, the search query) is owned by
  the caller and reflected into the component through setters.
- Components accept an optional `parent` widget and correctly reparent
  children they create.

### Inventory (part 2)

- `StatBadge` — compact label-value badge with a visual tone
  (`neutral`, `positive`, `warning`, `danger`). The tone is applied as a
  dynamic Qt property so the stylesheet can key on it without rebuilding.
- `TagList` — wrapping list of tag chips with optional removal and
  activation. Emits `tag_removed(identifier)` and
  `tag_activated(identifier)`. The component is a view onto a caller-owned
  list; it never mutates the list itself.
- `MetadataGrid` — two-column label/value grid with optional link values.
  Emits `link_activated(key, value)`; the component never opens URLs.
- `ArticleCard` — publication summary card. Carries a
  `PublicationSummary` payload; emits `activated`, `save_requested`,
  `open_requested`, and `details_requested`.
- `ResearchProjectCard` — research project summary card. Carries a
  `ResearchProjectSummary` payload; emits `opened`, `edited`, and
  `archived`.
- `CollectionCard` — collection summary card. Carries a
  `CollectionSummary` payload; emits `opened`, `edited`, and `exported`.
- `AIProviderCard` — AI provider configuration card. Carries an
  `AIProviderSummary` payload; emits `test_requested`, `edit_requested`,
  `remove_requested`, and `enabled_toggled(identifier, enabled)`.
- `SearchSourceRow` — search source configuration row. Carries a
  `SearchSourceSummary` payload; emits `test_requested`, `edit_requested`,
  `remove_requested`, and `enabled_toggled(identifier, enabled)`.

### Payload conventions

Content cards accept a plain, immutable payload dataclass rather than a
domain object. This decouples the presentation layer from the persistence
layer and allows the UI to be developed before the domain model is
finalized. Later phases may add adapter functions that convert a domain
object into the corresponding payload.

Payloads are frozen dataclasses with default values for optional fields.
Unknown or unavailable fields are empty strings or empty tuples; the card
hides rows whose value is empty so that no placeholder text is displayed.

### Enable-then-connect rule

Every actionable control on a card is disabled at construction. The caller
enables a control by calling the corresponding `enable_*` method after it
has connected the control's signal to a handler. This rule prevents a live
control that does nothing and makes the wiring state visible in the code.

Toggle controls (the enable checkbox on `AIProviderCard` and
`SearchSourceRow`) do emit their signal even when initially disabled by the
caller's policy; the caller reflects persisted state back through
`set_enabled`, which suppresses the signal to avoid loops.

## Dialogs

Standard dialogs live in `academic_platform.ui.dialogs`. The
`DialogFactory` is the single entry point; callers express intent and do
not assemble widgets ad hoc.

### Dialog catalogue

- `MessageDialog` — informational, warning, or error message with an
  optional expandable details pane and an optional "copy details"
  button. Details are hidden by default.
- `ConfirmDialog` — yes/no confirmation with a configurable default
  button, optional details pane, and optional "do not ask again"
  checkbox. Returns a `ConfirmOutcome` carrying both the decision and the
  checkbox state.
- `PromptDialog` — single-line text prompt with a synchronous validator.
  The OK button is disabled while the validator reports a problem. The
  value is trimmed by default.
- `FormDialog` — multi-field dialog built from a declarative field list.
  Each field has a kind (`text`, `multiline`, `checkbox`, `select`) and an
  optional validator. The submit button is disabled while any field fails
  validation.
- `ProgressDialog` — modal progress dialog with an optional cancel
  button. Cancellation is a request, not an enforcement.

### Dialog policies

- Dialogs never perform the action they confirm. They return the user's
  decision to the caller, which performs the action.
- The default button for destructive actions is the cancelling button.
  Callers request the opposite behaviour explicitly by passing
  `default_to_confirm=True`.
- Dialogs do not persist state. The "do not ask again" checkbox state is
  returned through `ConfirmOutcome`; the caller decides whether to
  persist it.
- Error dialogs always accept a `details` payload and render a "copy
  details" button when the payload is non-empty. Technical diagnostics
  are confined to the details pane.

## Notifications

Non-blocking notifications live in `academic_platform.ui.notifications`.
They are used for events that do not require a decision.

### Components

- `Notification` — immutable value carrying an identifier, title,
  message, severity, timeout, and creation timestamp.
- `NotificationService` — bounded queue with publish, dismiss, and
  observer APIs. The service is Qt-independent and testable in isolation.
- `NotificationHost` — Qt widget that renders the notifications as
  stacked cards anchored to the bottom-right of its parent widget.

### Policies

- Errors do not auto-dismiss. Informational, success, and warning
  notifications auto-dismiss after their timeout.
- The service maintains a bounded queue. When the queue exceeds the
  maximum size, the oldest notification is dropped.
- Dismissal is idempotent. Dismissing an unknown identifier is a no-op.
- The service does not own timing. Automatic dismissal is implemented in
  the host card via a per-card `QTimer`.
- Notifications are presentation-only. They never perform the action they
  report; callers publish notifications to describe events that have
  already occurred.

### Wiring

The bootstrap attaches a `NotificationService` to the `MainWindow` and
constructs a `NotificationHost` over the window. Pages obtain the service
through `window.notifications`.

## Dashboard Page

The dashboard is the landing page. It renders the following sections, each
as a `SectionCard`:

1. Quick actions
2. Recent research projects
3. Recently opened articles
4. Saved searches
5. Current research tasks
6. Pending evidence reviews
7. Recent analysis reports
8. Recent activity

### Data provider contract

The dashboard reads its data through a callable registered on the main
window as `dashboard_data_provider`. The callable returns a mapping whose
keys are a subset of:

- `recent_projects` — list of `ResearchProjectSummary`
- `recent_articles` — list of `PublicationSummary`
- `saved_searches` — list of strings
- `research_tasks` — list of strings
- `pending_evidence` — list of strings
- `recent_reports` — list of strings
- `recent_activity` — list of strings

Missing keys are treated as empty. Until the persistence layer registers a
provider, every section renders an explicit empty state.

### Refresh

The shell calls `refresh()` when the dashboard becomes visible. The page
also exposes a header-level "Refresh" button that invokes the same method.
`refresh()` is idempotent and cheap when the provider returns empty
collections.

### Empty state actions

The "Recent research projects" section renders an empty state with an
enabled action button that navigates to the research projects destination.
Every other section renders an empty state without an action button
because the appropriate next step is either to navigate to another page or
to perform an action that is not yet available.

### Navigation

The dashboard emits `destination_requested(identifier)` when a quick action
or an empty-state action is activated. The shell connects this signal to
`navigate_to`. The dashboard never navigates itself.

## Global Search

The global search page (`academic_platform.ui.pages.search`) presents two
result surfaces through a `QTabWidget`:

- **Local** — results from the user's own library, projects, collections,
  notes, and extracted evidence.
- **Remote** — results from the enabled academic search sources.

### Search controller

The page does not fetch anything itself. It calls a `SearchController`
through the protocol defined in
`academic_platform.ui.pages.search.search_controller`. The protocol
exposes two methods:

- `search_local(query) -> SearchResponse`
- `search_remote(query) -> SearchResponse`

`SearchResponse` carries the entries, per-source status reports, a partial
flag, and an optional message. The page renders these values verbatim. It
never interprets the underlying data.

Until the local and remote search subsystems are available, the page uses
`NullSearchController`. It returns empty results with `SourceStatus.SKIPPED`
and a message explaining that the subsystem is not yet available. This is
the only controller the application installs by default.

### Scope selector

The search bar carries a scope selector with three values: `all`, `local`,
and `remote`. The scope determines which tab is focused after the search
completes. It does not restrict which subsystems are queried when `all` is
selected; both `search_local` and `search_remote` are invoked.

### Source status panel

Every search response reports per-source status. The page renders this
report explicitly:

- `OK` with a result count.
- `FAILED` with the error message.
- `SKIPPED` with the reason.
- `DISABLED` with no further detail.

A partial response is flagged on the response and is reflected in the
status panel. The page never claims a source succeeded when it did not.

### Result entries

A `SearchResultEntry` carries a stable identifier, a title, an optional
subtitle and snippet, an origin, a source label, an optional score, and
optional metadata. The identifier is used to correlate the entry with a
caller-owned record; the page does not resolve the identifier itself.

### Filters

Each tab owns a `FilterPanel` instance. Local results filter on kind
(library, project, collection, note, evidence) and year. Remote results
filter on access, year, and sort order. Filters are not applied by the
page; the controller receives the query only. Filter application is
introduced when the corresponding data sources are available.

## Settings Page

The Settings page hosts six tabs, each a `SettingsTab` subclass:

1. **General** — interface language, update checks, telemetry, exit
   confirmation.
2. **Appearance** — theme, font scale, density, navigation labels.
3. **Search** — result limit, request timeout, concurrency, deduplication,
   HTTPS requirement.
4. **AI Providers** — default provider and model, external-provider
   policy, excerpt transmission policy.
5. **Privacy** — log level, log retention, content redaction, search
   history.
6. **Advanced** — network behavior, resolved paths, diagnostic actions,
   reset to defaults.

### Persistence model

Every control persists its value on change through
`SettingsService.update_section`. There is no global Apply button. The
settings schema validates every update; an update that fails validation is
rejected and the tab re-populates from the current settings.

### Cross-tab coordination

The page subscribes to the settings service. When settings change
externally (another tab, a command-line edit, another window in a later
phase), the page calls `reload()` on every tab. Each tab sets
`self._loading = True` while populating so that user-facing signals do not
trigger redundant persistence calls.

### Reset to defaults

The Advanced tab exposes a "Reset to defaults" action guarded by a
confirmation dialog. Confirmation invokes
`SettingsService.reset_to_defaults`, which persists the schema defaults
and notifies observers. The tab emits `settings_reset` and publishes a
success notification.

### Diagnostic actions

The Advanced tab exposes "Open configuration folder" and "Open log
folder". Both actions open the resolved path using the platform's native
handler. Failures are logged and do not crash the application.

### Resolved paths

The Advanced tab displays the resolved configuration file, database, log,
managed library, and exports directories. The values are read from
`AppDirectories`; the tab never resolves paths itself.

## Persistence Foundation

The persistence layer is built on SQLAlchemy 2.x with SQLite as the storage
engine. The foundation lives in
`academic_platform.infrastructure.database` and consists of three
components:

- `DatabaseConfiguration` — an immutable description of how the engine is
  bound.
- `Database` — the engine and session factory wrapper.
- Typed exceptions `DatabaseError` and `DatabaseConfigurationError`.

Schema declaration and migrations are delivered in subsequent phases. This
phase introduces only the engine and the session lifecycle.

### Configuration

`DatabaseConfiguration` is constructed through two convenience class
methods:

- `for_file(path)` — binds to a file-backed SQLite database. The URL is
  built from the absolute path so that the engine does not depend on the
  process working directory.
- `for_memory()` — binds to an in-memory database. The journal mode is
  forced to `MEMORY` because WAL is not supported for in-memory databases.

The configuration validates the URL scheme, the busy timeout, the journal
mode, and the synchronous mode. Unknown values are rejected rather than
silently normalized.

### Engine

The engine is created with `future=True` for SQLAlchemy 2.x semantics. The
connection pool is `NullPool` for file-backed databases because SQLite
serializes writes at the file level and does not benefit from a
connection pool; `StaticPool` is used for in-memory databases so that every
session shares the same in-memory instance.

A `connect` event listener applies the SQLite PRAGMAs that the application
depends on:

- `busy_timeout` — lets a writer wait instead of failing immediately when
  a reader holds a lock.
- `foreign_keys = ON` — SQLite does not enforce foreign keys by default.
- `journal_mode` — `WAL` for file-backed databases, `MEMORY` for
  in-memory databases.
- `synchronous` — `NORMAL`, the recommended setting when WAL is enabled.

The listener logs the first successful connection at INFO level and every
subsequent connection at DEBUG level. No SQL text is logged unless `echo`
is enabled.

### Sessions

Sessions are short-lived. The `Database.session()` context manager yields
a session, commits on success, rolls back on failure, and closes the
session in all cases. The session factory disables `expire_on_commit` so
that detached instances do not perform implicit IO; autoflush is enabled so
that result sets are consistent with the in-memory unit of work.

`Database.session_scope` is an explicit alias for `Database.session`. Both
names refer to the same context manager. Call sites that read more clearly
with one name use it; no behavior differs between them.

### Diagnostics and maintenance

- `health_check()` executes a trivial statement and returns a boolean. It
  does not raise.
- `integrity_check()` runs `PRAGMA integrity_check` and reports the
  result.
- `vacuum()` reclaims space. It is skipped for in-memory databases.
- `analyze()` refreshes SQLite's query planner statistics.
- `dispose()` releases the engine and its connection pool.

### Wiring

The bootstrap constructs a `Database` from the resolved `AppDirectories`,
performs a health check before constructing the UI, passes the wrapper to
the main window, and disposes it after the Qt event loop exits. A database
failure before startup returns a dedicated exit code and is reported
before any window is shown.

The main window exposes the database through a `database` property. Pages
obtain it through the page factory, which accepts the database as a
parameter. No page disposes the database.

## Migrations

Schema evolution is managed by Alembic. The environment is configured
programmatically so that the database URL always matches the application's
actual database.

### Layout

- `alembic.ini` — Alembic configuration. The `sqlalchemy.url` field is
  intentionally blank; the URL is resolved at runtime.
- `migrations/env.py` — the migration environment. Reads the URL from
  `AppDirectories` unless an override is supplied, resolves
  `target_metadata` lazily from
  `academic_platform.infrastructure.database.base`, and enables
  `compare_type`, `compare_server_default`, and `render_as_batch`.
- `migrations/script.py.mako` — the template used when generating
  revisions.
- `migrations/versions/` — revision scripts. The baseline revision is
  `0001_baseline`; it performs no schema changes and exists so that later
  revisions have a stable parent.

### Runtime

Migrations run at application startup, before the health check and before
the UI is constructed. The runner is
`academic_platform.infrastructure.database.migrations.upgrade_to_head`.
It reads the previous revision, applies every pending revision, and
returns a `MigrationResult` describing the transition. A failure raises
`DatabaseMigrationError`, which the bootstrap reports with a dedicated
exit code.

The runner is idempotent. Running it against an up-to-date database reports
the current revision as both the previous and the resulting revision.

### SQLite specifics

SQLite does not support most `ALTER TABLE` operations. `render_as_batch`
is enabled in the environment so that Alembic rewrites tables inside a
transaction, which SQLite does support. New migrations rely on this
behavior automatically; no per-revision opt-in is required.

### Command-line tool

`scripts/migrate.py` exposes `upgrade`, `downgrade`, `current`, and
`head`. The tool uses the application database by default and accepts a
`--url` override for diagnostics.

### Baseline revision

The baseline revision performs no schema changes. Its purpose is to
record an initial revision identifier. Reverting it leaves the database
in the same empty state it had before the baseline was applied.

### Future migrations

Every subsequent phase that adds or changes a table adds a revision whose
`down_revision` refers to the previous head. Revisions are reviewed
carefully: autogenerate produces a proposal, not a verified migration.

## Declarative Base and Core Tables

The persistence layer's declarative base lives in
`academic_platform.infrastructure.database.base`. It provides `Base`,
`TimestampMixin`, and `VersionMixin`, and it exports a module-level
`metadata` alias so that Alembic's environment can import the metadata
object directly.

### Naming convention

A constraint naming convention is applied through `MetaData`. Every
constraint and index produced by the ORM has a deterministic name, which
makes migrations readable and reversible. The convention is not optional;
it is attached to the metadata that `Base` uses.

### Shared mixins

- **`TimestampMixin`** adds `created_at` and `updated_at`. Both columns
  store timezone-naive UTC values. `created_at` is set on insert.
  `updated_at` is set on insert and refreshed on every update.
- **`VersionMixin`** adds a `version` column with a default of `1`. The
  column is not incremented automatically by a database trigger; callers
  that need optimistic concurrency compare the loaded version with the
  persisted version before saving. Future phases may add a SQLAlchemy
  event listener to increment on flush if a strict counter is required.

### Model registration

Models live under
`academic_platform.infrastructure.database.models`. The base module
imports the models package at the end of its own module body so that
tables are registered on `Base.metadata` before Alembic inspects it. The
import is deferred to avoid a circular import: model modules import
`Base` from the base module.

### Core tables

- **`user_profile`** — one row per user profile. The `key` column is
  unique and immutable. Optional fields default to `NULL`.
- **`app_settings`** — a single row holding installation-level values.
  A check constraint restricts `id` to `1`, enforcing the singleton
  invariant at the database level.
- **`audit_event`** — an append-only audit trail. Events carry an actor,
  an action identifier, optional target metadata, a short summary, and an
  optional JSON payload. Two indexes support the timeline queries that
  the dashboard will use.

### Pydantic schemas

`academic_platform.infrastructure.database.schemas` provides the
boundary schemas that validate values entering and leaving the
persistence layer. They are distinct from the settings schema (which
validates the user-editable configuration file) and from the external API
schemas (which validate the HTTP surface).

Persistence schemas accept ORM instances directly. The `from_attributes`
flag on their shared base enables `model_validate` to consume ORM objects
without an intermediate dictionary conversion.

### Migration 0002

The revision `0002_user_profile_settings_audit` creates the three tables
and their indexes. The migration is fully reversible: downgrading drops
the indexes and then the tables. Reverting this revision leaves the
database at `0001_baseline`, which represents an empty database.

## Repository Pattern

The repository layer sits between the application layer and the
persistence layer. It isolates the rest of the codebase from SQLAlchemy's
query API, centralizes query composition, and provides a single place
where persistence errors are translated into typed exceptions.

### Components

- **`Repository`** — the typed base class. Concrete repositories subclass
  `Repository[Entity]` and set the `entity` attribute to the ORM class
  they manage. The base class provides:
  - `get`, `get_or_raise`, `find_one`, `find_all`, `find_page`, `count`,
    `exists`.
  - `add`, `create`, `update`, `update_fields`, `delete`, `delete_by_id`,
    `add_all`.
- **`Specification`** — a composable predicate over an ORM entity.
  `AndSpecification`, `OrSpecification`, and `NotSpecification` combine
  specifications with `&`, `|`, and `~`. Each specification yields a
  SQLAlchemy expression through `to_expression(entity)`.
- **`PageRequest`** and **`Page`** — pagination primitives. `PageRequest`
  validates its values; `Page` carries the slice, the request, and the
  total count.
- **`RepositoryManager`** — constructs repositories bound to a single
  session. Repository classes are registered by key; instances are
  constructed lazily and cached for the manager's lifetime.
- **`unit_of_work`** — a context manager that yields a `RepositoryManager`
  bound to a transactional session. The session is committed on success
  and rolled back on failure.

### Design rules

- Repositories never own a session factory. They operate on the session
  they are given. This makes composition into a single unit of work
  possible and keeps testing straightforward.
- Repositories never commit. Commit and rollback are the caller's
  responsibility through `Database.session()` or `unit_of_work`.
- Repositories flush when they need to materialize server-generated
  values. They do not implicitly commit.
- Persistence errors are translated. Callers depend on `RepositoryError`,
  `EntityNotFoundError`, `DuplicateEntityError`, and
  `RepositoryValidationError`; they never see SQLAlchemy exceptions.
- Specifications operate on ORM classes and column attributes. They are a
  persistence-layer concept, not a domain concept.
- The base repository is generic over the ORM entity type. Concrete
  repositories declare their entity and inherit the standard operations
  without duplicating them.

### Registration

Repository classes are registered with
`academic_platform.infrastructure.repositories.factory.register_repository`.
The registry is a plain dictionary so that tests may shadow entries for
the duration of a test. The `unit_of_work` context manager reads the
registry each time it is entered, so registrations made at import time and
at runtime are both visible.

### Schemas and repositories

The base repository's `create` and `update` methods accept Pydantic
models. The `Create` schema's fields become constructor keyword arguments
for the ORM entity; the `Update` schema's explicitly set fields are
applied to the existing entity. The repository never inspects the schema
class itself; the convention is that the caller supplies the correct
schema.

## Settings Persistence

The application keeps user-editable settings in ``config.toml`` and a
small set of installation-level values in the ``app_settings`` table.
The two storage locations serve different purposes:

- The configuration file is user-editable, versioned, and portable.
- The database row is protected by the same transactions that protect
  the rest of the user's data.

### Bridge

`academic_platform.application.settings_persistence.SettingsPersistenceBridge`
reconciles the two locations. It is constructed per unit of work and
performs two jobs:

- **Schema version mirroring** — the settings file's `schema_version` is
  written to `app_settings.settings_schema_version` after the settings
  service loads. Recovery tooling can inspect the row even if the file is
  later corrupted.
- **Active user management** — the active user key is stored only in the
  database. `set_active_user` validates that the profile exists before
  activating it; `set_active_user(None)` clears the selection.

### Bootstrap integration

The bootstrap runs `synchronize` after migrations and before constructing
the UI. A failure to reconcile returns a dedicated exit code and is
reported before any window is shown.

### Main window integration

The main window exposes `active_user_key` and `refresh_active_user`. The
value is refreshed when the window finishes construction and whenever the
settings service notifies its observers.

### Repositories

Three concrete repositories are registered with the factory:

- `user_profile` — `UserProfileRepository`.
- `app_settings` — `AppSettingsRepository`.
- `audit_event` — `AuditEventRepository`.

The audit repository overrides the base class's update and delete methods
to raise `RepositoryError`, enforcing the append-only contract at the
repository boundary as well as at the schema boundary.

### Settings page integration

The Settings page's General tab displays the active user key and offers a
"Refresh" action. The tab reads the value through the window's
`active_user_key` property and refreshes it through
`refresh_active_user`. The tab never reads the database directly.

## Projects and Collections

The project and collection subsystem is composed of four tables:

- **`research_project`** — a project under development. The `key` is a
  stable, human-readable identifier. `stage` is a closed enumeration
  enforced by a check constraint. `project_metadata` stores optional
  JSON; it is not queried by the database.
- **`research_question`** — a question belonging to a project. Questions
  are ordered within a project by the `position` column. The `kind`
  column distinguishes main, sub, exploratory, and hypothesis questions.
  The `is_primary` flag designates the primary question. The schema does
  not enforce a unique primary question; the application workflow does.
- **`collection`** — a grouping of materials. `kind` distinguishes
  manual, topic, project, saved-search, and smart collections. A check
  constraint enforces that project-linked collections carry a project
  identifier and that other kinds do not.
- **`collection_item`** — an association between a collection and a
  resource. `item_type` names the kind of resource (publication,
  document, evidence, note); `item_identifier` names the specific
  resource. A unique constraint prevents the same target from being
  added twice to the same collection.

### Repositories

Four concrete repositories are registered with the factory:

- `research_project` — `ResearchProjectRepository`.
- `research_question` — `ResearchQuestionRepository`.
- `collection` — `CollectionRepository`.
- `collection_item` — `CollectionItemRepository`.

Each repository exposes the standard base operations plus the entity-
specific operations the application needs (lookup by stable key, listing
by project, ordered lists, cascade-safe helpers).

### Reusable specifications

`academic_platform.infrastructure.repositories.specifications` holds the
specifications that are used in more than one place:

- `ProjectByStage`, `ProjectTitleContains`.
- `QuestionByProject`, `QuestionByKind`, `PrimaryQuestionForProject`.
- `CollectionByKind`, `CollectionByProject`.

Repository-private specifications continue to live in the repository
module itself.

### Migration 0003

The revision `0003_projects_and_collections` creates the four tables and
their indexes. It is fully reversible. Downgrading drops the tables in
reverse dependency order.

## Document Assets

The personal library is composed of four tables:

- **`document_asset`** — a physical file the user imported or referenced.
  `storage_mode` distinguishes managed copies (under the application's
  library directory) from referenced files (in their original location).
  `checksum_sha256` is the primary key for duplicate detection.
  `processing_state`, `ocr_state`, and `indexing_state` track the
  pipeline's progress. `missing` records whether the underlying file has
  been detected as absent.
- **`document_metadata`** — extracted bibliographic metadata. One row per
  document, enforced by a unique constraint on `document_id`.
  `authors_json` stores an ordered list of author strings as JSON.
  `extraction_confidence` records the extractor's own confidence; a low
  value signals that the user should review the values.
  `reviewed_by_user` records whether the user has confirmed the metadata.
- **`document_chunk`** — extracted text chunks. Chunks are bounded in size
  by the pipeline. `page_number` is nullable when the extractor cannot
  attribute text to a page. `token_count` is stored when available.
- **`annotation`** — user-authored notes, highlights, and bookmarks. The
  `kind` column distinguishes them. Location is expressed with an
  optional page number, an optional text excerpt, and an optional anchor
  string that the reader interprets.

### Repositories

Four concrete repositories are registered with the factory:

- `document_asset` — `DocumentAssetRepository`.
- `document_metadata` — `DocumentMetadataRepository`.
- `document_chunk` — `DocumentChunkRepository`.
- `annotation` — `AnnotationRepository`.

### Reusable specifications

`academic_platform.infrastructure.repositories.specifications` gains:

- `DocumentByProcessingState`, `DocumentByStorageMode`, `DocumentMissing`,
  `DocumentDisplayNameContains`, `DocumentChecksum`.
- `AnnotationByDocument`, `AnnotationByKind`, `AnnotationOnPage`.

### Migration 0004

The revision `0004_document_assets` creates the four tables and their
indexes. It is fully reversible. Downgrading drops the tables in reverse
dependency order.

### Design rules carried forward

- The database never stores the file contents. Files live on disk; the
  database stores location, checksum, and metadata.
- Annotations are separate records. The original PDF is never modified to
  store a note.
- Deletion of a document asset cascades to its metadata, chunks, and
  annotations. Deleting a document is a destructive action; the
  application prompts before it.
- Referenced files can disappear from disk when the user moves or deletes
  them outside the application. The `missing` flag records this state so
  that the application can report it without failing.

## Search and Publications

The search subsystem is composed of five tables:

- **`publication`** — a normalized scholarly work. The DOI is unique
  when present; publications without a DOI are permitted and are
  identified by their stable `key`. The `source_providers_json` column
  records every provider that returned the publication.
- **`search_source`** — a configurable academic search provider.
  Built-in and user-defined sources share the table; the `source_type`
  column distinguishes them. Credentials are never stored in the table;
  they live in the operating system keyring and are referenced by
  `credential_reference`.
- **`saved_search_query`** — a reusable search definition. Filters and
  the target source set are stored as JSON. The application interprets
  them; the database stores them.
- **`search_session`** — a single execution of a search. Each session
  carries its own copy of the query text so that a session remains
  meaningful even if the originating saved query is later deleted.
  Per-source status is stored as JSON.
- **`search_result`** — a single result returned by a session. A unique
  constraint on `(session_id, publication_id)` prevents duplicates;
  deduplication is performed by the orchestration layer before results
  are persisted.

### Repositories

Five concrete repositories are registered with the factory:

- `publication` — `PublicationRepository`.
- `search_source` — `SearchSourceRepository`.
- `saved_search_query` — `SavedSearchQueryRepository`.
- `search_session` — `SearchSessionRepository`.
- `search_result` — `SearchResultRepository`.

### Reusable specifications

`academic_platform.infrastructure.repositories.specifications` gains:

- `PublicationByDoi`, `PublicationOpenAccess`,
  `PublicationTitleContains`, `PublicationInYearRange`.
- `SearchSourceEnabled`, `SearchSourceByType`.
- `SearchSessionByQueryText`, `SearchResultBySession`,
  `SearchResultByProvider`.

### Migration 0005

The revision `0005_search_and_publications` creates the five tables and
their indexes. It is fully reversible. Downgrading drops the tables in
reverse dependency order.

### Migration head as a moving target

The head revision changes with every new migration. Tests and diagnostics
that need the current head call
`academic_platform.infrastructure.database.declared_head_revision` or
import `EXPECTED_HEAD` from `tests.unit._migration_head`. Tests that name
a specific revision for a targeted operation (downgrade to an
intermediate state, for example) use the literal revision identifier,
which is stable by definition.

## AI Providers and Models

The AI subsystem is composed of four tables:

- **`ai_provider`** — a configured provider. `provider_kind` distinguishes
  local GGUF providers, OpenAI-compatible APIs, Anthropic, and other
  hosted services. `endpoint_url` is populated for every provider,
  including local ones; the application never loads a GGUF file directly
  and instead calls the local runtime's HTTP endpoint.
  `credential_reference` is an opaque identifier for a credential in the
  operating system keyring. The database never stores the secret value.
- **`ai_model`** — a model exposed by a provider. The pair
  `(provider_id, model_identifier)` is unique. `capabilities_json`
  stores provider-declared capabilities; the application reads it to
  decide whether a task can be routed to the model.
- **`ai_task_routing`** — a mapping from task to provider and model.
  `task_key` is unique. `provider_id` and `model_id` are nullable;
  when they are null, the application falls back to the provider- and
  model-level defaults, then to the application default declared in
  `app_settings`. Optional fallback columns are used when the primary
  target fails for a recoverable reason.
- **`ai_invocation`** — an append-only log of provider invocations. The
  log never stores prompt or response bodies; only identifiers, sizes,
  token counts when the provider reports them, and metadata are
  recorded. `status` is a closed enumeration.

### Repositories

Four concrete repositories are registered with the factory:

- `ai_provider` — `AIProviderRepository`.
- `ai_model` — `AIModelRepository`.
- `ai_task_routing` — `AITaskRoutingRepository`.
- `ai_invocation` — `AIInvocationRepository`.

The invocation repository overrides the base class's update and delete
methods to raise `RepositoryError`, enforcing the append-only contract at
the repository boundary as well as at the schema boundary.

### Reusable specifications

`academic_platform.infrastructure.repositories.specifications` gains:

- `AIProviderEnabled`, `AIProviderByKind`.
- `AIModelEnabled`, `AIModelByProvider`.
- `AIInvocationByTask`, `AIInvocationFailed`.

### Migration 0006

The revision `0006_ai_providers_and_models` creates the four tables and
their indexes. It is fully reversible. Downgrading drops the tables in
reverse dependency order.

### Design rules carried forward

- Secrets are never stored in the database. Provider authentication uses
  the operating system keyring; the database stores only an opaque
  reference.
- Provider and model health is checked explicitly. The application does
  not assume a provider is reachable; `health_state` is updated after
  each test.
- Task routing resolves in a defined order: explicit task routing,
  model-level default, provider-level default, application default. A
  failure at any step is reported explicitly rather than silently
  ignored.
- Invocations are append-only. The log supports diagnostics and cost
  estimation without storing user content.

## Evidence and Analysis

The evidence and analysis subsystem is composed of five tables:

- **`evidence_extraction_run`** — a single execution of the extraction
  pipeline over a document. Runs are append-only; re-running extraction
  creates a new run and preserves the previous one so that the user can
  compare results and revert to an earlier extraction.
- **`evidence_record`** — a structured fact extracted from a document.
  The record carries both the extracted value and the raw source text so
  that a reviewer can verify the extraction against the source.
  `verification_status` distinguishes AI-proposed, auto-parsed,
  user-verified, uncertain, rejected, and missing records.
  `extraction_method` preserves the distinction between deterministic
  extraction, AI-assisted proposal, and user entry. Original and
  normalized values are stored separately.
- **`analysis_run`** — a single execution of the statistical engine. The
  run carries the analysis type, the engine version, the library
  versions, the settings the engine consumed, warnings, results, and
  timing information. Results are stored as a JSON payload because the
  shape varies by analysis type.
- **`analysis_input`** — a single input value consumed by an analysis
  run. Inputs are stored as separate rows so that the reproducibility
  record is complete and so that individual values can be linked to the
  evidence records they came from.
- **`synthesis_report`** — a source-linked synthesis report. Reports
  record the contributing runs, the included and excluded evidence, the
  exclusion reasons, the limitations, and the reproducibility record.

### Repositories

Five concrete repositories are registered with the factory:

- `evidence_record` — `EvidenceRecordRepository`.
- `evidence_extraction_run` — `EvidenceExtractionRunRepository`.
- `analysis_run` — `AnalysisRunRepository`.
- `analysis_input` — `AnalysisInputRepository`.
- `synthesis_report` — `SynthesisReportRepository`.

### Reusable specifications

`academic_platform.infrastructure.repositories.specifications` gains:

- `EvidenceByDocument`, `EvidenceByType`, `EvidenceByVerification`,
  `EvidenceAwaitingReview`.
- `AnalysisByType`, `AnalysisSucceeded`.

### Migration 0007

The revision `0007_evidence_and_analysis` creates the five tables and
their indexes. It is fully reversible. Downgrading drops the tables in
reverse dependency order.

### Design rules carried forward

- Evidence records carry provenance. The raw source text, page number,
  section title, and extraction method are always recorded when
  available. A record without provenance is not treated as authoritative.
- The AI subsystem proposes evidence; it does not confirm it. Records
  produced by AI assistance carry the `ai_proposed` verification state
  and are excluded from synthesis until they are reviewed.
- Statistical outputs come from the engine. The AI layer never computes
  a statistic. This is enforced at the application layer; the schema
  records what the engine produced.
- Analysis inputs are stored. An analysis run can be replayed from its
  stored inputs and settings; the application compares the replay's
  output with the stored result to detect divergence.
- Synthesis reports reference the evidence they consumed. The list of
  included and excluded evidence is stored with the report so that the
  reasoning is traceable.

## Knowledge, Guides, Achievements, and Plans

This phase adds four clusters of tables:

### Knowledge map

- **`knowledge_node`** — a node of the map. `node_kind` is a closed
  enumeration. The `key` is stable and constructed by the application.
- **`knowledge_relationship`** — a directed edge. The combination
  `(source_node_id, target_node_id, relationship_kind)` is unique.
  `grounding` distinguishes metadata-derived, user-linked, and
  AI-proposed edges. AI-proposed edges are visually distinguished until
  the user confirms them.

### Research guides

- **`research_guide`** — a structured guide owned optionally by a
  project or collection. Guides are user content; deleting the owner
  clears the reference but preserves the guide.
- **`research_guide_section`** — an ordered section of a guide. Sections
  carry their own body text; source-derived sections carry citations.
- **`citation_record`** — a citation linking a section to a typed source
  (publication, document, evidence, external). The quoted text and page
  number are recorded so the claim can be verified.

### Achievements and activity

- **`achievement`** — a definition. Definitions are stored so they can be
  revised without changing application code.
- **`achievement_unlock`** — a record that a user profile unlocked an
  achievement. The combination `(achievement_id, user_key)` is unique.
- **`user_activity`** — an append-only feed of notable actions. The
  repository overrides the base update and delete methods to enforce
  the append-only contract.

### Research plans

- **`research_plan`** — the structured output of the Research Design
  Assistant. Plans are versioned by insertion.
- **`research_task`** — an actionable item within a project.
- **`research_title_candidate`** — a proposed title with rationale,
  strengths, problems, and assumptions.
- **`methodology_proposal`** — a methodology with trade-offs.
- **`analysis_recommendation`** — a statistical-method recommendation
  with assumptions, diagnostics, alternatives, and cautions.

Title candidates, methodology proposals, and analysis recommendations
share a closed `state` enumeration (`proposed`, `accepted`, `rejected`,
`archived`). The user's decision is a first-class attribute.

### Repositories

Thirteen new repositories are registered with the factory:

- `knowledge_node`, `knowledge_relationship`.
- `research_guide`, `research_guide_section`, `citation_record`.
- `achievement`, `achievement_unlock`, `user_activity`.
- `research_plan`, `research_task`, `research_title_candidate`,
  `methodology_proposal`, `analysis_recommendation`.

### Reusable specifications

`academic_platform.infrastructure.repositories.specifications` gains
specifications for every new repository, including `AchievementActive`,
`KnowledgeNodeByKind`, `KnowledgeRelationshipAIGrounded`,
`ResearchGuideByKind`, `ResearchGuideForProject`,
`ResearchGuideSectionFor`, `ResearchPlanForProject`,
`ResearchTaskForProject`, and `ResearchTaskOpen`.

### Migration 0008

The revision `0008_knowledge_guides_achievements_plans` creates the
thirteen tables and their indexes. It is fully reversible. Downgrading
drops the tables in reverse dependency order.

### Design rules carried forward

- The knowledge map distinguishes grounded and AI-proposed edges.
  AI-proposed edges carry the `ai_proposed` grounding state and are
  presented as proposals, not as established facts.
- Guides are user content. Deleting a project or a collection preserves
  the guide and clears the owner reference.
- Achievements are transparent. Definitions are stored, unlocks are
  recorded, and the trigger event is preserved. The system never
  fabricates an unlock.
- Activity entries are append-only. The repository enforces the
  append-only contract; the schema does not store prior versions.
- Research plans are versioned by insertion. The user can compare
  successive plans without losing the earlier ones.

## Persistence Layer Summary

By the end of Phase B the persistence layer is complete and verified:

- **Engine and sessions.** `Database` wraps a SQLAlchemy engine bound to
  a SQLite file. Sessions are short-lived; the `session()` context
  manager commits on success and rolls back on failure. SQLite PRAGMAs
  are applied on every connection through a `connect` event listener.
- **Migrations.** Alembic revisions 0001 through 0008 define the schema.
  Migrations run at application startup before the UI is constructed and
  are exposed through `scripts/migrate.py`.
- **Models.** Every entity is declared as a SQLAlchemy 2.x model
  inheriting from `Base` and, where appropriate, from `TimestampMixin`
  and `VersionMixin`. Every model is registered in the models package so
  that Alembic autogenerate sees the full schema.
- **Schemas.** Every entity has a Pydantic `Create`, `Update`, and
  `Read` schema in `academic_platform.infrastructure.database.schemas`.
  The schemas validate values at the boundary; the models do not perform
  boundary validation.
- **Repositories.** Every entity has a repository in
  `academic_platform.infrastructure.repositories` registered with the
  factory. The base repository provides the standard operations; the
  concrete repositories add the entity-specific operations the
  application needs.
- **Specifications.** Reusable specifications live in the
  `specifications` subpackage. Repository-private specifications live in
  the repository module itself.
- **Append-only contracts.** The audit, activity, and invocation
  repositories override the base update and delete methods to raise
  `RepositoryError`. The contract is enforced at the repository
  boundary as well as at the schema boundary.

The Phase B acceptance harness verifies that the migration head is
discoverable, migrations are idempotent, downgrade works, every
registered table exists after upgrade, every repository constructs
against a live session, every exported schema is importable, round-trip
persistence survives a session close, foreign-key cascades behave as
declared, and the append-only contracts are enforced.

## Search Provider Adapter Interface

The search provider subsystem lives in
`academic_platform.infrastructure.search_providers`. It defines a narrow
interface that every concrete academic provider implements, plus the
value objects that describe requests, responses, capabilities, and
status.

### Interface

`SearchProviderAdapter` is the abstract base class. Concrete adapters
implement three members:

- `descriptor` — a `ProviderDescriptor` carrying the provider's key,
  display name, base URL, documentation URL, provider kind, filter
  support, and capabilities.
- `search(request)` — executes a single search and returns a
  `SearchResponse`.
- `test_connection()` — verifies reachability and returns a
  `SourceStatusReport`. It returns a report for transient failures and
  raises `ProviderConfigurationError` only for misconfiguration.

The interface is synchronous. Long-running work is the caller's
responsibility; the orchestration layer executes adapters on a worker
thread.

### Value objects

- `ProviderFilterSupport` describes which filters the provider supports
  natively. The orchestration layer uses this to decide whether a filter
  can be pushed down to the provider or must be applied locally.
- `ProviderCapabilities` describes optional features: pagination,
  cursor-based pagination, abstract availability, citation counts, open
  access flag, API key requirement, and the maximum number of results
  per page.
- `SearchRequest` is provider-neutral. It carries the free-text query,
  pagination parameters, filter values, sort mode, and a provider-
  specific `extra` mapping. Provider-specific parameters are never
  first-class fields of the request.
- `SearchHit` is provider-neutral. It carries the normalized
  bibliographic fields plus the provider key and provider identifier
  that together form the provider's stable identifier for the work.
- `SearchResponse` carries the hits, the total reported by the provider,
  the next cursor when the provider supports cursor pagination, and the
  per-request `SourceStatusReport`.
- `SourceStatus` and `SourceStatusReport` describe the outcome of a
  single request. The orchestration layer aggregates these reports
  across providers.

### Errors

- `ProviderError` is the base class. Concrete adapters raise only its
  subclasses outward.
- `ProviderConfigurationError` covers misconfiguration detected before a
  request is issued.
- `ProviderRequestError` covers network failures, timeouts, and invalid
  request parameters detected before the response is received.
- `ProviderResponseError` covers malformed or unexpected responses.
- `ProviderUnavailableError` covers rate limits, service outages, and
  authentication failures that may be resolved by retrying later.

### Registry

`ProviderRegistry` maps a provider key to an adapter. Entries may be a
class, a factory that constructs an adapter from a configuration
dictionary, or a pre-constructed instance. The registry exposes
`registered_keys`, `descriptors`, and `get`. Registering an existing key
replaces the previous entry; this is intentional because tests override
entries for the duration of a test.

`default_registry()` returns the process-wide registry. The null adapter
is registered under the key `"null"` so that the orchestration layer
always has a fallback. The null adapter reports honestly that no remote
source is configured.

### Migration to concrete adapters

Later phases add concrete adapters for Crossref, OpenAlex, Semantic
Scholar, PubMed, Europe PMC, and arXiv. Each adapter registers itself
with the default registry at import time and carries its own descriptor.
Adapters never mutate the request; they return fresh response objects on
every call.

## Search Source Registry Service

The search source registry service lives in
`academic_platform.application.search_sources`. It mediates between
persisted source configuration and the provider adapter interface.

### Components

- **`SourceConfig`** — immutable value object describing a source's
  configuration. It is constructed from the ORM row at the boundary;
  callers never see ORM state.
- **`SourceRecord`** — a `SourceConfig` paired with its database
  identifier and timestamps.
- **`SourceResolver`** — resolves a persisted source to a provider
  adapter through the provider registry. It caches adapters per source
  key for the lifetime of the resolver. When a provider key is not
  registered, the resolver falls back to the null adapter rather than
  raising.
- **`SearchSourceService`** — the application service. It lists, enables,
  disables, tests, updates, and removes sources. It validates every
  source against the URL safety policy before persisting it.
- **`CatalogInstaller`** — installs the built-in source catalog into the
  database. Installation is idempotent: missing entries are created,
  display-level fields of existing entries are refreshed, and
  user-editable fields (enabled, result_limit, timeout_seconds) are
  preserved.

### URL safety policy

Every user-supplied URL is validated before it is stored and again
before a request is issued. The validator lives in
`academic_platform.infrastructure.search_providers.url_validator` and
implements the following rules:

- Only `https` is accepted by default. `http` is accepted only when the
  caller explicitly allows it for a specific source.
- URLs with embedded credentials are rejected.
- Loopback addresses are rejected unless the caller explicitly allows
  them for a local source.
- Private, link-local, and cloud metadata addresses are always rejected.
- The host is resolved and the resulting addresses are revalidated to
  reduce DNS rebinding risk.

The validator never performs a network request. It uses the operating
system resolver only when the caller asks for resolution.

### Built-in catalog

The catalog lives in `academic_platform.application.search_sources.catalog`
and ships six built-in sources: Crossref, OpenAlex, Semantic Scholar,
PubMed, Europe PMC, and arXiv. Each entry declares the provider key, the
base URL, the endpoint, the parameter map, the provider's capabilities,
and the default limits. The catalog is data, not code: adding a new
built-in source is a matter of adding an entry.

### Startup integration

The bootstrap installs the built-in catalog after migrations and after
settings reconciliation, and attaches the `SearchSourceService` to the
main window before the window is shown. A failure to install the catalog
is logged and reported but does not prevent the UI from starting; the
search page falls back to the null adapter.

### Migration to concrete adapters

Concrete adapters for the built-in sources are delivered in later
phases. Each adapter registers itself with the default provider registry
at import time and carries its own descriptor. Once registered, the
source resolver automatically resolves the built-in source to the
concrete adapter instead of the null adapter.

## HTTP Client Infrastructure

The HTTP client lives in `academic_platform.infrastructure.http` and is
shared by every search provider adapter. It wraps `httpx` and adds the
safety guarantees the application requires.

### Configuration

`HttpClientConfig` is an immutable value object. It carries the base URL,
timeouts (connect, read, write, pool), retry policy (attempts, initial
backoff, maximum backoff), response size limit, allowed content types,
redirect limit, HTTP and loopback flags, rate-limit parameters, user
agent, default headers, TLS verification flag, and optional credentials.
Every field is validated at construction; invalid configurations are
rejected before any request is issued.

### Client

`HttpClient` is a synchronous client. It is safe to share across threads
and is intended to be constructed once per search source adapter. It
provides `get`, `post`, and a general `request` method. Every call
returns an `HttpResponse` value object with status code, normalized
headers, body, effective URL, and elapsed milliseconds.

### Safety guarantees

- **URL and destination revalidation.** Every request revalidates the
  absolute URL and the resolved destination through the URL safety
  validator. A URL that passed validation when a source was saved can
  later resolve to a different address; the client catches that.
- **Bounded retries.** Retries are limited to GET and HEAD requests and
  to transient status codes (429, 502, 503, 504) or transport-level
  failures. Exponential backoff is capped by the configuration.
- **Rate limiting.** A host-scoped token-bucket limiter enforces an
  average rate and a burst capacity. The limiter is process-local and
  shared across threads.
- **Response size limits.** The body is read incrementally and aborted
  as soon as it exceeds the configured limit.
- **Content-type enforcement.** The response content type must be in the
  configured allow-list. Missing content type is permitted so that
  providers that omit it remain usable.
- **Redirect handling.** Redirects are not followed automatically.
  Redirect responses are rejected after revalidating the destination.
- **Credential injection.** Bearer tokens and API keys are injected as
  request headers. They are never logged and never echoed in exception
  messages.
- **Structured logging.** The client logs retry attempts at DEBUG level.
  It never logs request bodies, response bodies, or credentials.

### Factory

`HttpClientFactory` constructs a client from a `SourceConfig` and an
optional resolved secret. The factory is the only place that decides
which client settings a source produces. The factory never resolves
credentials itself; the application layer resolves them from the
keyring and passes them in.

### Errors

- `HttpClientError` is the base class.
- `HttpClientConfigurationError` covers invalid configuration and
  rejected destinations.
- `HttpClientTimeoutError` covers request timeouts.
- `HttpClientNetworkError` covers transport-level failures.
- `HttpClientResponseError` covers non-2xx responses and content-type
  violations.
- `HttpClientSizeLimitError` covers bodies that exceed the limit.
- `HttpClientRateLimitError` covers local rate-limit exhaustion.

Adapters translate these into the provider-layer error hierarchy. The
HTTP client never raises provider-layer exceptions.

## Crossref Adapter

The Crossref adapter lives in
`academic_platform.infrastructure.search_providers.crossref`. It
implements the search provider interface against Crossref's REST API and
is the first concrete provider the application ships.

### Components

- **`CrossrefUrlBuilder`** — converts a provider-neutral `SearchRequest`
  into the Crossref endpoint URL and parameter dictionary. Filters that
  Crossref does not support are omitted; the orchestration layer applies
  them locally.
- **`CrossrefResponseParser`** — converts Crossref's response JSON into
  provider-neutral `SearchHit` objects. The parser is defensive:
  individual malformed items are skipped with a warning; the parser
  raises `ProviderResponseError` only when the top-level structure is
  not what Crossref documents.
- **`CrossrefAdapter`** — the adapter itself. It consumes the shared
  HTTP client and translates HTTP client exceptions into provider-layer
  exceptions.
- **Registration** — the adapter is registered with the default provider
  registry when the search providers package is imported. Registration
  uses the registry's factory API so that the adapter is constructed
  with the source's configuration.

### Crossref-specific notes

- The `query` parameter carries the free-text query. Crossref requires a
  query or a filter for search; the adapter rejects requests that carry
  neither.
- Pagination uses `rows` and `offset`. Crossref does not support cursor
  pagination.
- Filters are combined with commas in a single `filter` parameter.
  Year ranges use `from-pub-date` and `until-pub-date`. DOI lookup uses
  `doi:`. Language filtering uses `language:`.
- Sorting supports relevance (the default) and deposit date. The adapter
  maps the application's `date_desc` and `date_asc` sort modes to
  Crossref's `deposited` sort key and reverses the results when
  ascending order was requested.
- Abstracts are returned as JATS XML. The parser strips tags and decodes
  entities; this is lossy and is documented on the parser.
- Open-access status is detected from the presence of a Creative Commons
  license URL. Crossref does not expose a dedicated open-access flag;
  the adapter's descriptor declares this limitation.

### Error handling

The adapter translates HTTP client exceptions into provider-layer
exceptions:

- `HttpClientTimeoutError` → `ProviderUnavailableError`.
- `HttpClientRateLimitError` → `ProviderUnavailableError`.
- `HttpClientNetworkError` → `ProviderRequestError`.
- `HttpClientConfigurationError` → `ProviderRequestError`.
- `HttpClientResponseError` → `ProviderResponseError`.

Callers see only `ProviderError` subclasses.

### Registration timing

The search providers package imports the Crossref registration module at
the end of its own module body. The import is deferred to avoid a
circular import: the adapter imports from the adapter interface module in
the same package. Import failures are logged and tolerated; the null
adapter remains available and the search page reports the absence of a
provider.

## OpenAlex Adapter

The OpenAlex adapter lives in
`academic_platform.infrastructure.search_providers.openalex`. It
implements the search provider interface against OpenAlex's REST API.

### Components

- **`OpenAlexUrlBuilder`** — converts a provider-neutral `SearchRequest`
  into the OpenAlex endpoint URL and parameter dictionary. Filters that
  OpenAlex does not support are omitted; the orchestration layer applies
  them locally.
- **`OpenAlexResponseParser`** — converts OpenAlex's response JSON into
  provider-neutral `SearchHit` objects. Individual malformed items are
  skipped with a warning; the parser raises `ProviderResponseError` only
  when the top-level structure is not what OpenAlex documents.
- **`OpenAlexAdapter`** — the adapter itself. It consumes the shared
  HTTP client and translates HTTP client exceptions into provider-layer
  exceptions.
- **Registration** — the adapter is registered with the default provider
  registry when the search providers package is imported. Registration
  uses the registry's factory API so that the adapter is constructed
  with the source's configuration.

### OpenAlex-specific notes

- The `search` parameter carries the free-text query. Filter expressions
  use the `filter` parameter with comma-separated clauses.
- Pagination supports both page-based and cursor-based access. The
  adapter propagates the `next_cursor` from the response so that callers
  can continue a search without re-executing the same query. The URL
  builder emits `cursor` when a cursor is supplied and `page` otherwise.
- Filters supported by OpenAlex and exposed by the application:
  `from_publication_date`, `to_publication_date`, `doi`, `is_oa`, and
  `language`.
- Sorting supports relevance (the default) and publication date. The
  adapter maps the application's `date_desc` to
  `publication_date:desc` and `date_asc` to `publication_date:asc`. The
  default relevance sort omits the `sort` parameter because OpenAlex
  sorts by relevance implicitly.
- Abstracts are returned as an inverted index. The parser reconstructs
  the plain-text abstract by placing each token at its position. The
  reconstruction preserves word order but loses formatting.
- Open-access status is exposed through the `open_access.is_oa` field.
  The adapter declares the open-access filter as supported.
- A contact email may be configured for the source. When present, the
  adapter includes a `mailto` parameter, which places requests in
  OpenAlex's polite pool.

### Error handling

The adapter translates HTTP client exceptions into provider-layer
exceptions using the same mapping as the Crossref adapter. Callers see
only `ProviderError` subclasses.

### Registration timing

The search providers package imports the OpenAlex registration module at
the end of its own module body, immediately after the Crossref
registration import. Import failures are logged and tolerated; the null
adapter remains available and the search page reports the absence of a
provider.

## Semantic Scholar Adapter

The Semantic Scholar adapter lives in
`academic_platform.infrastructure.search_providers.semantic_scholar`. It
implements the search provider interface against Semantic Scholar's
Graph API.

### Components

- **`SemanticScholarUrlBuilder`** — converts a provider-neutral
  `SearchRequest` into the Semantic Scholar endpoint URL and parameter
  dictionary. The builder emits the `query`, `limit`, `offset`, `year`,
  and `fields` parameters. It does not emit a `sort` parameter because
  the relevance-search endpoint does not support one.
- **`SemanticScholarResponseParser`** — converts Semantic Scholar's
  response JSON into provider-neutral `SearchHit` objects. The parser
  extracts the DOI from `externalIds` when present. It raises
  `ProviderResponseError` only when the top-level structure is not what
  Semantic Scholar documents.
- **`SemanticScholarAdapter`** — the adapter itself. It consumes the
  shared HTTP client and translates HTTP client exceptions into
  provider-layer exceptions. It applies the requested sort order
  locally because the endpoint does not support sorting.
- **Registration** — the adapter is registered with the default provider
  registry when the search providers package is imported. Registration
  uses the registry's factory API so that the adapter is constructed
  with the source's configuration.

### Semantic Scholar-specific notes

- The `query` parameter carries the free-text query. Semantic Scholar
  requires a query on the relevance-search endpoint used here.
- The `year` parameter supports three forms: `YYYY`, `YYYY-YYYY`, and
  `YYYY-` / `-YYYY`. The builder emits the narrowest form the request
  supports.
- The `fields` parameter is required to receive the bibliographic fields
  the application uses. The builder emits a stable field list.
- Filtering by open-access PDF and by venue is not supported on the
  relevance-search endpoint. The adapter declares the corresponding
  filter support flags as false.
- An API key raises the provider's rate limit. When a credential
  reference is configured, the factory passes the resolved secret to the
  HTTP client, which injects it as an `x-api-key` header. The adapter
  itself never reads the secret.
- Sorting is applied locally. The adapter reverses the response when
  `date_asc` is requested.

### Error handling

The adapter translates HTTP client exceptions into provider-layer
exceptions using the same mapping as the Crossref and OpenAlex adapters.
Callers see only `ProviderError` subclasses.

### Registration timing

The search providers package imports the Semantic Scholar registration
module at the end of its own module body, immediately after the OpenAlex
registration import. Import failures are logged and tolerated; the null
adapter remains available and the search page reports the absence of a
provider.

## PubMed Adapter

The PubMed adapter lives in
`academic_platform.infrastructure.search_providers.pubmed`. It
implements the search provider interface against the NCBI E-utilities
API.

### Components

- **`PubMedUrlBuilder`** — constructs the esearch, esummary, and efetch
  URLs and parameters. Year filters map to `mindate`/`maxdate` with
  `datetype=pdat`. The identifier list is comma-separated.
- **`PubMedResponseParser`** — parses the three response shapes into the
  data the adapter needs. The parser exposes `parse_search`,
  `parse_summary`, and `parse_abstracts`; it also exposes
  `merge_abstracts` to combine summary hits with fetched abstracts.
- **`PubMedAdapter`** — the adapter itself. It composes esearch,
  esummary, and efetch internally. When the abstract fetch fails, hits
  are returned without abstracts rather than failing the search.
- **Registration** — the adapter is registered with the default provider
  registry when the search providers package is imported.

### PubMed-specific notes

- Search is a two-step process. `esearch` returns identifiers and a
  total count; `esummary` returns bibliographic metadata for those
  identifiers; `efetch` returns abstracts.
- The `retmode` parameter is always `json`. The application consumes the
  JSON representation.
- Year filters use `mindate`, `maxdate`, and `datetype=pdat`. When only
  one bound is supplied, only the corresponding parameter is emitted.
- The `retmax` parameter is clamped to the provider's maximum (10000).
- PubMed does not expose citation counts or an open-access flag through
  the endpoints used here. The adapter declares the corresponding
  capabilities as false.
- Abstracts are fetched in a separate efetch call. When the call fails,
  the adapter logs the failure and returns hits without abstracts rather
  than failing the whole search. Abstracts are optional.
- The adapter declares `fetch_abstracts` as a configurable flag. When
  disabled, the adapter skips the efetch call entirely and returns hits
  with empty abstracts.

### Error handling

The adapter translates HTTP client exceptions into provider-layer
exceptions using the same mapping as the previously implemented
adapters. Callers see only `ProviderError` subclasses.

### Registration timing

The search providers package imports the PubMed registration module at
the end of its own module body, immediately after the Semantic Scholar
registration import. Import failures are logged and tolerated; the null
adapter remains available and the search page reports the absence of a
provider.

## Europe PMC Adapter

The Europe PMC adapter lives in
`academic_platform.infrastructure.search_providers.europe_pmc`. It
implements the search provider interface against the Europe PMC REST
API.

### Components

- **`EuropePmcUrlBuilder`** — constructs the search URL and parameters.
  The builder composes a Europe PMC search-query string from the
  application's filters: DOI, year range, language, and open-access
  flags are expressed as query clauses rather than as separate
  parameters because the search endpoint does not expose dedicated
  parameters.
- **`EuropePmcResponseParser`** — parses the response into
  provider-neutral hits. Authors are extracted from the
  comma-separated `authorString` when present; the parser falls back to
  the structured `authorList` when the string is missing.
- **`EuropePmcAdapter`** — the adapter itself. It propagates the
  `nextCursorMark` from the response through the provider-neutral
  response.
- **Registration** — the adapter is registered with the default provider
  registry when the search providers package is imported.

### Europe PMC-specific notes

- The `query` parameter carries the free-text query and the filter
  clauses. Europe PMC's search syntax combines clauses with `AND`.
- Pagination is cursor-based. The initial request omits `cursorMark`;
  subsequent requests pass the cursor returned by the previous response.
  The adapter does not emit page numbers.
- The `resultType=core` value requests the extended representation that
  includes abstracts and bibliographic metadata in a single call.
- Sorting uses the `sort` parameter with `P_PDATE_D desc` or
  `P_PDATE_D asc` for publication date ordering. Relevance ordering is
  the provider's default and does not require a `sort` parameter.
- Open-access status is exposed through the `isOpenAccess` field.
  The adapter declares the open-access filter as supported.
- Citation counts are exposed through the `citedByCount` field when the
  `resultType=core` representation is used.
- The `pageSize` parameter is clamped to the provider's maximum (1000).

### Error handling

The adapter translates HTTP client exceptions into provider-layer
exceptions using the same mapping as the previously implemented
adapters. Callers see only `ProviderError` subclasses.

### Registration timing

The search providers package imports the Europe PMC registration module
at the end of its own module body, immediately after the PubMed
registration import. Import failures are logged and tolerated; the null
adapter remains available and the search page reports the absence of a
provider.

## arXiv Adapter

The arXiv adapter lives in
`academic_platform.infrastructure.search_providers.arxiv`. It implements
the search provider interface against arXiv's Atom API.

### Components

- **`ArxivUrlBuilder`** — constructs the query URL and parameters. The
  builder composes a `search_query` field expression from the
  application's filters: free-text queries use the `all:` prefix, author
  filters use the `au:` prefix, and year ranges use the
  `submittedDate:[...]` field. Filters that arXiv does not support are
  omitted; the orchestration layer applies them locally.
- **`ArxivResponseParser`** — parses the Atom XML response into
  provider-neutral hits. The parser uses the standard library's
  `xml.etree.ElementTree` and handles the Atom, OpenSearch, and arXiv
  namespaces explicitly.
- **`ArxivAdapter`** — the adapter itself. It consumes the shared HTTP
  client and translates HTTP client exceptions into provider-layer
  exceptions. Because arXiv returns `application/atom+xml`, the
  adapter's factory extends the HTTP client's content-type allow-list to
  include the Atom media type.
- **Registration** — the adapter is registered with the default provider
  registry when the search providers package is imported.

### arXiv-specific notes

- The `search_query` parameter carries the field expression. arXiv
  combines clauses with `AND`. Free-text queries use `all:`; author
  filters use `au:`; date ranges use `submittedDate:`.
- Pagination uses `start` (offset) and `max_results` (limit). arXiv does
  not support cursor pagination. The `max_results` value is clamped to
  the provider's maximum (2000).
- Sorting uses `sortBy` with `relevance` or `submittedDate`, and
  `sortOrder` with `ascending` or `descending`. The adapter maps the
  application's `date_asc` and `date_desc` modes to the
  `submittedDate` sort key with the appropriate order.
- DOI lookup is not supported by the query endpoint. The builder omits
  the corresponding clause; the orchestration layer applies the filter
  locally.
- Preprints on arXiv are openly available. The adapter reports
  `is_open_access=True` for every hit.
- Abstracts are returned in the `summary` element. The parser normalizes
  whitespace and returns plain text.
- The identifier is extracted from the entry's `id` URL. Entries whose
  `id` is missing are skipped.
- The primary category is extracted from the `arxiv:primary_category`
  element, with a fallback to the first top-level `category` element.

### Content-type handling

arXiv returns responses with the `application/atom+xml` media type. The
shared HTTP client's default content-type allow-list does not include
this media type; the arXiv factory therefore constructs the client with
an extended allow-list. This is a documented exception to the default
policy and is scoped to the arXiv adapter only.

### Error handling

The adapter translates HTTP client exceptions into provider-layer
exceptions using the same mapping as the previously implemented
adapters. Callers see only `ProviderError` subclasses.

### Registration timing

The search providers package imports the arXiv registration module at
the end of its own module body, immediately after the Europe PMC
registration import. Import failures are logged and tolerated; the null
adapter remains available and the search page reports the absence of a
provider.

## Publication Normalization and Deduplication

The publication normalization subsystem lives in
`academic_platform.application.publications`. It converts the
provider-neutral `SearchHit` objects returned by adapters into the
application's canonical `CanonicalPublication` representation, and it
deduplicates the results across providers.

### Components

- **`PublicationKey`** — a stable identifier derived from a DOI or a
  provider identifier. The key has the form `doi:<lowercase-doi>` or
  `<provider>:<identifier>`. It never derives from a title or from
  author names.
- **`CanonicalPublication`** — an immutable value object. Merging two
  publications produces a new instance; the originals are not modified.
  Missing fields are filled from the other publication; existing fields
  are preserved.
- **`PublicationNormalizer`** — converts a `SearchHit` into a
  `CanonicalPublication`. The normalizer is deterministic: the same hit
  produces the same publication on every call. It never invents data.
- **`PublicationDeduplicator`** — merges canonical publications that
  refer to the same underlying work. Deduplication is conservative:
  publications are considered duplicates only when they share a
  normalized DOI, or when their keys are equal.
- **`PublicationService`** — the application service that normalizes
  hits, deduplicates them, and persists the result through the
  repository layer.

### Key derivation

The key is derived in the following order:

1. When the hit has a DOI, the key is `doi:<lowercase-doi>`. DOI
   prefixes such as `https://doi.org/` and `doi:` are stripped before
   normalization.
2. When the hit has no DOI but has a provider key and a provider
   identifier, the key is `<provider>:<identifier>`.
3. When neither is available, the hit cannot be normalized. It is
   skipped and reported in the normalization result.

### Deduplication rules

Deduplication uses two rules, applied in order:

1. **DOI equality.** Two publications with the same normalized DOI are
   duplicates, regardless of how their keys were constructed.
2. **Key equality.** Two publications with the same key are duplicates.
   Key equality reflects equality of the underlying identifier; a key
   is derived from a DOI or from a provider identifier, never from a
   title.

Title-only matching is not performed. Titles are not reliable
identifiers: distinct works can share titles, and the same work can
appear under different titles in different sources.

### Persistence

`PublicationService.persist` is idempotent with respect to DOI and key.
Persisting the same publication twice updates the existing row rather
than creating a second one. When an existing row already carries a
field, the service preserves it; only missing fields are filled. This
makes the operation safe to repeat after a user has corrected a field
through the UI.

The service records every source provider that has returned a
publication. The provider list is a sorted, de-duplicated set.

### Integration

The search source service exposes the publication service through a
`publications` property. The orchestration layer obtains the service
from the same place it obtains the source service, so that a single
repository manager backs both.

### Error handling

- `PublicationNormalizationError` is the base class for normalization
  failures.
- `PublicationKeyError` is raised when a hit cannot produce a key.
- `PublicationPersistenceError` is raised when a normalized publication
  cannot be persisted.

## Search Orchestration Service

The search orchestration service lives in
`academic_platform.application.search_orchestration`. It coordinates the
execution of a provider-neutral search request across every enabled and
selected source, aggregates the results, deduplicates the merged hits,
and — when requested — persists the outcome.

### Components

- **`SourceSelection`** — describes which sources a search targets.
  Either every enabled source or an explicit set of source keys.
- **`SearchOrchestrationRequest`** — combines the provider-neutral
  `SearchRequest` with the source selection, the concurrency policy, and
  the persistence policy. It validates its values at construction; an
  empty search, an empty explicit selection, or an out-of-range
  concurrency value is rejected.
- **`SourceOutcome`** and **`SourceOutcomeStatus`** — describe the
  outcome of executing a single source. The status enumerates the
  outcomes: `OK`, `FAILED`, `SKIPPED`, `DISABLED`.
- **`SearchOrchestrationResponse`** — carries the aggregated outcomes,
  hits, canonical publications, deduplication result, and the
  identifiers of any persisted session and result rows. A `partial` flag
  is True when at least one source succeeded and at least one source
  failed.
- **`SearchOrchestrator`** — the application service.

### Concurrency

Adapters are executed on a bounded thread pool whose size is driven by
the request's `max_concurrency`. Each adapter runs on its own thread;
the orchestrator does not share mutable state across threads beyond the
future collection. Failures are isolated per source; a failure in one
adapter never aborts the whole search.

### Persistence

When `record_session` is True, the orchestrator records:

- One `SearchSession` row carrying the query, the scope, the per-source
  reports, the result count, and the partial flag.
- One `Publication` row per deduplicated publication. The publication
  service is idempotent with respect to DOI and key, so re-running a
  search does not create duplicate publication rows.
- One `SearchResult` row per persisted publication, carrying the rank
  and the source URL.

Session and result rows are recorded only after the search has
completed, so a failure during search never leaves a partial session in
the database.

### Error handling

- `SearchOrchestrationError` is the base class for orchestration
  failures.
- `SearchOrchestrationConfigurationError` is raised when the request is
  misconfigured — for example, when the explicit selection names no
  enabled source.
- Adapter failures are recorded as `SourceOutcome` entries with status
  `FAILED`. They are not raised. The orchestrator only raises for
  configuration errors and for persistence failures.

### Deduplication

Hits returned by different adapters are merged in the order sources were
resolved. Deduplication is applied after merging, using the same
conservative rules as the publication service: normalized DOI equality
or key equality.

## Discover Page Wiring

The Discover page is wired to the search orchestration service through
`OrchestrationSearchController`. The controller implements the
`SearchController` protocol introduced in Phase 10 and delegates to the
orchestrator for remote searches. Local searches continue to be reported
as unavailable until the library's full-text index is populated.

### Controller composition

The controller is constructed with two callables:

- `orchestrator_factory` — returns a `SearchOrchestrator` bound to a
  fresh unit of work.
- `source_service_factory` — returns a `SearchSourceService` bound to
  the same unit of work.

The two callables are the same in practice; the controller invokes the
factory once per search so that each search runs in its own transaction
boundary. The factory is provided by the main window through its
`search_orchestrator_factory` property.

### Background execution

Searches are executed on a background thread through `SearchWorkerHandle`.
The handle owns a `QThread` and a `SearchWorker`; it is created per
search and discarded once the completion callback has been invoked. The
page holds a list of active handles so that threads survive until their
work completes.

The worker emits a `SearchResponse` on completion. Errors raised by the
controller are caught at the worker boundary and returned as a failed
source report. The worker never propagates an exception to the Qt event
loop.

### Focus and rendering

The page renders each surface independently when its search completes.
The tab focus is determined by the last scope:

- `local` focuses the local surface.
- `remote` focuses the remote surface.
- `all` focuses the local surface if it has results, otherwise the
  remote surface.

Because results arrive asynchronously, the focus decision is made from
the last scope and the entry count at the time of the focus call. The
order in which surfaces complete is not significant.

### Orchestrator factory

The main window builds the orchestrator factory during construction,
before pages are registered. The factory opens a fresh per-call
repository manager (`_PerCallManager`) that behaves like a
`RepositoryManager` but constructs its repositories against a
short-lived session. Each search therefore runs in its own transaction
boundary. The factory is exposed as `search_orchestrator_factory` so
that other components can obtain an orchestrator without reaching into
the window's private attributes.

## Source Management UI

The source management dialog lives in
`academic_platform.ui.pages.settings.sources_dialog`. It is opened from
two places:

- The Settings page's Search tab, through the "Manage sources…" button.
- The Discover page, through the "Manage sources…" button.

Both entry points obtain the application-layer `SearchSourceService`
from the main window's `search_source_service` property. The dialog
never reads the database directly.

### Actions

The dialog exposes the following actions:

- **Add source** — opens a form dialog collecting the source's key,
  provider key, display name, base URL, endpoint, timeout, and result
  limit. The form validates each field before the submit button is
  enabled. The source is created with `source_type="user_defined"`.
- **Edit source** — opens a form dialog prefilled with the source's
  current values. Only the fields that may be changed without risking
  the source's identity are exposed: display name, base URL, endpoint,
  timeout, and result limit. The key and the provider key are not
  editable.
- **Test** — executes a synchronous connectivity test through the
  service. The dialog displays a busy cursor while the test runs. A
  successful test publishes a success notification; a failure displays
  an error dialog with the provider's message.
- **Enable / disable** — toggles the source's enabled state through the
  service. The change is persisted immediately.
- **Remove** — removes a user-defined source after a confirmation
  prompt. Built-in sources may be disabled but not removed; the Remove
  button is hidden for them.

### Change propagation

The dialog emits `sources_changed` after any persisted change. Both
parent surfaces connect this signal to their own refresh method:

- The Search tab refreshes its configured sources panel.
- The Discover page refreshes its sources hint.

### Source list rendering

The dialog renders one `SearchSourceRow` per source. The row's filter
labels are derived from the source's declared capabilities: pagination,
cursor pagination, abstract availability, citation counts, and open
access flag. The row's last-test indicator reflects the source's
`last_tested_at` and `last_error` fields.

### Validation

Form validation is provided by the form dialog's validator callables.
The key validator enforces the same rules as the persistence schema:
lowercase ASCII letters, digits, hyphens, and underscores, starting
with a letter or digit. The integer validators enforce the same ranges
as the source configuration value object. The service performs a second
validation pass before persisting; a validation failure is displayed as
a source-rejected error dialog listing every issue.

## Saved Searches

Saved searches are stored in the `saved_search_query` table and managed
by `academic_platform.application.saved_searches.SavedSearchService`.
The service validates every payload through the persistence schema and
never reads the database directly.

### Model

A saved search carries a stable key, an optional name, the query text,
the scope (`all`, `local`, or `remote`), a filter payload, a target source
set, and a timestamp of the last execution. The display label prefers the
name, falls back to the query text, and finally to the key.

### Integration with the orchestrator

`build_request_from_saved_search` converts a saved search into a
`SearchOrchestrationRequest`. The saved search's `source_keys` are
honoured when present; otherwise every enabled source is targeted. The
saved search's filter payload populates the provider-neutral
`SearchRequest` fields the application supports.

### Presentation

The `SavedSearchesPanel` component embeds the saved-search list in the
Discover page. It exposes Load, Run, Rename, and Remove actions for each
saved search. Loading populates the search bar without executing;
running executes the search immediately.

The Discover page's "Save this search…" button prompts for a name and
saves the current search bar state. The key is derived from a SHA-1
digest of the query and scope; saving the same query twice is
idempotent from the user's perspective because the second save is
reported as a duplicate.

## Phase C Acceptance

Phase C is verified end to end by the harness described in
`docs/phases/phase_c_acceptance.md`. The harness exercises:

- The catalog installer.
- The provider registry.
- The orchestrator's deduplication logic.
- The orchestrator's partial-failure handling.
- The saved-search service.
- Session recording.
- Source management.
- Publication idempotence.

The validator uses deterministic stub adapters registered with a
private registry. It never contacts a real provider.

## File Storage Abstraction

`academic_platform.infrastructure.file_storage` is the only component in
the application that performs filesystem operations on document assets.
It supports two storage modes:

- **Managed copy.** The file is copied into the managed library root.
  The original is left untouched. Managed copies are the default because
  they make the library self-contained and protect against the user
  moving or deleting the original file.
- **Referenced file.** The file remains in place and the application
  stores a reference to it. Missing files are detected and reported; the
  application never deletes a referenced file.

### Configuration

`FileStorageConfig` is immutable. It carries the managed root, the
maximum file size, and the streaming chunk size. It validates its values
at construction. The managed root is created on first use.

### Service

`FileStorage` provides:

- `compute_checksum(path)` — streamed SHA-256 checksum.
- `import_managed_copy(source, overwrite=False)` — atomic copy into the
  managed library. The managed filename is derived from the checksum so
  that identical files resolve to the same location.
- `record_referenced_file(source)` — validate a file that remains in
  place and return its record.
- `verify_managed_copy(location, expected_checksum)` — return True when
  a managed file matches its expected checksum.
- `verify_referenced_file(location)` — return True when a referenced
  file is present and readable.
- `delete_managed_copy(location)` — delete a file under the managed
  root. Refuses to delete paths outside the root.

### Design rules

- **Streaming.** Checksums and copies are computed in fixed-size chunks.
  The service never reads a whole file into memory.
- **Atomic writes.** Managed copies use a temporary file in the same
  directory and an atomic rename. A crash during the copy leaves no
  partial file under the managed root.
- **No silent overwrites.** A caller that intends to replace a file must
  pass `overwrite=True`. Without it, an existing target with a different
  checksum raises `FileStorageExistsError`.
- **No writes outside the managed root.** The service refuses to delete
  a path outside the managed root. Deletion of referenced files is not
  offered.
- **No network access.** The service never performs network operations
  and never spawns subprocesses.
- **Fan-out layout.** Managed files are placed under
  `<root>/<hex[:2]>/<hex[2:4]>/<checksum>.<ext>`. The two-level fan-out
  keeps any single directory from accumulating too many entries.
- **Extension preservation.** The managed filename preserves the
  original extension when it is short and alphanumeric. Files without a
  usable extension receive a neutral `.bin` suffix.

### Integration

The application layer uses the service through a narrow interface. The
presentation layer never touches the filesystem directly. The document
repository records the managed location or the referenced path along
with the checksum returned by the service; the service is the only
component that reads, writes, or deletes the file.

## Library Import

The library import subsystem is split between an application-layer
coordinator and a presentation-layer dialog.

### Application service

`academic_platform.application.library_import.ImportCoordinator`
provides two methods:

- `prepare(sources, mode)` — validate the selected paths and return an
  `ImportPlan`.
- `import_files(plan, selected_paths=None, import_duplicates=False)` —
  persist the confirmed selection.

Validation covers:

- Existence and regular-file status.
- Extension against the coordinator's supported set. At this stage the
  set contains `.pdf`.
- Size against the coordinator's maximum, which defaults to the file
  storage service's configured limit.
- Duplicate detection by checksum against the document repository's
  `find_by_checksum`.

Import delegates to the file storage service:

- Managed copy mode calls `import_managed_copy`.
- Referenced file mode calls `record_referenced_file`.

The document repository records the location, mode, size, and checksum
in a `DocumentAsset` row. The document's stable key is derived from the
checksum, so identical files resolve to the same document key. When a
document with the same key already exists, the import is a no-op and
the caller receives the existing key.

### Presentation

`academic_platform.ui.dialogs.ImportDialog` presents the plan returned
by `prepare`. It exposes:

- A file list with per-candidate state, size, and duplicate
  information.
- A storage-mode selector (`managed_copy` or `referenced_file`).
- A "re-import duplicates" toggle.
- Select all and clear actions.
- Import and cancel actions.

The dialog renders each candidate with an `ImportRow` frame. The row's
state label uses a dynamic property for styling; `ready` and
`duplicate` are distinguished from the blocked states.

### Platform picker

`academic_platform.ui.pages.library.import_helper.open_import_dialog`
opens the platform picker restricted to PDFs and, when files are
selected, opens the dialog. It is shared between pages that offer an
import action.

### Change propagation

The dialog emits `imported(ImportResult)` after a successful import.
Callers connect this signal to refresh their views and to publish
notifications.

### Design rules

- The dialog never performs validation, checksum computation, or
  filesystem operations itself. It delegates to the coordinator.
- The coordinator never reads file contents directly. It delegates
  checksum computation and file copies to the file storage service.
- The coordinator never deletes source files. The user's originals are
  left untouched in both modes.
- Duplicate detection is based on checksum, not on filename. Two files
  with the same content but different names are recognized as
  duplicates.
- Import is idempotent with respect to document key. Importing the same
  file twice creates one document record; the second import returns the
  existing key.

## PDF Text Extraction

The PDF extraction subsystem lives in
`academic_platform.infrastructure.document_processing` and
`academic_platform.application.document_extraction`. It converts a PDF
on disk into structured text, metadata, and page-level blocks.

### Infrastructure

`PdfTextExtractor` wraps PyMuPDF and returns a `PdfExtractionResult`
carrying:

- Page count and extracted page count.
- Extracted PDF metadata (title, author, subject, keywords, producer,
  creator, dates).
- Document outline (table of contents) as `(level, title, page)`
  tuples.
- Per-page text with whitespace normalized.
- Per-page text blocks with bounding boxes, ready for annotation
  anchoring in later phases.

### Configuration

`PdfExtractorConfig` is immutable. It carries:

- `max_pages` — extraction cap. A truncated extraction is recorded.
- `max_text_bytes` — byte cap on the extracted text. A truncated
  extraction is recorded.
- `normalize` — whether to normalize whitespace.
- `strict` — whether page-level failures abort the entire extraction.

### Design rules

- **Read-only.** The extractor never modifies the PDF. Files are opened
  in read-only mode; no annotations are written.
- **Streaming.** The extractor loads pages on demand and releases each
  page before moving on. The whole document is never loaded into memory.
- **Encrypted PDFs.** Encrypted PDFs are rejected with
  `PdfEncryptedError`. The application never attempts to bypass
  encryption.
- **Per-page isolation.** In non-strict mode, a page-level failure is
  recorded as a warning on the affected page; the remaining pages are
  extracted. In strict mode the first failure aborts the extraction.
- **Deterministic normalization.** Whitespace normalization is
  documented on the `_normalize_whitespace` helper and is applied
  consistently.

### Application service

`DocumentExtractionService` reads a `DocumentAsset` by key, opens its
file through the extractor, and persists the result:

- Every text-bearing page becomes a `DocumentChunk` row. The previous
  chunks for the document are replaced in the same transaction.
- PDF embedded metadata is written to `DocumentMetadata`. A metadata
  row that has been reviewed by the user is preserved.
- The document asset's `processing_state`, `processing_version`,
  `page_count`, and `last_error` are updated. Success advances the
  state to `extracted` and increments the version. Failure advances the
  state to `failed` and records the error.

The service never commits. It runs inside a unit of work supplied by
the caller.

## PDF Metadata Extraction

`PdfMetadataExtractor` produces normalized bibliographic metadata from
a `PdfExtractionResult` (or directly from a PDF path). It combines
three sources of evidence:

1. The PDF's embedded metadata dictionary.
2. The first N pages of text (front matter).
3. Pattern matching for DOIs, arXiv identifiers, years, and venues.

Each extracted field carries a confidence value in `[0.0, 1.0]`. Fields
that could not be extracted are left `None` with confidence 0.0. The
extractor never invents values.

### Field heuristics

- **Title.** Preferred source is the embedded metadata dictionary. A
  set of placeholder titles is rejected (for example, `Microsoft Word -
  paper.doc`, `untitled`, and file names with common document
  extensions). When the embedded title is absent or rejected, the
  extractor selects the earliest front-matter line that looks like a
  title: reasonable length, predominantly alphabetic, not ending with a
  colon or a period, not a running head.
- **Authors.** Preferred source is the embedded `author` field. The
  extractor accepts semicolons, "and", and comma separators. Tokens
  that look like an institution (they contain "university", "institute",
  "department", or "school") are rejected. When the embedded list is
  absent, the extractor inspects the front matter for a line that looks
  like an author list: it contains at least one separator and at least
  two capitalized names.
- **Year.** Preferred source is the PDF's creation or modification date.
  The extractor takes the highest four-digit year found in the front
  matter when the embedded dates are absent.
- **Venue.** Preferred source is the embedded `subject` when it
  contains "journal", "conference", or "proceedings". Otherwise the
  extractor looks for a front-matter line containing "proceedings",
  "journal", "conference", "workshop", or "symposium".
- **DOI.** Matches the canonical `10.<registrant>/<suffix>` form. The
  extractor strips trailing punctuation and lowercases the value.
- **arXiv identifier.** Matches the `arXiv:YYMM.NNNNN[v#]` form. The
  helper `extract_arxiv_identifier` is exposed for callers that want to
  inspect front matter independently.
- **Abstract.** Found after an "Abstract" or "Summary" marker. The
  extractor stops at the first paragraph that begins with a section
  marker such as "Introduction", "Keywords", or "1.".
- **Language.** Only extracted from the embedded metadata when the value
  matches a BCP 47 subset pattern (two-letter code with an optional
  regional subtag).

### Integration

`DocumentExtractionService` uses the extractor in its
`_persist_metadata` step. The service computes an overall confidence as
the arithmetic mean of the per-field confidences for fields that were
extracted. This value is stored in `DocumentMetadata.extraction_confidence`.
The extraction method is recorded as `pdf_heuristic` to distinguish it
from embedded-metadata-only extraction performed by an earlier phase.

### Design rules

- The extractor is deterministic. The same PDF produces the same result
  on every run.
- The extractor never modifies the PDF.
- The extractor never invents a value. A field that cannot be extracted
  is left `None`.
- Confidence values reflect the reliability of the evidence, not the
  size of the field. Fields from the embedded metadata dictionary carry
  higher confidence than fields inferred from the front matter.
- The extractor operates on a `PdfExtractionResult` when one is
  available; otherwise it runs the PDF text extractor itself.
- Placeholder titles from common office tools are rejected rather than
  stored.

## Duplicate Detection

The duplicate detection subsystem lives in
`academic_platform.application.deduplication`. It provides a
policy-driven detector that evaluates a candidate document against the
existing library.

### Signals

The detector evaluates three signals in order:

1. **Checksum equality.** Decisive. When the candidate's SHA-256
   checksum matches an existing document, the candidate is a duplicate
   regardless of other signals. Byte-identical files are the same file.
2. **DOI equality.** Strong but not decisive. When the candidate's DOI
   matches an existing publication, the candidate is a duplicate only
   when the metadata agrees (title or authors match). A metadata
   extraction error that produces a spurious DOI does not trigger a
   false positive.
3. **Conservative metadata equality.** Fallback. The detector compares
   the normalized title and, when the policy requires it, the
   normalized author list. Title-only matching is enabled only when the
   policy explicitly disables the author requirement.

### Policy

`DuplicatePolicy` is immutable. It carries:

- Signal toggles: `use_checksum`, `use_doi`, `use_metadata`.
- `require_author_match` — whether metadata matches require authors.
- `allow_year_difference` — whether a one-year difference is accepted.
- `metadata_candidate_limit` — bound on the metadata fallback scan.

The policy rejects configurations that disable every signal.

### Normalization

Titles are normalized before comparison:

- Unicode NFKC normalization.
- Case folding.
- Punctuation removal.
- Whitespace collapse and trim.

Author lists are normalized the same way, then sorted. The order of the
author list therefore does not affect the comparison.

### Integration

`ImportCoordinator` uses the detector in its `_evaluate` step.
Candidates that the detector reports as duplicates receive the
`DUPLICATE` state and carry the detection signal, the existing document
key, and the existing checksum. The import dialog surfaces the signal
so the user understands why a file was flagged.

### Design rules

- Checksum equality is decisive. The detector never overrides it.
- DOI equality is decisive only when the metadata agrees.
- Title-only matching is disabled by default. Distinct works can share
  titles.
- The detector never merges existing documents. It reports a candidate
  as a duplicate of an existing document; merging rows is a separate
  operation that is not implemented at this stage.
- The detector is deterministic. The same candidate and library produce
  the same decision on every run.
- The detector exposes each signal match it found so the presentation
  layer can explain the decision.

## OCR Integration

The OCR subsystem lives in
`academic_platform.infrastructure.document_processing` (extractor,
configuration, errors) and integrates with the document extraction
service.

### Extractor

`PdfOcrExtractor` renders each PDF page to a raster image through
PyMuPDF and passes the image to Tesseract through the `pytesseract`
wrapper. It returns a `PdfExtractionResult` that is compatible with the
non-OCR extractor's output, so downstream consumers do not need to
distinguish OCR-produced text from native text.

### Configuration

`OcrConfig` is immutable. It carries:

- `language` (Tesseract language code, default `eng`).
- `languages` (optional tuple; when present, joined with `+`).
- `dpi` (rendering resolution; default 300).
- `tesseract_config` (extra Tesseract parameters).
- `min_characters_per_page` (threshold for considering a page
  meaningful; default 16).
- `max_pages` (extraction cap; `None` processes every page).
- `timeout_seconds` (per-page timeout passed to Tesseract).
- `strict` (page failures abort the extraction when True).
- `preserve_blocks` (word-level bounding boxes are emitted when True).

### Availability probe

`PdfOcrExtractor.probe_availability` reports whether the backend is
usable. It never raises. A missing `pytesseract` wrapper or a missing
Tesseract binary is reported through `OcrAvailability.available = False`
with an actionable message. Language packs are listed when Tesseract
exposes them.

### Integration

`DocumentExtractionService` decides whether to run OCR based on the
non-OCR extraction result:

- A document whose pages produced no text at all needs OCR.
- A document whose average extracted text per page is fewer than 16
  characters needs OCR.

When OCR runs:

- The document asset's `ocr_state` is set to `completed` on success or
  `failed` on any OCR error.
- When OCR is enabled but not needed for a document, the state is set
  to `not_required`.

OCR runs only when the library's `ocr_enabled` setting is True. When
the setting is False, the service never invokes the OCR extractor.

### Design rules

- The extractor never modifies the source PDF. Rasters are held in
  memory and released as soon as Tesseract returns.
- Pages are processed one at a time. Memory usage stays bounded for
  long documents.
- In non-strict mode, page-level failures are recorded as warnings on
  the affected page and extraction continues. In strict mode the first
  failure aborts the extraction.
- The extractor never invents text. A page whose OCR output is shorter
  than `min_characters_per_page` is recorded with its actual text and a
  warning noting that OCR produced very little text.
- The extractor never bypasses a requested language. A missing language
  pack raises `OcrLanguageError` before any page is processed.
- The application never silently fails when Tesseract is unavailable.
  The extraction service records the failure state and surfaces the
  warning to the caller.

## Full-Text Search (FTS5)

The full-text search subsystem lives in
`academic_platform.infrastructure.full_text_search` and uses SQLite's
FTS5 virtual tables. It provides local search over document chunks,
publication metadata, and user annotations.

### Virtual tables

Three FTS5 virtual tables are declared:

- `document_fts` — indexed document chunk content with `document_key`,
  `chunk_index`, `page_number`, `title`, `authors`, and `content`.
- `publication_fts` — indexed publication metadata with
  `publication_key`, `title`, `authors`, `abstract`, and `venue`.
- `note_fts` — indexed annotation content with `document_key`,
  `annotation_id`, `page_number`, and `content`.

The table names and columns are declared once in
`academic_platform.infrastructure.database.models.fts` and consumed by
the indexer, the query service, the rebuilder, the base metadata
registration, and the Alembic migration.

### Row identifiers

FTS5 rows are identified by their `rowid`. The indexer assigns
deterministic rowids derived from the underlying entity: a chunk's
rowid is derived from the document key and chunk index, a publication's
rowid is derived from its key, and an annotation's rowid is derived
from its identifier. This makes updates and deletions precise; the
indexer never has to scan the FTS5 table to find a row to replace.

### Indexer

`FtsIndexer` writes document, publication, and note content into the
FTS5 tables. It deletes previous rows for the target entity before
inserting new ones, so the operation is idempotent. It skips empty
content. It raises `FtsIndexError` on failure and never modifies the
primary tables.

### Query service

`FtsQueryService` executes MATCH queries against the FTS5 tables. It
supports three domains — documents, publications, and notes — and a
combined `search_all` method. Results carry the domain, the entity
identifier, the FTS5 rank, a snippet produced by FTS5's `snippet`
function, and optional page metadata.

Snippet markers (`[[` and `]]`) are inserted by FTS5. The
`FtsSnippet.plain` helper strips them. The presentation layer replaces
the markers with the UI's highlight styling.

### Rebuilder

`FtsRebuilder` reconstructs the FTS5 tables from the primary tables. It
clears every FTS5 table before repopulating it, so partial indexes are
never left behind. It processes documents, publications, and notes in
separate passes. Failures on individual entities are recorded as
warnings; the rebuild continues.

### Integration

`DocumentExtractionService` updates the index after every successful
extraction. The service reads the persisted chunks and metadata,
constructs an `FtsIndexer`, and calls `index_document`. The update runs
inside the same unit of work as the extraction.

Indexing can be disabled through the `index_enabled` flag on the
service. Tests and bulk operations use this flag to avoid the index
overhead.

### Migration

Migration `0009_fts5_index` creates the three virtual tables. It is
fully reversible. Downgrading drops the tables.

## Library Page

The personal library page lives in
`academic_platform.ui.pages.library`. It replaces the placeholder page
that shipped in Phase 5 and presents the user's documents with:

- A scope-aware search bar wired to the FTS5 query service.
- A filter card that summarizes the active filter state.
- A sortable table of documents.
- A detail panel that renders the selected document's metadata and
  location.
- A context menu offering Open, Add to collection, Add to project,
  Mark as missing, Mark as present, and Remove from library.
- A header-level import action and refresh action.

### Application service

`academic_platform.application.library.LibraryService` is the page's
single data source. It exposes:

- `list_entries(filter_state, sort_field, sort_direction, offset, limit)`
  — return a `LibraryPage` of `LibraryEntry` objects.
- `get_entry(document_key)` — return a single entry.
- `count_by_state()` — return the number of documents per processing
  state.
- `extensions_present()` — return the sorted set of extensions present.
- `delete_entry(document_key)` — remove a document and its FTS5 rows.
- `mark_missing(document_key)` / `mark_present(document_key)` — toggle
  the missing flag.

Full-text search delegates to `FtsQueryService`. When the filter
carries a search term, the service resolves the FTS5 document keys and
restricts the repository query to those keys. The order of the FTS5
results is preserved.

### Presentation details

- **Debounced search.** Typing starts a short timer; the actual query
  runs when the timer fires or when the user presses Enter.
- **Sorting.** The table model exposes the columns the service can sort
  by. The service performs the sort; the model never sorts in memory.
  This keeps large libraries responsive.
- **Filters.** The page holds a `LibraryFilter` instance. Filters are
  updated explicitly (search cleared, filters reset); partial filter
  selection is delivered in a later phase.
- **Selection.** Selecting a row populates the detail panel from the
  entry alone. Loading chunks on demand is deferred to the reader.
- **Double click.** Opens the document. The reader is delivered in a
  later phase; the shell publishes an informational notification.
- **Context menu.** Offers the actions the user expects from a library
  table. Destructive actions are guarded by a confirmation prompt.

### Wiring

`MainWindow._wire_library_page` constructs a `LibraryService` from the
window's `library_service_factory`, attaches it to the page, and
attaches the import dialog factory. The page emits
`open_document_requested`, `add_to_collection_requested`, and
`add_to_project_requested`; the shell handles each signal.

### Design rules

- The page reads only through the application service. It never touches
  the database or the filesystem directly.
- The page never deletes the underlying file. Removing a document from
  the library removes the ORM row and the FTS5 rows; deleting the file
  is a separate operation performed by the file storage service when
  the user confirms it.
- The page publishes notifications through the notification service for
  actions that complete asynchronously or that require user feedback.
- The page's columns are declared in the table model. Adding a column
  is a matter of adding an entry to `COLUMNS` and a corresponding
  branch in `_display_value`.

## Document Reader Shell

The reader is a hidden destination hosted by the main window. It is not
listed in the primary navigation; the shell activates it when the user
opens a document and returns to the previous destination when the
reader emits `close_requested`.

### Application service

`academic_platform.application.document_reading.DocumentReaderService`
opens a document by key and renders pages on demand. It exposes:

- `open_document(document_key)` — return the page count and outline.
- `render_page(document_key, page_number, dpi)` — return a
  `RenderedPage` carrying PNG-encoded image bytes and page metadata.
- `page_size_points(document_key, page_number)` — return page dimensions
  without rendering.
- `close_document(document_key)` — release the document handle and
  evict its cache entries.
- `close_all()` — release every open document.

### Caching

The service caches rendered pages in a bounded LRU cache. The cache key
is `(document_key, page_number, dpi)`. The default bound is eight
pages. `close_document` evicts every entry belonging to the document.

### Rendering

Pages are rendered through PyMuPDF's `get_pixmap` at a DPI derived from
the reader's zoom level. The DPI is clamped to the range the service
accepts (36 to 600). The rendered image is encoded as PNG and handed to
the presentation layer as raw bytes; the presentation layer converts
them into a Qt pixmap.

### Reader page

`academic_platform.ui.pages.reader.ReaderPage` provides:

- A navigation bar with first/previous/next/last buttons, a page spin
  box, and a page-count label.
- A zoom combo box with preset DPI levels.
- An outline panel populated from the document's table of contents.
- A page view with a scroll area and a pixmap label.
- A reading progress bar.
- Keyboard shortcuts: Home, End, PageUp, PageDown, Left, Right, Escape.

### Wiring

`MainWindow._ensure_reader_page` constructs the reader page lazily on
first use, attaches a `DocumentReaderService`, and registers the page
under the `"reader"` identifier in the page stack. The service is
constructed from the window's library service factory; the reader and
the library share the same repository layer.

`MainWindow._on_open_document_requested` remembers the current
destination, loads the document, and switches the stack to the reader.
`MainWindow._on_reader_close_requested` returns to the remembered
destination.

### Design rules

- The reader never modifies the source PDF. Files are opened read-only.
- The reader renders one page at a time. The whole document is never
  loaded into memory.
- Page rendering is synchronous. Rendering a single page at a time is
  fast enough for interactive use; a background pipeline is delivered
  in a later phase if needed.
- The reader never disposes the document while the user is reading it.
  The document handle is released when the user closes the reader
  explicitly or opens a different document.
- The reader page participates in the shell's lifecycle contract.
  `on_activated` refreshes the current page; `on_deactivated` is a
  no-op because the reader keeps its document open while the user
  navigates elsewhere.

## Bookmarks and Annotations

Annotations are user-authored records linked to a document and its
page. The source PDF is never modified; annotations are stored as
separate rows in the `annotation` table.

### Application service

`academic_platform.application.annotations.AnnotationService` provides:

- `create_note(document_key, page_number, body, ...)`.
- `create_highlight(document_key, page_number, text_excerpt, color=..., ...)`.
- `create_bookmark(document_key, page_number, ...)`.
- `list_for_document(document_key)`.
- `list_bookmarks(document_key)`.
- `list_for_page(document_key, page_number)`.
- `get(annotation_id)`.
- `update(annotation_id, ...)` — update mutable fields only.
- `delete(annotation_id)` — delete the annotation and its FTS5 row.
- `export_to_json(document_key)` — return a JSON serialization.
- `export_to_markdown(document_key)` — return a Markdown serialization.

The service validates inputs against the persistence schema before
writing. It keeps the FTS5 note index in sync: creating or updating an
annotation re-indexes it; deleting an annotation removes its FTS5 row.
It never commits; it runs inside a unit of work supplied by the caller.

### Supported kinds and colors

- Kinds: `note`, `highlight`, `bookmark`.
- Colors: `yellow`, `green`, `blue`, `pink`.

The kinds and colors are closed enumerations enforced by the model and
by the persistence schema.

### Annotation panel

`academic_platform.ui.pages.reader.annotation_panel.AnnotationPanel` is
the reader's side panel. It provides:

- A list of the current document's annotations.
- Actions to add a note, highlight, or bookmark on the current page.
- A color picker for highlights.
- An editor for the selected annotation's body and color.
- Buttons to save and delete the selected annotation.
- Buttons to export all annotations as JSON or Markdown.

The panel is told which document and page are current by the reader
page. It emits `annotation_selected(annotation_id, page_number)` when
the user activates an annotation; the reader jumps to that page.

### Reader integration

The reader page hosts the panel as the third pane of its horizontal
splitter. The reader attaches the annotation service in
`attach_annotation_service` and refreshes the panel on document load,
page change, and document close.

### Wiring

`MainWindow._build_annotation_service_factory` provides a callable that
constructs an `AnnotationService` bound to a per-call session. The
reader page receives an instance of the service when it is first
created.

### Design rules

- Annotations are separate records. The source PDF is never modified.
- Kind cannot be changed after creation. Updating a note cannot turn it
  into a highlight or a bookmark.
- Updating an annotation re-indexes it in FTS5. Deleting an annotation
  removes its FTS5 row.
- Exports are read-only. Exporting annotations never modifies the
  database.
- Page-level and note-level text is stored as the user entered it. The
  service does not attempt to normalize prose.
- The panel never reads the database directly. It goes through the
  application service.

## In-Document Search

The in-document search subsystem lives in
`academic_platform.application.document_search`. It searches a single
document's stored chunks and returns matches with page numbers, snippet
text, and character offsets.

### Source of truth

The service reads from the `document_chunk` table. It never reads the
PDF file. Results therefore reflect exactly what the extractor, the
OCR pipeline, and the indexer produced. A page that was never extracted
will not produce matches; a page that was extracted with OCR errors
will match against the OCR text.

### Matching modes

The service supports two matching modes:

- **Literal substring.** The default. Case-insensitive unless the caller
  requests case-sensitive matching.
- **Regular expression.** Opt-in. The pattern is compiled once and
  matched against each chunk.

An invalid regular expression raises `DocumentSearchError` with a
descriptive message; the panel surfaces it to the user.

### Snippets

Snippets are produced with a configurable radius around each match.
Matched terms are wrapped in `[[` and `]]` markers so the presentation
layer can apply highlight styling without re-searching the snippet.
Newlines inside the snippet are collapsed so the snippet renders on a
single line.

### Result shape

`DocumentSearchResult` carries the document key, the query, the matches,
a `truncated` flag, and a message. Each `DocumentSearchMatch` carries
the page number, chunk index, character offsets, the snippet, and the
matched text.

### Panel

`academic_platform.ui.pages.reader.search_panel.DocumentSearchPanel`
provides:

- A query input with Enter to search.
- Case-sensitivity and regular expression toggles.
- A Clear button.
- A summary label reporting the number of matches and pages.
- A list of matches; activating one emits `match_activated(match)`.

The panel is told which document is current by the reader page. It
never reads the database or the PDF directly.

### Reader integration

The reader page hosts the panel between the navigation bar and the
main splitter. `Ctrl+F` focuses the search input. Activating a match
jumps to the match's page.

### Design rules

- The service never modifies the database or the PDF.
- The service reads the extracted chunks, not the PDF. Results match
  what the indexer and the extractor produced.
- An empty query returns an empty result. The service never searches
  the empty string.
- The match limit is enforced; the result records truncation.
- Snippet markers are `[[` and `]]`. The reader panel strips them for
  the list label; the underlying snippet retains them.
- Regular expressions are opt-in. The service never interprets a query
  as a regular expression unless the caller explicitly requests it.

## Document Linking

The document linking subsystem lives in
`academic_platform.application.document_linking`. It associates
documents with collections and projects.

### Data model

- A document is linked to a collection through a `collection_item` row
  whose `item_type` is `document` and whose `item_identifier` is the
  document key.
- A document is linked to a project through the project's linked
  collection. The service creates a project-linked collection on demand
  and reuses it across subsequent links. This keeps the association
  visible through the collections view without duplicating the
  relationship in a second table.

### Application service

`DocumentLinkingService` provides:

- `list_collection_options()` — the collections available as link
  targets.
- `list_project_options()` — the projects available as link targets.
- `links_for_document(document_key)` — the collections and projects a
  document is linked to.
- `link_document_to_collection(document_key, collection_key)`.
- `unlink_document_from_collection(document_key, collection_key)`.
- `link_document_to_project(document_key, project_key)`.
- `unlink_document_from_project(document_key, project_key)`.

The service is idempotent: adding a document that is already linked is
a no-op with `affected = 0`; removing a document that is not linked is
a no-op with `affected = 0`. It never commits; it runs inside a unit of
work supplied by the caller.

### Project-linked collections

A project-linked collection is created with the key
`project-<project-key>` and a title of the form
`<project-title> — documents`. The collection's `kind` is `project` and
its `project_id` is set to the project's identifier. The service reuses
an existing project-linked collection when one is present.

### Dialog

`academic_platform.ui.dialogs.link_document_dialog.LinkDocumentDialog`
presents two tabs — Collections and Projects — each listing the
available targets with a checkbox indicating whether the document is
currently linked. The Apply action diffs the initial state against the
user's selection and applies the difference. Failures are reported as
an aggregate error dialog and the dialog reloads its state.

The dialog emits `links_changed(document_key)` on success.

### Reader and library integration

- The reader page's header includes a "Link to…" button, enabled only
  when a document is open. The button opens the dialog.
- The library page's context menu includes "Add to collection…" and
  "Add to project…" actions. The shell handles those signals by opening
  the dialog focused on the appropriate tab.

### Design rules

- Linking is a purely relational operation. The service never resolves
  the document's file path.
- The service reuses the collection and project repositories. It never
  duplicates their logic.
- A project link is implemented through a project-linked collection.
  The service creates the collection on demand and reuses it.
- The service is idempotent. Duplicate link and unlink operations are
  no-ops.
- The dialog computes a diff between the initial state and the user's
  selection. It applies only the difference.
- Failures during apply are reported as an aggregate error and the
  dialog reloads its state so the user sees what succeeded.

## Reader → Research Assistant Handoff

The handoff subsystem packages the reader's current context into a
payload the research assistant will consume once the assistant is
implemented. It lives in
`academic_platform.application.assistant_handoff`.

### Payload

`AssistantHandoff` is an immutable payload carrying:

- The document key.
- The title, authors, year, venue, DOI, and abstract (subject to the
  user's options).
- The current page number and the document's page count.
- A bounded excerpt of the current page's extracted text.
- A list of annotation summaries.

The payload is read-only. It carries everything the assistant needs to
answer questions about the current document without additional database
access.

### Store

`HandoffStore` is a bounded, in-process store that holds the most
recent handoff per document. It is process-local; later phases that run
the assistant in a separate process will replace it with a persistent
store. The store's interface is deliberately narrow so that
replacement is straightforward.

The default store is returned by `default_handoff_store()`. It is a
process-wide singleton constructed on first use.

### Application service

`AssistantHandoffService` composes a payload from a document and stores
it. It reads metadata from the metadata repository (never re-extracting
it), reads page excerpts from the document chunks, and reads
annotation summaries from the annotation repository. The service never
commits; it writes only to the in-process store.

### Dialog

`academic_platform.ui.dialogs.assistant_handoff_dialog.AssistantHandoffDialog`
previews the payload and lets the user toggle three inclusion options:
metadata, current page excerpt, and annotations. Changing an option
rebuilds the payload so the preview always reflects the current
selection. On accept, the dialog emits `handoff_prepared(handoff)`.

### Reader integration

The reader page's header includes a "Hand off to assistant" button,
enabled only when a document is open. The button opens the dialog with
the current page.

### Design rules

- The handoff is a read-only snapshot. The service never modifies the
  document, its metadata, or its annotations.
- Metadata is read from the metadata repository, not re-extracted.
- The page excerpt is bounded. The default bound is 2000 characters; a
  truncated excerpt ends with an ellipsis.
- The store is in-process. Later phases replace it with a persistent
  store; the interface is stable.
- The dialog rebuilds the payload on every option change so the
  preview always matches the user's selection.
- The dialog emits a typed signal (`handoff_prepared`) rather than
  performing the handoff itself. Navigation to the assistant is the
  shell's responsibility and is delivered in a later phase.

## Phase D Acceptance

Phase D is verified end to end by
`scripts/validate_phase_d.py` and by
`tests/unit/test_phase_d_acceptance.py`. The harness exercises:

- The file storage abstraction (atomic copy, checksum verification,
  managed-root confinement).
- The import coordinator (validation, duplicate detection, persistence).
- The PDF extractor (page-level text, page count, blocks).
- The metadata extractor (title, authors, year).
- The OCR gate (availability probe).
- The FTS5 index (population and query).
- The library service (listing, filtering, search).
- The reader service (page count and PNG rendering).
- The annotation service (notes, highlights, bookmarks, exports).
- The in-document search service (literal and regex modes).
- The document linking service (collections and projects).
- The reader → assistant handoff (payload composition and store).
- Persistence across a database reopen.

The validator runs against a temporary directory and an in-memory
database. It never contacts the network and never touches the user's
data.

The acceptance document is `docs/phases/phase_d_acceptance.md`.

## Research Project Service

The research project service lives in
`academic_platform.application.projects`. It is the single entry point
the presentation layer uses to manage research projects and their child
entities.

### Value objects

- **`ProjectStage`** — a closed enumeration of lifecycle stages: idea,
  design, collection, analysis, writing, complete, archived.
- **`ProjectView`** — an immutable summary of a project, including its
  questions, task counts, and linked-document count.
- **`ProjectQuestionView`** — an immutable summary of a research
  question.
- **`ProjectTaskView`** — an immutable summary of a research task.

### Application service

`ProjectService` provides:

- **Project lifecycle.** `create_project`, `update_project`,
  `delete_project`, `list_projects`, `get_project`.
- **Question management.** `add_question`, `update_question`,
  `remove_question`, `set_primary_question`, `list_questions`.
- **Task management.** `add_task`, `update_task`, `remove_task`,
  `list_tasks`, `list_open_tasks`.

Every mutation writes an audit event through the audit repository. The
audit event records the actor, the action identifier, the target, a
short summary, and (when applicable) a small JSON payload describing
the change.

### Project-linked collection

Creating a project also creates a project-linked collection with the
key `project-<project-key>` and a title of the form
`<project-title> — documents`. The collection is used by the document
linking service to associate documents with the project. When the
project's title changes, the collection's title is synchronized.

Deleting a project removes its children and its linked collection
through the model's cascade. The documents that were linked to the
collection are not deleted.

### Validation

Validation is fail-closed. `ProjectValidationError` carries every
issue at once so the presentation layer can present them together.

Project keys must be lowercase, start with a letter or digit, and
contain only letters, digits, hyphens, and underscores. Titles and
topics are bounded. Question text is required and bounded. Question
kinds are restricted to the closed set declared by the schema. Task
titles are required and bounded.

### Persistence contract

The service never commits. It runs inside a unit of work supplied by
the caller. A validation failure raises before any row is written; a
repository failure is translated into `ProjectError` and surfaces the
underlying cause.

### Audit trail

Audit events use stable action identifiers:

- `project.created`, `project.updated`, `project.stage_changed`,
  `project.deleted`.
- `project.question_added`, `project.question_updated`,
  `project.question_removed`, `project.question_primary_changed`.
- `project.task_added`, `project.task_updated`, `project.task_completed`,
  `project.task_removed`.

Audit events are append-only. The service writes them through the audit
repository; a failure to write an audit event is logged but never
prevents the primary mutation from completing, because the primary
mutation is the user's intent and the audit trail is diagnostic.

## Projects Page

The research projects page lives in
`academic_platform.ui.pages.projects`. It replaces the placeholder that
shipped in Phase 5 and presents the user's research projects with:

- A stage filter combo box.
- A sortable table of projects.
- A detail panel that renders the project's questions and tasks.
- Context-menu actions for edit, stage change, and delete.
- Header-level create, edit, and refresh actions.
- An empty state with a "Create a project" action.

### Application service

`ProjectService` is the page's single data source. It provides the
list, get, create, update, and delete operations for projects and their
questions and tasks. See the research project service section for the
full interface.

### Presentation details

- **Stage filter.** The filter restricts the rendered projects to a
  single lifecycle stage. The underlying service returns all projects;
  the page filters the model.
- **Inline stage change.** The detail panel's stage combo box updates
  the project's stage through the service. The change is recorded as
  an audit event.
- **Question and task editors.** The detail panel exposes tabs for
  questions and tasks. Each tab provides add, edit, and remove actions
  and a toggle action for tasks. Destructive actions are guarded by
  confirmation prompts.
- **Empty state.** The empty state carries an enabled action that opens
  the create dialog.
- **Selection.** Selecting a project populates the detail panel from
  the service. The detail panel reloads questions and tasks on every
  selection and after every mutation.

### Wiring

`MainWindow._wire_projects_page` constructs a `ProjectService` from
the window's `project_service_factory` and attaches it to the projects
page. The factory opens a fresh per-call repository manager so that
every operation runs in its own transaction boundary.

### Design rules

- The page reads and writes only through the application service. It
  never touches the database directly.
- The page emits typed signals for actions the shell handles. The
  current phase emits `open_document_requested`; the shell handles it
  in a later phase when the project document browser is delivered.
- The page never modifies documents. Document linking is delivered by
  the reader and library flows.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The form dialog is used for creation and editing. The page never
  constructs ad-hoc input widgets.
- The stage filter is a view-level operation. It never mutates the
  service's data.

## Collection Service

The collection service lives in
`academic_platform.application.collections`. It is the single entry
point the presentation layer uses to manage collections and their
items.

### Value objects

- **`CollectionKind`** — a closed enumeration of collection kinds:
  manual, topic, project, saved search, smart.
- **`CollectionView`** — an immutable summary of a collection,
  including its project linkage and its items.
- **`CollectionItemView`** — an immutable summary of a collection item.

### Application service

`CollectionService` provides:

- **Collection lifecycle.** `create_collection`, `update_collection`,
  `delete_collection`, `list_collections`,
  `list_collections_for_project`, `get_collection`.
- **Item management.** `add_item`, `update_item`, `remove_item`,
  `remove_item_by_target`, `reorder_items`, `list_items`, `find_item`.
- **Project-linked collection helper.** `project_collection_key`.

Every mutation writes an audit event through the audit repository.

### Validation

Validation is fail-closed. `CollectionValidationError` carries every
issue at once.

- Collection keys must be lowercase, start with a letter or digit, and
  contain only letters, digits, hyphens, and underscores.
- Titles and descriptions are bounded.
- Project-linked collections require a `project_key`; other kinds
  reject one.
- Smart and saved-search collections require a JSON object as their
  filter payload.
- Item types are restricted to the closed set declared by the schema.
- Manual items are permitted only on collections whose kind allows
  them.

### Project-linked collections

The key convention `project-<project-key>` is shared with the document
linking service. Collections created by either service are recognized
as the same object. The service exposes `project_collection_key` so
callers construct the key consistently.

### Item ordering

Item positions are assigned sequentially when items are added. The
`reorder_items` operation assigns new positions in a single flush; it
is atomic with respect to the caller's unit of work.

### Persistence contract

The service never commits. It runs inside a unit of work supplied by
the caller. A validation failure raises before any row is written; a
repository failure is translated into `CollectionError` and surfaces
the underlying cause.

### Audit trail

Audit events use stable action identifiers:

- `collection.created`, `collection.updated`, `collection.deleted`.
- `collection.item_added`, `collection.item_updated`,
  `collection.item_removed`, `collection.reordered`.

Audit events are append-only.

## Collections Page

The collections page lives in
`academic_platform.ui.pages.collections`. It replaces the placeholder
that shipped in Phase 5 and presents the user's collections with:

- A kind filter combo box.
- A sortable table of collections.
- A detail panel with two tabs: Items and Filter.
- Context-menu actions for edit and delete.
- Header-level create, edit, and refresh actions.
- An empty state with a "Create a collection" action.

### Application service

`CollectionService` is the page's single data source. See the
collection service section for the full interface.

### Presentation details

- **Kind filter.** The filter restricts the rendered collections to a
  single kind. The underlying service returns all collections; the
  page filters the model.
- **Items tab.** The items tab renders the collection's items and
  exposes add, edit note, move up, move down, and remove actions.
  Reordering is applied through the service's atomic `reorder_items`
  operation.
- **Filter tab.** The filter tab exposes a JSON editor for smart and
  saved-search collections. Other kinds have no filter payload; the
  editor is disabled for them.
- **Project-linked collections.** Project-linked collections are
  visible in the list but are not editable from this page. The edit
  button is disabled for them; the error message guides the user to
  the project's page and the document linking workflow.
- **Empty state.** The empty state carries an enabled action that opens
  the create dialog.
- **Selection.** Selecting a collection populates the detail panel from
  the service. The detail panel reloads items on every selection and
  after every mutation.

### Wiring

`MainWindow._wire_collections_page` constructs a `CollectionService`
from the window's `collection_service_factory` and attaches it to the
collections page. The factory opens a fresh per-call repository manager
so that every operation runs in its own transaction boundary.

### Design rules

- The page reads and writes only through the application service. It
  never touches the database directly.
- The page emits typed signals for actions the shell handles. The
  current phase emits `open_document_requested`; the shell handles it
  in a later phase when the collection document browser is delivered.
- The page never modifies documents. Deleting a collection removes its
  items but not the referenced documents.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The form dialog is used for creation and editing. The page never
  constructs ad-hoc input widgets.
- The kind filter is a view-level operation. It never mutates the
  service's data.
- The filter editor's contents are validated as JSON before being
  submitted to the service.

## Smart Collections

A smart collection is a collection whose items are computed from a
saved filter rather than added manually. Smart collections reuse the
`CollectionKind.SMART` kind and the collection's JSON filter payload.

### Filter model

`SmartCollectionFilter` is an immutable value object parsed from the
collection's JSON payload. The supported fields are:

- `year_from`, `year_to` — inclusive publication-year range.
- `processing_states` — array of processing states to include.
- `extensions` — array of file extensions to include (lowercased
  during parsing).
- `storage_modes` — array of storage modes to include.
- `missing` — boolean; when True, only missing files match; when
  False, only present files match.
- `title_contains` — case-insensitive substring match against the
  document title or display name.
- `author_contains` — case-insensitive substring match against any
  author in the document's metadata.
- `has_annotations` — boolean; when True, only documents with
  annotations match; when False, only documents without annotations
  match.
- `has_doi` — boolean; when True, only documents with a DOI in their
  metadata match; when False, only documents without a DOI match.

Unknown fields are rejected. Every field is optional; an empty filter
matches every document.

### Evaluator

`SmartCollectionEvaluator` applies the filter to the library and
returns the matching items. It:

- Reads through the document repository, the document metadata
  repository, and the annotation repository.
- Applies the coarse-grained filters (processing state, storage mode,
  missing) first so that the fine-grained filters run over a smaller
  candidate set.
- Batches its metadata and annotation lookups per document.
- Returns items in the order the underlying query produced them.
- Never persists anything.

The evaluator's item type is `document`. Smart collections that
reference other item types are out of scope at this stage.

### Integration

`CollectionService.list_items` short-circuits to the evaluator when the
collection's kind is `SMART`. The service also exposes
`evaluate_smart_collection(key)` for callers that want to evaluate a
smart collection explicitly. Creation and update validate the filter
payload through the smart-filter parser; a malformed payload never
reaches the database.

### Presentation

The Collections page renders the evaluated items for smart
collections. Item actions (add, edit note, move up, move down, remove)
are disabled because the items are computed; the page displays a hint
label explaining that the items are derived from the filter and that
the user should edit the filter to change the set. The Filter tab is
selected automatically when a smart collection is first shown.

### Design rules

- The evaluator is deterministic and side-effect free. The same filter
  and library produce the same items on every run.
- The evaluator never modifies the library.
- The evaluator's item type is `document`. New item types require a
  schema extension and an update to the evaluator.
- The filter parser rejects unknown fields. A silent no-op would hide
  the user's intent.
- The filter parser rejects malformed JSON and malformed field values
  with a list of issue messages.
- The evaluator's limit is applied after filtering; the limit does not
  bound the underlying query.

## Research Tasks and Milestones

The research tasks and milestones subsystem lives in
`academic_platform.application.tasks`. It builds on the task entities
introduced in Phase 18 and on the task operations already exposed by
`ProjectService`, adding a dedicated workflow service.

### Value objects

- **`TaskStatus`** — a closed enumeration: open, in progress, blocked,
  done, cancelled. `is_terminal` is true for done and cancelled;
  `is_active` is true for open, in progress, and blocked.
- **`TaskPriority`** — a closed enumeration: low, normal, high,
  critical. `rank` provides a numeric ordering for sorting.
- **`TaskView`** — an immutable summary of a task, including its
  status, priority, milestone flag, due date, completion timestamp, and
  notes.
- **`MilestoneView`** — an immutable summary of a task with the
  milestone flag set.
- **`TaskProgressSummary`** — the aggregated progress of a project's
  tasks: counts per status, milestone counts, overdue count, and the
  underlying task and milestone views.

### Application service

`TaskService` provides:

- **Reads.** `list_tasks`, `list_tasks_by_status`, `list_milestones`,
  `get_task`, `progress_summary`.
- **Writes.** `create_task`, `update_task`, `set_status`,
  `set_priority`, `mark_milestone`, `clear_milestone`, `delete_task`,
  `reorder_tasks`.

Every mutation writes an audit event through the audit repository.

### Status semantics

- Setting a task to `done` records a `completed_at` timestamp if one
  is not already present.
- Moving a task out of `done` clears its `completed_at`.
- The legacy `completed` boolean is derived from the status: it is 1
  when the status is `done` and 0 otherwise. This keeps the existing
  task repository operations that read `completed` consistent with the
  new status column.

### Milestone semantics

A milestone is a task whose `is_milestone` flag is set. There is no
separate table. The flag is preserved across updates and is exposed
through `MilestoneView`. The `mark_milestone` and `clear_milestone`
methods set and clear the flag and write dedicated audit events.

### Due dates

Due dates are stored as UTC timestamps. The service accepts a
`datetime` or an ISO-8601 string; strings are parsed and normalized to
UTC. `clear_due_at` is a distinct parameter that sets the due date to
`None`; passing `due_at=None` leaves the due date unchanged.

### Progress summary

`TaskProgressSummary` reports:

- Total tasks and counts per status.
- Total milestones and completed milestones.
- Overdue tasks: tasks with a due date in the past whose status is not
  terminal.
- The ratio of completed tasks and the ratio of completed milestones.

The summary is computed on demand; the service does not maintain a
materialized progress record.

### Presentation

The projects page hosts the `MilestonesPanel` as a third tab in the
project detail panel. The panel renders a summary row, a status filter,
a milestones-only filter, and the task list. Each row carries the
task's status icon, milestone marker, and title. A context menu on
each row offers status, priority, and milestone actions. The panel is
told which project is current by the projects page.

### Schema change

The `research_task` table gains five columns: `status`, `priority`,
`is_milestone`, `notes`, and `completed_at`. The migration
`0010_task_workflow_columns` adds them and backfills `status` from the
legacy `completed` flag. The migration is fully reversible.

## Project Export

The project export subsystem lives in
`academic_platform.application.project_export`. It serializes a
research project and its related entities into a self-contained
document.

### Formats

Two output formats are supported:

- **JSON** — a stable, versioned, machine-readable document. The
  schema version is recorded in the output so that future consumers can
  detect the format.
- **Markdown** — a human-readable document with source-linked
  references to the project's entities.

### Sections

The export is composed of independent sections. The caller may select
any subset:

- **Project fields** — key, title, topic, stage, metadata, timestamps,
  and version.
- **Research questions** — text, kind, primary flag, position, and
  timestamps.
- **Tasks** — title, description, status, priority, milestone flag,
  notes, due date, completion timestamp, and position.
- **Milestones** — the subset of tasks whose milestone flag is set.
- **Collections** — the project's linked collection, with its item
  count.
- **Linked documents** — the documents in the project's linked
  collection, with their extracted metadata.

The milestones section duplicates entries from the tasks section when
both are selected. The duplication is deliberate: the tasks section
shows every task, the milestones section highlights the milestones.

### Application service

`ProjectExportService` provides:

- `export(project_key, output_path, options=..., overwrite=...)` —
  write the export to a file.
- `build_json(project_key, options=...)` — return the JSON
  representation without writing it.
- `build_markdown(project_key, options=...)` — return the Markdown
  representation without writing it.
- `suggested_filename(project_key, export_format)` — return a
  suggested filename derived from the project's key or title.

The service is a pure read operation over the project, question, task,
collection, and document repositories. It never writes to the
database.

### Output discipline

- The JSON schema is versioned. The version is recorded in the output
  under `schema_version`.
- The Markdown output is deterministic. Given the same project and the
  same options, it produces the same text.
- The output is written atomically enough for the caller's purposes:
  the service writes the whole content with a single `write_text`
  call.
- Existing files are not overwritten unless the caller passes
  `overwrite=True`.

### Presentation

The projects page exposes an "Export…" header action and a
context-menu action. Both open `ProjectExportDialog`, which lets the
user pick the format, the destination, the sections to include, and
whether to overwrite an existing file. The dialog delegates the export
to the service and emits `exported(result)` on success.

### Design rules

- The service never writes to the database.
- The service never modifies the project or its entities.
- The output is self-contained. Every referenced document is
  identified by its key so that a reader can trace the reference.
- Documents that are missing from the library are reported rather than
  silently omitted.
- The export does not include binary content. Document files are
  referenced by their keys and metadata, not embedded.

## Phase E Acceptance

Phase E is verified end to end by
`scripts/validate_phase_e.py` and by
`tests/unit/test_phase_e_acceptance.py`. The harness exercises:

- The project CRUD service (create, update, question management,
  task operations, collection synchronization, delete).
- The collection CRUD service (create, update, list, delete; add,
  note, reorder, and remove items; invariants).
- Smart collections (filter parsing, rejection of unknown fields,
  evaluation against the library).
- The task workflow service (status, priority, milestones, progress
  summary, overdue detection).
- The project export service (JSON and Markdown with independent
  selectable sections; refusal to overwrite without a flag).
- The audit trail spanning project, collection, and task mutations.
- Persistence across a database reopen.

The validator runs against a temporary directory and an in-memory
database. It never contacts the network and never touches the user's
data.

The acceptance document is `docs/phases/phase_e_acceptance.md`.

## Research Assistant Page

The research assistant page lives in
`academic_platform.ui.pages.research_assistant`. It replaces the
placeholder that shipped in Phase 5 and hosts the ten workflow
sections declared by the product specification.

### Sections

- **Topic & Problem** — the broad subject, the research problem, the
  context and population, and the constraints.
- **Title Builder** — the working title and a list of candidate titles.
- **Research History** — history notes and a list of references.
- **Research Questions** — the primary question, secondary questions,
  and hypotheses.
- **Theories & Concepts** — the theoretical framework and a list of
  theories and concepts.
- **Methodology Advisor** — a list of candidate methodologies with a
  chosen flag.
- **Statistical Analysis** — data notes, assumption notes, and a list
  of candidate statistical methods with a chosen flag.
- **Research Plan** — the structured research plan fields.
- **Sources & Evidence** — the list of sources and evidence notes.
- **Review & Export** — a summary of every other section and an export
  action.

### Architecture

Each section is a `BasePage` subclass that participates in the page's
lifecycle. A `SectionHost` wraps each section in a scroll area with a
footer that exposes a "Clear section" action and a summary label. The
page owns a single `QStackedWidget`; sections remain constructed for
the lifetime of the page, so work is preserved across navigation.

### Sidebar

The sidebar lists every section in the order declared by the enum. Each
row renders the section's name and, when available, its summary. The
summary is refreshed when the section is activated and when the user
clicks the "Refresh summaries" action.

### Review section

The review section is a read-only view composed from the other
sections. The page provides a summary provider at construction time;
the section invokes the provider when it is activated. The provider
iterates the sections in declaration order and renders each section's
summary.

### Persistence contract

Section work lives in the widgets. It is preserved across navigation
and across page activations. Persistence to the database is delivered
in later phases when the rule-based and AI-backed assistants write
their state through the research plan service.

### Design rules

- Sections never communicate with each other directly. Cross-section
  coordination is delivered through the page or through the research
  plan service in later phases.
- The page never mutates a section's state directly. It invokes the
  section's lifecycle methods and reads the section's summary.
- The sidebar reflects the section's own summary. The page never
  fabricates a summary for a section.
- The review section's summary provider is owned by the page. The
  section never inspects other sections directly.
- The page emits `destination_requested(identifier)` when the user
  requests to navigate to a different destination; the shell handles
  the signal.

## Topic & Problem Workspace

The Topic & Problem workspace lives in
`academic_platform.application.topic_workspace`. It persists the
research assistant's topic draft to the database and anchors it to a
research project.

### Fields

The workspace captures nine fields:

- Broad subject
- Research problem
- Context
- Population
- Time period
- Key concepts
- Potential outcomes
- Constraints
- Researcher's knowledge level

The `broad_subject` and `research_problem` fields are the essential
fields. A draft is ready when both are populated. The completeness
report treats the other fields as contributions that do not block
readiness.

### Persistence

The workspace stores its state in the project's `project_metadata`
JSON column under the key `topic_workspace`. The project's dedicated
`topic` column carries the broad subject so that the subject remains
visible in the projects page without decoding JSON.

When the workspace is not attached to a project, it holds a draft in
memory. The draft can be attached to a project later through
`merge_into_project`, which merges the draft's non-empty fields into
the project's current fields.

### Validation

Every write validates its fields against a documented maximum length.
Empty values are permitted because a draft is filled incrementally.
A validation failure raises `TopicWorkspaceValidationError` with all
issues at once.

### Audit trail

Every successful write records an audit event. Action identifiers:

- `topic.attached`, `topic.detached`.
- `topic.created`, `topic.updated`, `topic.cleared`.

Audit events are append-only.

### Section integration

The Topic section in the research assistant page is backed by the
service. The section gains an `attach_service` method and an
`attach_project` method. Its `summary` returns the service's
completeness report. Its `reset` calls the service's `clear`. Editor
changes are written through the service as the user types; the writes
are idempotent because the service persists the whole draft on each
change.

### Wiring

`MainWindow._build_topic_workspace_service_factory` provides a callable
that constructs a `TopicWorkspaceService` bound to a per-call session.
`MainWindow._wire_research_assistant_page` attaches an instance to the
research assistant page after pages are registered.

### Design rules

- The workspace is anchored to a project. When no project is attached
  the workspace holds a draft in memory.
- The workspace never invents values. Unset fields remain empty.
- The workspace never mutates a project that does not exist.
- The `topic` column carries the broad subject. The extended fields
  live in the project's metadata.
- The completeness report treats the broad subject and the research
  problem as essential. Additional fields contribute to the ratio but
  do not block readiness.
- The workspace never commits. It runs inside a unit of work supplied
  by the caller.

## Clarifying Question Engine

The clarifying-question engine lives in
`academic_platform.application.clarifying_questions`. It is a
deterministic, rules-based system that inspects a topic draft and
produces a bounded list of focused clarifying questions.

### Model

- **`ClarifyingQuestion`** — a single question carrying a stable
  identifier, a category, the target topic field, the question text,
  a rationale, a priority, a blocking flag, and an optional example
  answer.
- **`QuestionCategory`** — a closed enumeration of categories: scope,
  problem, context, population, time, concepts, outcomes, constraints,
  knowledge.

### Engine

`ClarifyingQuestionEngine` runs a fixed set of rules. Each rule reads
the draft and yields zero or one question. The engine collects the
questions, sorts them by priority, filters out dismissed identifiers,
and returns the top `max_questions`. The engine is a pure function: it
never mutates the draft, never persists anything, and never calls an
AI provider.

### Rules

The default rule set:

1. **Broad subject present.** Emitted when the draft has no broad
   subject. Blocking.
2. **Broad subject scope.** Emitted when the broad subject is present
   but very short. Advisory.
3. **Research problem present.** Emitted when the draft has no
   research problem. Blocking.
4. **Research problem nature.** Emitted when the research problem is
   present but does not indicate whether it is practical or
   theoretical. Advisory.
5. **Context present.** Emitted when the draft has no context.
6. **Population present.** Emitted when the draft has no population.
7. **Time period present.** Emitted when the draft has no time period.
8. **Key concepts present.** Emitted when the draft has no key
   concepts.
9. **Potential outcomes present.** Emitted when the draft has no
   potential outcomes.
10. **Constraints present.** Emitted when the draft has no
    constraints.
11. **Knowledge level present.** Emitted when the draft has no
    knowledge level.

Rules are pure functions of the draft. Each rule is a small function
that returns either a `ClarifyingQuestion` or `None`.

### Section integration

The Topic section renders the questions in a panel beneath the topic
fields. The panel refreshes whenever the section is populated or an
editor changes. Each question row carries the question text, a
tooltip with the rationale, and actions to focus the target field and
to dismiss the question. Dismissed identifiers are tracked in the
section for the duration of the session.

### Design rules

- The engine is deterministic. The same draft produces the same
  questions in the same order on every run.
- Rules never emit a question whose answer would not change the next
  step of the workflow.
- The engine bounds the number of returned questions. A long list is a
  worse experience than a short, focused list.
- The engine never calls an AI provider. Rule-based logic is
  deterministic and auditable.
- The engine never persists anything. Persistence of the user's
  answer is the workspace's responsibility.
- A rule that raises an unexpected exception is wrapped as a
  `ClarifyingQuestionError` and reported to the caller.

## Title Builder

The title builder lives in
`academic_platform.application.title_builder`. It generates and
evaluates candidate research titles from a topic draft.

### Model

- **`TitlePattern`** — a closed enumeration of title templates:
  subject-and-outcome, subject-in-population, effect-of-X-on-Y,
  association-between-X-and-Y, exploration-of-subject,
  comparison-across-groups, development-of-instrument, methodological
  study.
- **`TitleState`** — a closed enumeration: proposed, accepted, rejected,
  archived.
- **`TitleCandidate`** — an immutable candidate with its pattern, title,
  rationale, strengths, problems, assumptions, alignment report, and
  state.
- **`TitleAlignmentReport`** — the alignment score, the fields that were
  matched, the fields that were missing, and any notes.

### Engine

`TitleBuilderEngine` applies the pattern functions to a topic draft.
Each pattern returns either a candidate or ``None`` when the draft
lacks the fields the pattern requires. The engine evaluates every
candidate against the draft and returns the candidates sorted by
alignment score. The engine is a pure function: it never persists
anything, never calls an AI provider, and never invents values the
draft does not support.

### Alignment score

The alignment score is a bounded, documented formula. Each topic field
carries a weight reflecting its significance in the specification:
the broad subject and the research problem carry the most weight; the
potential outcomes, population, and context carry moderate weight; the
remaining fields carry small weights. The score is the sum of the
weights of the fields the pattern used plus a small contribution from
the other populated fields, clamped to ``[0.0, 1.0]``.

### Service

`TitleBuilderService` composes the engine with the
``research_title_candidate`` repository. It generates candidates from a
topic draft, persists them against the attached research project,
manages their state, and records an audit event for every mutation.
Regenerating the candidates replaces the previous proposed candidates
in a single transaction; accepted, rejected, and archived candidates
are preserved so that the user's decisions are not lost.

### Section integration

The Title Builder section is backed by the service. The section exposes
actions to generate candidates, accept, reject, and use a candidate as
the working title. A details pane shows the selected candidate's
rationale, strengths, problems, and assumptions. The section reads the
current topic draft through the assistant page so that it does not
depend on the topic workspace service directly.

### Design rules

- The engine is deterministic. The same draft produces the same
  candidates in the same order on every run.
- The engine never invents values the draft does not support. A pattern
  that lacks its required fields returns ``None`` and is not reported
  as a candidate.
- The engine bounds the number of returned candidates.
- The engine never calls an AI provider. Rules-based generation is
  deterministic and auditable.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Regeneration preserves the user's decisions on accepted, rejected,
  and archived candidates.
- The alignment score is documented in the engine module. Changing the
  weights requires updating the module's documentation and the tests
  that depend on the score.

## Title Comparison and Selection

The comparison workspace is embedded in the Title Builder section. It
renders every candidate as a card and exposes the actions the user
needs to decide among them.

### Service extensions

The title builder service gains four operations:

- `update_title(project_key, candidate_id, title)` — replace a
  candidate's title text. The candidate's rationale, strengths,
  problems, assumptions, and stored alignment are preserved.
- `restore_candidate(project_key, candidate_id)` — return a candidate
  to the proposed state.
- `list_by_state(project_key)` — return candidates grouped by state.
- `comparison_report(project_key)` — return candidates ordered for
  side-by-side comparison: accepted first, then proposed (sorted by
  alignment descending), then rejected, then archived.

### Panel

`TitleComparisonPanel` is a self-contained widget. It renders each
candidate as a card carrying the title, state, pattern, alignment,
rationale, strengths, problems, and assumptions. The panel exposes
actions to accept, reject, archive, restore, edit the title, and use
the candidate as the working title. Every action writes through the
service; the panel refreshes from the service after each action.

### Editing

Editing a candidate's title uses the standard prompt dialog. The
service validates the new title: it must be non-empty and at most 200
characters. The original title is recorded in the audit trail.

### Card states

A card's left border and its state label reflect the candidate's
state: accepted (green), proposed (accent), rejected (danger), and
archived (muted). The card renders its state as a dynamic Qt property
so that the stylesheet can key on it without rebuilding the stylesheet.

### Section integration

The Title Builder section embeds the panel beneath its details pane.
The section wires the panel's `working_title_selected` signal to its
working-title field so that the user can promote a candidate with a
single action. The panel is refreshed whenever the section reloads its
candidates.

### Design rules

- The panel reads and writes only through the service. It never
  recomputes the candidate's rationale or alignment; the service is the
  single source of truth.
- The panel refreshes from the service after every action. Local
  caching of candidate state is not permitted.
- Editing a candidate's title preserves the other fields. The stored
  alignment summary is not recomputed on edit; a fresh generation pass
  is required for that.
- The panel emits `working_title_selected(title)` when the user
  requests to use a candidate as the working title. The section
  handles the signal; the panel does not write to the working-title
  field directly.
- Destructive actions are guarded by the service's validation and, for
  removals, by the standard confirmation prompt.

## Research Question Development

The research-question workspace lives in
`academic_platform.application.research_questions`. It persists the
topic, the problem, the gap, the primary research question, and the
secondary questions and hypotheses to the attached research project.

### Model

- **`QuestionKind`** — a closed enumeration: main, sub, exploratory,
  hypothesis. `is_testable` is true for main, sub, and hypothesis.
- **`ResearchQuestionView`** — an immutable view of a single question.
- **`QuestionValidationIssue`** and **`QuestionValidationReport`** —
  the validation output. Issues carry a severity of ``error`` or
  ``warning``. The report is valid when it has no errors.
- **`ResearchQuestionDraft`** — an immutable view of the workspace's
  current state.

### Service

`ResearchQuestionWorkspaceService` provides:

- `attach_project(project_key)` — attach the workspace to a project.
- `current_draft()` — return the current draft.
- `validation_report()` — return the validation report for the current
  draft.
- `set_topic`, `set_problem`, `set_gap`, `set_primary_question` —
  write the workspace fields.
- `add_question`, `update_question`, `remove_question`,
  `promote_to_primary` — manage the secondary questions.

Every mutation records an audit event.

### Persistence

The topic lives on the project's dedicated ``topic`` column. The
problem and the gap live in the project's ``project_metadata`` JSON
column under the ``research_question_workspace`` key. The primary
question is mirrored as a ``research_question`` row with the
``is_primary`` flag set; the workspace metadata also carries the
primary question text so that the workspace's own view is complete.
Secondary questions and hypotheses live exclusively in the
``research_question`` table.

### Validation

Validation is a pure function of the draft. Issues carry a severity:

- **Errors** block the workflow: a missing primary question.
- **Warnings** describe improvements: a missing topic, problem, or
  gap; a question that does not end with a question mark; a question
  that does not start with an interrogative word; a question that
  contains a vague term; a question that is very short or very long.

The validation report is a separate operation. It never blocks a
write; the service's input validation is the operation that raises.

### Section integration

The Research Questions section is backed by the service. The section
renders the topic, the problem, the gap, and the primary question as
multiline fields; the secondary questions as a list; and the
validation report as a label whose severity drives its styling. The
section exposes actions to add, edit, remove, and promote questions.

### Design rules

- The workspace is anchored to a project. Writes without an attached
  project raise a dedicated error.
- The primary question is mirrored as a research-question row so that
  it participates in the project's question list and in project export.
- The topic, problem, and gap are stored in the project's metadata.
  The topic is additionally stored on the project's dedicated column.
- Validation is fail-closed for inputs. The service raises on invalid
  input with every issue at once.
- The validation report describes the draft; it never blocks a write.
- The service never commits. It runs inside a unit of work supplied by
  the caller.

## Research History Workspace

The research-history workspace lives in
`academic_platform.application.research_history`. It is the first
section of the research assistant that is explicitly search-backed: it
proposes alternative queries from a topic and its synonyms, executes
them against the search orchestration service, persists the retrieved
results with provenance, and groups the results into a timeline and a
set of themes.

### Model

- **`HistoryQuery`** — a single search query the workspace proposes
  or the user records.
- **`HistoryResult`** — a single retrieved publication with its
  provenance.
- **`HistorySearchRun`** — a single execution of a query against the
  search orchestration service.
- **`HistorySearchStatus`** — the outcome of a single run: ok,
  partial, failed, or skipped.
- **`HistoryTimelineBucket`** — a year-bucketed aggregation of
  results.
- **`HistoryTheme`** — a set of related results grouped by a shared
  concept.
- **`ResearchHistoryDraft`** — an immutable view of the workspace's
  current state.

### Service

`ResearchHistoryService` composes the search orchestration service and
the publication service. It reads and writes the workspace draft in
the project's `project_metadata` JSON column under the
`research_history_workspace` key. It never speaks HTTP directly.

The service provides:

- `attach_project(project_key)` — attach the workspace to a project.
- `current_draft(project_key)` — return the current draft.
- `propose_queries(project_key)` — return the queries the workspace
  proposes for the topic. The proposal is deterministic for a given
  topic and synonym set.
- `set_topic`, `add_synonym`, `remove_synonym`, `add_user_query`,
  `remove_user_query`, `set_narrative`, `clear` — write the workspace
  state.
- `run_query(project_key, query)` — execute a single query and
  persist the run and its results.
- `run_all(project_key)` — execute every proposed and user-defined
  query.

Every mutation records an audit event.

### Search execution

The service builds a `SearchOrchestrationRequest` with the query's
text and the enabled source selection, executes it through the
orchestrator, and persists the retrieved publications through the
publication service. The run is recorded with its status and its
per-source reports.

The service never fabricates results. When a query fails, the run is
recorded with a failure status and the source reports are preserved.

### Timeline and themes

The timeline groups results by year. The themes group results by a
fixed set of keywords derived from titles, abstracts, and venues. Both
aggregations are deterministic: the same results produce the same
timeline and themes on every run.

### Design rules

- The service is deterministic for a given topic, synonym set, and
  search response.
- The service never calls an AI provider. Rules-based grouping is
  deterministic and auditable.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The service persists the workspace state in the project's metadata.
  It does not create a dedicated table for the workspace.
- The narrative is user-authored. The workspace never generates
  narrative text.