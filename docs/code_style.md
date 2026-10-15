# Code Style

- Python 3.11 or newer.
- Line length: 100 characters.
- Type annotations required on public functions and boundaries.
- Module docstrings required on every module.
- Section comments are used to break up long modules and must describe intent,
  not restate the next line.
- Naming: `PascalCase` for classes, `snake_case` for functions, variables, and
  modules. No unexplained abbreviations.
- Errors are handled explicitly. Generic success messages must never follow a
  failed operation.
- No secrets in source. No commented-out obsolete code.
- TODO comments must include a description and, when available, an issue
  reference.

## Architecture Decision Records

- Every decision that changes module boundaries, dependencies, persistence,
  or validation strategy requires an ADR.
- ADRs use the template at `docs/adr/TEMPLATE.md` and are numbered
  sequentially in four-digit form.
- The `Status` field is one of: `proposed`, `accepted`, `rejected`,
  `deprecated`, `superseded`.
- A record with status `superseded` must name the superseding ADR in the
  `Superseded by` field.
- Supersession is recorded in both directions: the superseded record names
  the new record, and the new record names the superseded record in
  `Supersedes`.
- The index at `docs/adr/README.md` is generated and must not be edited by
  hand.
- ADR files must parse without validation errors. The `validate` subcommand
  of `scripts/adr.py` is the authority for this check.

## Build System Conventions

- All build metadata lives in `pyproject.toml`. No `setup.py`, `setup.cfg`,
  or `requirements.txt` files are maintained in parallel.
- Package discovery is restricted to the `academic_platform*` namespace.
  New top-level packages under `src/` must be added explicitly.
- Package data must be declared in `[tool.setuptools.package-data]`. New
  resource directories under `src/academic_platform/` must be added there.
- Ruff, mypy, pytest, and coverage configuration live in `pyproject.toml`.
  No separate `pytest.ini`, `mypy.ini`, or `ruff.toml` files are permitted.
- Console scripts are declared under `[project.scripts]`. Any new command
  must map to a callable with a `main(argv) -> int` signature.
- Python version support is expressed through `requires-python` and
  `[tool.ruff] target-version`. Both must be updated together.

## UI Page Conventions

- Every page inherits from `BasePage`. A page that does not inherit from
  `BasePage` must justify the exception in a module-level comment.
- Pages must not manipulate the main window directly. Cross-page
  communication goes through signals emitted from the page and connected by
  the shell or a controller.
- The page header is constructed by the base class. Pages supply their title
  and subtitle at construction time and update them with `set_subtitle`.
  Pages must not construct a second header.
- Content is installed exactly once via `_install_content`. Attempting to
  install content twice is a programming error and raises.
- Empty states are installed via `_install_empty_state` and displayed with
  `show_empty_state`. Pages that never have content use the placeholder
  page instead.
- Pages define an object name that matches the destination identifier
  (`placeholderPage_<identifier>`, `dashboardPage`). Object names are used
  by the stylesheet and by UI tests.
- Button controls that are not yet wired must be disabled and carry a
  tooltip explaining their purpose. A disabled control is honest; a live
  control that does nothing is not.
- Signal names use the imperative form (`destination_requested`,
  `status_message_requested`) and are documented with a docstring comment
  above the `Signal` declaration.

## Component Conventions

- Every component lives in `academic_platform.ui.components` and exposes a
  small, documented public API. Private attributes are prefixed with an
  underscore.
- Components are presentation-only. They do not import from repositories,
  HTTP clients, or statistical libraries.
- A component that has user actions emits typed signals. Signal names use
  the imperative form (`action_requested`, `retry_requested`,
  `cancel_requested`, `submitted`, `cleared`, `scope_changed`,
  `text_changed`, `filters_changed`, `reset_requested`).
- A component that has controls which are not yet wired must disable those
  controls. Enabling a control is a caller decision made when a handler is
  connected.
- Components provide accessor properties for the controls they own so that
  callers can bind shortcuts or inspect state without reaching into
  private attributes. UI tests use these accessors where possible.
- Object names are assigned to every widget that the stylesheet targets or
  that tests query. Object names use lowerCamelCase with a component
  prefix (`emptyStateTitle`, `searchBarInput`, `filterPanelTitle`).
- Components must not depend on the widget hierarchy for styling. Every
  selector in `styles.py` keys on an object name.
- Components accept `parent` as an optional keyword argument and default to
  `None`.
- A component that manages state must expose a `set_state`-style API for
  bulk updates and a granular API for individual mutations. Bulk updates
  suppress intermediate signal emissions where that is meaningful.

### Payload dataclasses

- Every content card defines a payload dataclass in the same module as the
  card. The payload is frozen and uses slots.
- Payload field names mirror the domain vocabulary where a domain concept
  exists. Field names that describe presentation state (`enabled`,
  `status`) are permitted when the domain does not carry that concept.
- Payloads carry no methods other than `display()`-style helpers that
  resolve a display string from the payload. Business logic never lives on
  a payload.
- Payloads are not persisted. Persistence uses domain models; adapters
  convert domain models to payloads for the presentation layer.

### Enable-then-connect rule

- Every actionable control on a component is disabled at construction.
- The caller enables a control by calling an `enable_*` method after
  connecting the corresponding signal.
- Toggle controls that mirror persisted state (for example, the enable
  checkbox on `AIProviderCard`) follow the caller-owned-state pattern: the
  component emits the intended state and the caller reflects it back with
  `set_enabled`, which suppresses signal emission.
- A component that violates this rule must document the exception in a
  module-level comment.

### Dynamic Qt properties

- Tones and similar stateful styling attributes are applied through
  dynamic Qt properties, not by rebuilding the stylesheet per widget.
- Property values are strings, not enum instances, so that the stylesheet
  matches on stable identifiers.
- When a dynamic property changes, the component calls `style().unpolish`
  followed by `style().polish` to trigger a re-evaluation.

## Dialog Conventions

- Every standard dialog lives in `academic_platform.ui.dialogs` and is
  constructed through `DialogFactory`. Direct instantiation of
  `QMessageBox` and similar is not permitted outside the dialogs package.
- Dialogs are modal by default. Non-modal events use the notification
  system.
- Dialogs never perform the action they confirm. They return a decision
  or a set of values; the caller performs the action.
- Destructive actions default to the cancelling button. Callers request
  the opposite explicitly.
- Every dialog carries an object name matching its class in lower
  camelCase (`messageDialog`, `confirmDialog`, `promptDialog`,
  `formDialog`, `progressDialog`).
- Validation in `PromptDialog` and `FormDialog` is synchronous and
  local. Asynchronous validation is performed by the caller after the
  dialog closes.

## Notification Conventions

- Notifications are published through `NotificationService`. Direct
  construction of `Notification` outside the service is not permitted.
- Severity is expressed through the service's convenience methods
  (`info`, `success`, `warning`, `error`). Callers do not construct
  severities directly.
- Errors do not auto-dismiss (`timeout_ms=0`). Other severities
  auto-dismiss after the default timeout unless overridden.
- The service is Qt-independent. It must not import from PySide6.
- The host is a child widget of the main window, not a separate window.

## Dashboard Conventions

- The dashboard is composed exclusively of `SectionCard` instances. Each
  section renders its own empty state.
- Every section exposes a private `_populate_<section>` method called by
  the public `refresh()` method. Section-specific data shaping happens
  inside that method.
- The dashboard never reads from repositories directly. It reads through
  the window-level `dashboard_data_provider` callable. When no provider
  is registered, every section renders its empty state.
- Empty states are honest: they do not present buttons that do not work.
  An empty state may carry an enabled action only when the action
  corresponds to a registered destination.
- Quick action buttons are always enabled because their destinations are
  always registered. The buttons are wired to emit
  `destination_requested`; the shell navigates.
- The dashboard does not persist state. All rendering state is derived
  from the provider on each `refresh()` call.

## Global Search Conventions

- The search page is composed of two `_ResultSurface` instances, one per
  tab. Each surface owns a `FilterPanel`, a source-status panel, a
  `SearchResultList`, a `LoadingIndicator`, and an `ErrorState`.
- The page never fetches data directly. It delegates to a `SearchController`
  and renders the `SearchResponse` it returns.
- The default controller is `NullSearchController`. It returns empty
  results with `SourceStatus.SKIPPED` and an explanatory message. This is
  the only controller the application installs by default.
- Search responses carry per-source status. The page renders the status
  panel from the response; it never synthesizes status.
- Errors raised by a controller are caught at the page boundary and
  rendered as an `ErrorState` with a retry action. The retry signal is
  forwarded to the shell through `retry_requested`.
- Empty results with an explanatory `message` replace the default empty
  state wording for that surface. Empty results without a message use the
  surface's default wording.
- Result entries are immutable dataclasses with optional fields. Empty
  optional fields are hidden by the row widget; they are never rendered as
  placeholder text.

## Settings Conventions

- Every settings tab inherits from `SettingsTab` and is constructed with
  the settings service and an optional notification service.
- Tabs persist changes on control change. There is no global Apply button.
- Tabs set `self._loading = True` while populating controls so that
  programmatic changes do not trigger persistence. They reset the flag in
  a `finally` block.
- Every tab implements `reload()` to re-read its section and repopulate
  its controls. `reload()` is invoked by the page on external changes and
  on activation.
- Updates go through `SettingsTab._update_section`, which catches
  `SettingsError` and reports the problem through the notification
  service. Tabs must not call `SettingsService.update_section` directly.
- Tabs do not import from other tabs. Cross-tab coordination goes through
  the settings service and its observer mechanism.
- The Advanced tab is the only tab that performs actions beyond editing
  settings. It uses `DialogFactory` for confirmations and publishes
  notifications through the notification service.
- Tabs carry an object name matching their purpose in lower camelCase
  (`settingsTabGeneral`, `settingsTabAppearance`, ...).
- Individual controls carry object names prefixed with the tab identifier
  (`settingsGeneralLanguage`, `settingsAppearanceTheme`, ...).


## Persistence Conventions

- The infrastructure layer is the only place that constructs database
  engines, sessions, and migrations. Domain and application modules must
  not import from `sqlalchemy` directly.
- SQLAlchemy exceptions are caught at the infrastructure boundary and
  translated into typed exceptions (`DatabaseError`,
  `DatabaseConfigurationError`). Callers depend only on the typed
  exceptions.
- Sessions are short-lived. Every session is obtained through
  `Database.session()` and used inside a `with` block. Long-lived sessions
  and global session objects are not permitted.
- The session factory disables `expire_on_commit` and enables autoflush.
  Code must not depend on lazy attribute refresh after commit; if data is
  needed after commit, it is read inside the same session before the block
  exits.
- Connection PRAGMAs are applied through a `connect` event listener, not
  through ad-hoc statements issued by callers. New PRAGMAs are added to
  the listener so that every connection is configured consistently.
- `Database` instances are created once per application and disposed after
  the event loop exits. They are not shared across processes.
- Test code uses `Database.in_memory()` when the test does not require a
  file and `Database.from_path(tmp_path / "app.sqlite3")` when it does.
  Tests must dispose their database in a fixture teardown.

  ## Migration Conventions

- Every schema change is expressed as an Alembic revision under
  `migrations/versions/`. Direct schema edits are prohibited.
- Revision identifiers use the form `NNNN_short_description` where `NNNN`
  is the sequential number. The baseline revision is `0001_baseline`.
- Each revision file declares `revision`, `down_revision`,
  `branch_labels`, and `depends_on` as module-level constants with
  explicit type annotations.
- `upgrade` and `downgrade` are implemented in full. `pass` is permitted
  only when the operation genuinely performs no schema change (as in the
  baseline revision).
- Revisions include a module docstring stating what the revision does and
  any assumptions it makes.
- Migrations are reviewed for reversibility. If a downgrade is impossible
  or destructive, the module docstring states the reason and `downgrade`
  raises a `RuntimeError` explaining that the operation is not supported.
- The application runs migrations at startup. Tests that construct a
  database either run migrations explicitly through
  `upgrade_to_head` or accept an unmigrated database and create tables
  directly with `metadata.create_all`.
- New revisions are added to `migrations/versions/` and are never
  removed once they have been released. Reverting a released revision
  requires a new revision that undoes the change.

  ## ORM Model Conventions

- Every ORM model inherits from `Base` and, where applicable, from the
  shared mixins `TimestampMixin` and `VersionMixin`.
- Model modules live under
  `academic_platform.infrastructure.database.models`. Every module is
  imported in the package's `__init__.py` so that Alembic's autogenerate
  sees the full schema.
- Table names use `snake_case` and are plural-free for singletons
  (`app_settings`) and singular for entity tables (`user_profile`,
  `audit_event`). The choice is deliberate per table and documented in
  the model's docstring.
- Column types are declared with SQLAlchemy 2.x syntax: `Mapped[T]` for
  the Python type and `mapped_column(...)` for the column. `nullable`,
  `default`, `server_default`, and `index` are set explicitly.
- Models do not contain business logic beyond simple derived properties.
  Methods that require a session, a repository, or an external service
  belong in the application layer.
- Every model defines `__repr__` returning a short string that includes
  the surrogate primary key or a stable business key. The full row is
  never included.

## Pydantic Persistence Schema Conventions

- Persistence schemas inherit from `PersistenceSchema`, which sets
  `from_attributes=True`, `extra="forbid"`, `str_strip_whitespace=True`,
  and `validate_assignment=True`.
- Every entity has three schemas: `Create`, `Update`, and `Read`. The
  `Update` schema treats every field as optional; absent fields are left
  unchanged by the repository.
- The `Read` schema includes `id`, `created_at`, `updated_at`, and any
  version column. It never includes relationship collections that could
  trigger lazy loading during serialization.
- Schemas are named `<Entity>Create`, `<Entity>Update`, and
  `<Entity>Read`. The pattern is applied consistently so that callers can
  infer the schema name from the entity name.
- Validation logic is expressed with Pydantic validators, not with ad-hoc
  checks in repository code.

## Repository Conventions

- Concrete repositories live under
  `academic_platform.infrastructure.repositories` in modules named
  `<entity>_repository.py`. They subclass `Repository[Entity]` and declare
  the `entity` class attribute.
- Repositories do not commit. They operate on the session they are given
  and flush when they need to materialize server-generated values.
- Persistence errors are translated to the repository's typed exceptions
  before leaving the method. Callers depend only on the typed exceptions.
- Query composition uses specifications, not ad-hoc `select` statements
  in the application layer. A specification that is used in more than one
  place lives in the repository module next to the repository that
  consumes it.
- Repository methods that read a single entity accept a primary key or a
  specification. Methods that read multiple entities accept a
  specification, an optional ordering, and optional limit and offset.
  Paginated reads accept a `PageRequest`.
- Update methods accept a Pydantic `Update` schema. Only fields present
  in the schema's `model_fields_set` are applied. Absent fields are left
  unchanged.
- The repository never mutates an entity outside the session it was
  obtained from. Detached entities are re-attached by reading them
  through the current session before they are updated.
- Repository registration happens through
  `register_repository(key, class)` in
  `academic_platform.infrastructure.repositories.factory`. Keys are
  lowercase snake_case and match the entity name (`user_profile`,
  `research_project`, ...).

## Specification Placement

- Specifications used by exactly one repository live in the repository
  module itself. They are named after the predicate they express
  (`_NameEquals`, `_StageIsIdea`) and are not exported.
- Specifications used by more than one repository, or that name an
  application-level concept that the UI references, live in
  `academic_platform.infrastructure.repositories.specifications` and are
  exported from that package.
- Specification classes are immutable. Their constructors accept the
  values they need; their ``to_expression`` method builds a fresh
  expression on each call.
- Specification names describe the predicate, not the query. Use
  `ProjectByStage`, not `QueryProjectsAtStage`.

## Cascade and Referential Integrity

- Foreign keys that represent ownership use ``ondelete="CASCADE"``.
  Research questions belong to their project; collection items belong to
  their collection. Deleting the parent removes the children.
- Foreign keys that represent references without ownership use no
  ``ondelete`` clause. The application controls the lifecycle.
- Check constraints enforce closed enumerations (project stage, question
  kind, collection kind, collection item type). New values require a
  migration and a schema update in the same phase.
- Cross-column invariants are enforced with check constraints, not with
  application code alone. The collection project-link invariant is the
  canonical example: project-linked collections must carry a project
  identifier; other kinds must not.

## Document Model Conventions

- Document records never store file contents. The file lives on disk;
  the database stores its location, its checksum, and the metadata that
  was extracted from it.
- The `location` column stores an absolute path for referenced files and
  an application-relative path for managed copies. The distinction is
  recorded by `storage_mode`; the application never infers it from the
  path.
- Checksums use SHA-256, lowercase hexadecimal, sixty-four characters.
  The Pydantic schema validates the format; the model does not.
- Processing, OCR, and indexing states are closed enumerations enforced
  by check constraints. New states require a migration and a schema
  update.
- Annotations are separate records. The application never modifies the
  source file to store a note, a highlight, or a bookmark.
- Cascade deletes are used only where ownership is unambiguous: metadata,
  chunks, and annotations belong to their document. Deleting a document
  removes them.
- Document repositories never delete the underlying file. Deleting a
  managed copy requires an explicit application-layer operation; deleting
  a referenced file is never performed by the application.

## Migration Testing

Tests must not hard-code the head revision. The head moves with every new
migration. Tests import `EXPECTED_HEAD` from `tests.unit._migration_head`.
Tests that name a specific revision for a targeted operation (downgrade,
upgrade to an intermediate state) use the literal revision identifier,
which is stable by definition.

## AI Subsystem Conventions

- Providers, models, routing entries, and invocations live in dedicated
  tables. Each has exactly one repository registered in the factory.
- The database never stores secrets. Provider credentials live in the
  operating system keyring; the database stores an opaque reference
  through `credential_reference`.
- The AI invocation log is append-only. The invocation repository
  overrides the base class's update and delete methods to raise
  `RepositoryError`; callers depend on the append-only contract.
- The AI invocation log never stores prompt or response bodies. Only
  identifiers, sizes, token counts, and metadata are recorded. Content
  lives in the user's own records.
- Task routing resolves in a fixed order: explicit routing, model-level
  default, provider-level default, application default. The resolution
  order is documented in the provider module and is not duplicated in
  repositories.
- Provider and model identifiers are unique within their scope. A
  provider's key is unique across the table; a model's identifier is
  unique within its provider. The schema enforces both invariants.
- AI providers are never invoked synchronously on the UI thread. The
  application layer schedules invocations on a worker; the presentation
  layer observes results through signals. The persistence layer is
  unaware of the scheduling.

## Evidence and Analysis Conventions

- Evidence records always carry provenance when available. The raw
  source text, page number, section title, extraction method, and
  extraction run identifier are recorded so that a reviewer can verify
  the value.
- Verification is explicit. Every evidence record carries a
  `verification_status`. Records produced by the AI subsystem carry the
  `ai_proposed` state and are excluded from synthesis until a user
  verifies them.
- Original and normalized values are stored separately. The original is
  never overwritten by a normalization pass; the normalized value is
  recorded in its own column.
- Analysis runs are append-only with respect to their inputs and
  results. Re-running an analysis creates a new run and preserves the
  previous one. The `analysis_input` table is the authoritative record
  of what the engine consumed.
- Statistical outputs are stored as JSON. The shape is documented in the
  statistical-methods documentation, not inferred from the schema.
- The engine version and library versions are recorded with every run.
  Reproducibility requires knowing which library produced a numerical
  result.
- Synthesis reports reference the evidence they consumed. Included and
  excluded evidence, exclusion reasons, limitations, and the
  reproducibility record are always stored with the report.

## Knowledge, Guides, Achievements, and Plans Conventions

- Knowledge nodes are identified by a stable, application-constructed
  key of the form ``kind:identifier``. The key is unique across the
  table; a different node kind requires a different key.
- Knowledge relationships are directed. The combination
  ``(source_node_id, target_node_id, relationship_kind)`` is unique. The
  ``grounding`` column distinguishes metadata-derived, user-linked, and
  AI-proposed edges. AI-proposed edges must never be presented as
  established facts.
- Research guides preserve citations. Every source-derived claim carries
  a ``citation_record`` with the source type, the source identifier, and
  the quoted text when available. A claim without a citation is a
  general statement and is labeled as such.
- Achievement definitions are stored, not hard-coded. The ``key`` is
  stable; the definition may be revised. Unlocks are idempotent and
  unique per ``(achievement_id, user_key)``.
- User activity records are append-only. The repository overrides the
  base class's update and delete methods to raise ``RepositoryError``.
  Callers depend on the append-only contract.
- Research plans are versioned by insertion. Successive saves create new
  rows. The project's most recent plan is retrieved by ordering on
  ``created_at``.
- Title candidates, methodology proposals, and analysis recommendations
  share a closed ``state`` enumeration. State changes are explicit; the
  repository exposes a ``set_state`` method rather than a general
  update.

## Migration-Head Convention

Tests must not hard-code the head revision. The head moves with every new
migration. Tests import `EXPECTED_HEAD` from `tests.unit._migration_head`.
Tests that name a specific revision for a targeted operation (downgrade,
upgrade to an intermediate state) use the literal revision identifier,
which is stable by definition.

The convention is enforced by
`tests/unit/test_migration_head_convention.py`. The module scans every
test file for string literals matching the current head and fails when
one is found. The scan is intentional: it makes the convention
self-enforcing and prevents regressions in future phases.

`declared_head_revision()` is available in production code for
diagnostics. It does not require a database URL and inspects the
migrations directory only.

## Search Provider Conventions

- Concrete adapters live in
  `academic_platform.infrastructure.search_providers` in modules named
  `<provider_key>_adapter.py`. They subclass `SearchProviderAdapter` and
  implement `descriptor`, `search`, and `test_connection`.
- Adapters raise only `ProviderError` subclasses outward. HTTP library
  exceptions, JSON parsing exceptions, and provider-specific error codes
  are translated at the adapter boundary.
- Adapters never mutate the `SearchRequest` they receive. They return a
  fresh `SearchResponse` on every call.
- Provider-specific request parameters are passed through the request's
  `extra` mapping. They are never first-class fields of `SearchRequest`.
- Provider-specific response fields that the application does not use
  are discarded. The `SearchHit.extra` mapping carries fields that later
  phases may consume; adapters populate it only with fields they have
  parsed successfully.
- Filter support and capabilities are declared in the descriptor. The
  orchestration layer reads them; it never inspects the adapter's
  implementation for feature detection.
- The provider key is stable and matches the module name. Renaming a
  provider key is a breaking change and requires a migration.
- The registry is a plain class, not a global. Tests construct their own
  registries. `default_registry()` returns the process-wide registry
  used by the application; mutating it is permitted only from the
  application bootstrap and from tests that intentionally exercise the
  process-wide registry.

## Search Source Service Conventions

- The application service lives in
  `academic_platform.application.search_sources`. It never imports Qt.
- The service produces value objects (`SourceConfig`, `SourceRecord`)
  rather than ORM instances. Callers never see ORM state.
- Every write operation validates the resulting configuration before
  persisting it. Validation is fail-closed: an invalid configuration is
  not persisted.
- Every write operation runs inside a transaction boundary. The service
  uses a per-call repository manager that opens a fresh session per
  operation and closes it when the operation completes.
- The service raises typed exceptions: `SourceNotFoundError` for missing
  sources, `SourceValidationError` for validation failures. It never
  raises repository-layer or provider-layer exceptions directly.
- The built-in source catalog is data. Adding a new built-in source is a
  matter of adding an entry; no other module needs to change.
- The installer preserves user-editable fields. When a built-in source
  already exists, only the display-level fields the application ships
  are refreshed; `enabled`, `result_limit`, and `timeout_seconds` are
  preserved.
- URL validation is performed by a dedicated module in the infrastructure
  layer. The application service calls it; it never re-implements the
  policy.

## HTTP Client Conventions

- The HTTP client lives in `academic_platform.infrastructure.http`. It
  never imports Qt.
- Adapters construct a client through `HttpClientFactory`. They never
  construct `httpx.Client` directly.
- Clients are constructed once per adapter and closed when the adapter
  is disposed. The `HttpClient` context manager closes the underlying
  transport on exit.
- The client raises only `HttpClientError` subclasses. Adapters catch
  those and raise the corresponding provider-layer errors.
- The client revalidates every destination. Adapters do not bypass the
  revalidation; a destination that the client rejects is a destination
  the adapter must not attempt.
- The client never logs request bodies, response bodies, or
  credentials. Retry attempts are logged at DEBUG level with the
  attempt number, the sleep duration, and the destination host only.
- Response bodies are read through the bounded reader. Adapters do not
  bypass the reader by accessing the raw `httpx` response.
- The client is safe to share across threads. Adapters that run in
  multiple worker threads may share a single client; they must not
  share it across processes.

## Concrete Search Provider Adapters

- Every concrete adapter lives in its own subpackage under
  `academic_platform.infrastructure.search_providers`. The subpackage
  contains the adapter, the URL builder, the response parser, and a
  registration module.
- The URL builder and response parser are separate modules. The adapter
  composes them; it does not implement URL construction or parsing
  inline.
- The response parser never raises on a missing optional field. It
  substitutes a neutral value and continues. It raises
  `ProviderResponseError` only when the top-level structure is not what
  the provider documents.
- Individual malformed items are skipped with a warning. A single bad
  item never invalidates a response.
- The adapter translates HTTP client exceptions into provider-layer
  exceptions. The mapping is documented on the adapter module and is
  preserved across providers.
- The registration module registers the adapter with the default
  provider registry at import time. Registration is idempotent and
  never raises.
- The adapter is constructed with an `HttpClient`. It never constructs
  its own client; the factory used by the search source service builds
  the client from the source's configuration.
- Adapters do not implement their own rate limiting. Rate limits are
  enforced by the shared HTTP client.
- Adapters do not implement their own retry logic. Retries are
  enforced by the shared HTTP client.
- Provider-specific limitations (for example, the absence of a dedicated
  open-access flag) are declared in the adapter's descriptor. They are
  documented in the descriptor's notes and in the adapter module.

## Provider-Specific Parsing Conventions

- The response parser reconstructs provider-specific representations
  into provider-neutral fields. A reconstruction that is lossy (for
  example, converting JATS XML or an inverted abstract index into plain
  text) is documented on the parser module.
- The parser never raises on a missing optional field. It substitutes a
  neutral value and continues. Individual malformed items are skipped
  with a warning.
- The parser raises `ProviderResponseError` only when the top-level
  structure is not what the provider documents.
- Provider-specific identifiers are extracted from the representation
  the provider returns and normalized to a stable form. DOIs are
  normalized to lowercase without the URL prefix. OpenAlex identifiers
  are extracted from the work URL.
- The parser prefers the provider's current field name over the legacy
  field name when both exist. OpenAlex's `primary_location.source` is
  preferred over `host_venue`; the fallback is documented.
- The parser never performs network access. Reconstructions that would
  require additional requests are not performed.

## Adapter Sorting and Filtering Conventions

- Adapters apply the requested sort order locally only when the provider
  does not support sorting natively. When the provider supports
  sorting, the adapter pushes the sort parameter down to the provider.
  The choice is documented in the adapter module.
- Adapters apply filters locally only when the provider does not support
  them natively. Adapters that push filters down do not re-apply them
  locally. The orchestration layer reads the adapter's `filter_support`
  to decide which behavior applies.
- Provider-specific limitations on sorting and filtering are declared in
  the adapter's descriptor. They are documented in the descriptor's
  notes and in the adapter module.
- Adapters that require an API key declare `requires_api_key=True` in
  their capabilities. The factory used by the source resolver passes the
  resolved secret to the HTTP client; the adapter itself never reads the
  secret.
- Adapters that use a provider-specific header for authentication
  declare the header name in the factory. The default is `X-API-Key` for
  providers that do not document a specific header.
- Adapters that apply sorting or filtering locally must apply the
  transformation to the full result set returned by the provider, not
  only to the first page. When the provider's pagination is exhausted,
  the transformation is complete.

## Multi-Endpoint Adapter Conventions

- Adapters that require multiple provider endpoints compose the calls
  internally. The provider-neutral `SearchProviderAdapter` interface is
  unchanged; callers see a single `search` method.
- Each response shape has its own parser method. The parser module
  exposes one method per shape and a composition helper that combines
  the results. Adapters do not merge parser outputs inline.
- Optional secondary calls — for example, fetching abstracts after a
  summary — are allowed to fail without failing the whole search. The
  adapter logs the failure and returns the primary results with the
  optional fields left empty.
- Adapters expose a configuration flag for optional secondary calls so
  that operators can disable them. The flag defaults to the
  application's desired behavior and is set through the source's
  configuration.
- Provider-specific rate limits are honoured through the shared HTTP
  client. Multi-endpoint adapters that issue multiple requests per
  search do not implement their own rate limiting; the client's limiter
  is shared across all requests issued by the adapter.
- The identifier list sent to a provider that expects comma-separated
  identifiers is joined without spaces. The builder is the single place
  that performs the join.

## Query-Composition Adapter Conventions

- Adapters whose provider expresses filters as query-string clauses
  compose those clauses in the URL builder, not in the adapter. The
  builder is the single place that constructs the final query.
- Clause composition uses the provider's documented syntax. Adapters
  never invent clause forms; each clause is verified against the
  provider's documentation before implementation.
- Free-text queries are parenthesized when combined with clauses to
  avoid operator-precedence ambiguity. The parenthesization is applied
  by the builder.
- Year filters that the provider expresses as date-range clauses emit
  open bounds where the request omits one side. The builder uses the
  provider's documented sentinel values (for example, `1000-01-01` and
  `3000-12-31`) rather than emitting an unbounded clause.
- Cursor-based pagination is preferred over page-based pagination when
  the provider supports both. Adapters emit a cursor parameter only when
  the request carries one; the initial request omits the cursor.
- Sort parameters use the provider's documented identifiers. Adapters
  map the application's `relevance`, `date_desc`, and `date_asc` modes
  to the provider's sort keys and document the mapping in the adapter
  module.

## XML-Based Provider Adapters

- Adapters whose provider returns XML use the standard library's
  `xml.etree.ElementTree`. No additional dependency is introduced for
  XML parsing.
- Namespaces are handled explicitly. The adapter defines helper
  functions that produce fully qualified tag names for each namespace
  the provider uses. The helpers are private to the parser module.
- The parser is self-contained: it extracts the fields the application
  uses and ignores the rest. It does not attempt to be a
  general-purpose XML processor.
- Malformed entries are skipped with a warning. The parser raises
  `ProviderResponseError` only when the root element or the top-level
  structure is not what the provider documents.
- Content types that the provider returns and that the shared HTTP
  client does not accept by default are added to the client's allow-list
  by the adapter's factory. The exception is scoped to the adapter and
  is documented in the adapter module.
- Preprint servers that do not expose a citation count or an
  open-access flag declare the corresponding capabilities as false or
  report a fixed value derived from the provider's policy. The choice is
  documented in the adapter module.

## Publication Normalization Conventions

- The canonical publication model is immutable. Merging two instances
  produces a new instance; the originals are not modified. Callers that
  need mutation construct a new instance or use `dataclasses.replace`.
- Keys are derived from DOIs or from provider identifiers, never from
  titles or author names. A missing identifier means the hit cannot be
  normalized; the normalizer reports the skip rather than fabricating an
  identifier.
- DOIs are normalized before comparison: lowercase, without the
  `https://doi.org/` or `doi:` prefix. The normalizer and the
  deduplicator share a single normalization helper.
- Deduplication is conservative. Publications are considered duplicates
  only when they share a normalized DOI or when their keys are equal.
  Title-only matching is not performed.
- Persistence is idempotent. Writing the same publication twice updates
  the existing row. Existing fields are preserved; only missing fields
  are filled. This protects user edits made through the UI.
- Source providers are recorded as a sorted, de-duplicated tuple.
  Duplicate entries are not stored.
- Normalization and deduplication are pure: they never touch the
  database. Persistence is a separate step performed by the application
  service inside a caller-supplied unit of work.

## Search Orchestration Conventions

- The orchestrator is the only application-layer component that
  coordinates multiple adapters. Callers do not run adapters directly
  except for connectivity tests.
- Adapters are executed on a bounded thread pool. The pool size is
  driven by the request's `max_concurrency`; the orchestrator does not
  use an unbounded pool.
- Failures are isolated per source. A failure in one adapter never
  aborts the whole search. The failure is recorded as a `SourceOutcome`
  with status `FAILED`; the remaining sources proceed.
- Adapter exceptions other than `ProviderError` are caught at the
  orchestrator boundary and reported as failures. The orchestrator logs
  the unexpected exception with a full stack trace but does not re-raise
  it.
- Session and result rows are recorded only after the search has
  completed. A failure during search never leaves a partial session in
  the database.
- The orchestrator never commits. It runs inside a unit of work supplied
  by the caller.
- The request's `record_session` flag allows callers to run a search
  without persisting it. This is used by diagnostics and by the
  application's own connectivity tests.
- The orchestrator's partial flag is True when at least one source
  succeeded and at least one source failed. This allows the
  presentation layer to distinguish a total failure from a partial one.
- The orchestrator sorts outcomes by display name so that per-source
  status is presented in a stable order.

## Background Execution Conventions

- Long-running work — network requests, document processing, model
  inference, statistical analysis, and report generation — is executed
  on a background thread. The UI thread never blocks.
- The Qt worker pattern is used consistently: a `QObject` moved to a
  `QThread`, with results delivered through signals. The worker never
  touches the UI directly.
- Workers catch all exceptions at their boundary and convert them into
  a value the UI can render. The worker never lets an exception reach
  the Qt event loop.
- Workers are single-use. A fresh worker is constructed for each
  operation, and the thread is torn down once the operation completes.
  Long-lived workers that process multiple operations are avoided
  because they complicate cancellation and error handling.
- The thread handle is retained by the caller until the completion
  callback has been invoked. Releasing the handle before the operation
  completes can cause the thread to be destroyed while it is still
  running.
- The presentation layer never calls a synchronous service method from
  the UI thread when the service may perform network access. Synchronous
  service methods that are known to be cheap — pure computations, local
  reads, or in-memory queries — may be called directly.
- Controllers and services never construct their own threads. Thread
  ownership is a presentation-layer concern; the application layer is
  synchronous by design.

## Source Management UI Conventions

- Source management is a modal dialog. It is not embedded in the
  Settings page as an always-visible list, and it is not embedded in
  the Discover page. This keeps the two surfaces consistent and avoids
  duplicating the management logic.
- The dialog obtains the application-layer service from the main
  window. It never reads the database directly.
- Testing a source is synchronous and bounded by the source's
  configured timeout. The dialog displays a busy cursor while the test
  runs. Long-running tests across many sources are performed one at a
  time; there is no batch-test action.
- The dialog emits a single `sources_changed` signal after any
  persisted change. Parent surfaces connect the signal to their own
  refresh method; the dialog does not know which surfaces are
  listening.
- Built-in sources may be disabled but not removed. The Remove action
  is hidden for built-in sources rather than disabled; a hidden action
  is unambiguous, while a disabled action invites the user to wonder
  why it is disabled.
- The edit form exposes only the fields that may be changed without
  risking the source's identity. The key and the provider key are not
  editable.
- Form validation is provided by the form dialog's validator callables.
  The validators enforce the same rules as the persistence schema and
  the source configuration value object. Validation is fail-closed: an
  invalid value disables the submit button rather than allowing the
  submission and rejecting it later.
- The dialog's error reporting uses the standard message dialog with
  the error kind. It does not attempt to render validation errors
  inline; the form dialog already does that for field-level issues.

## File Storage Conventions

- The file storage service lives in
  `academic_platform.infrastructure.file_storage`. It never imports Qt.
- The service is the only component that reads, writes, or deletes
  document files. Other components receive paths and checksums through
  the service.
- Paths are resolved with `Path.resolve()` before use. A path that
  cannot be resolved raises `FileStorageValidationError`.
- Checksums use SHA-256, lowercase hexadecimal. The algorithm is fixed;
  the schema stores the checksum in this form.
- Streaming is mandatory for file content. Checksums and copies are
  computed in fixed-size chunks; the service never reads a whole file
  into memory.
- Managed copies are written atomically: a temporary file in the same
  directory, then a rename. A crash during the copy leaves no partial
  file.
- Managed filenames are derived from the checksum. Two imports of
  identical files resolve to the same managed path. The original
  extension is preserved when it is short and alphanumeric; otherwise a
  neutral extension is used.
- Deletion is explicit. The service does not delete a file as a side
  effect of any other operation. Deletion of a managed copy refuses to
  operate outside the managed root.
- The service never spawns subprocesses and never performs network
  access. It does not follow symlinks in a way that could escape the
  managed root.
- Size limits are enforced before any copy begins and again on the
  final file. The default limit is one gigabyte; callers may lower it
  through the configuration.

## Library Import Conventions

- The import coordinator lives in
  `academic_platform.application.library_import`. It never imports Qt.
- The coordinator performs validation and orchestration only. It never
  reads file contents; checksum computation and file copies are
  delegated to the file storage service.
- Duplicate detection uses the document repository's
  `find_by_checksum`. Filenames are not used for duplicate detection.
- The document's stable key is derived from the checksum. Two imports of
  identical files resolve to the same key; the second import is a no-op
  and returns the existing key.
- The coordinator never deletes source files. The user's originals are
  left untouched in both storage modes.
- The import dialog is a thin presentation layer. It renders the plan
  returned by the coordinator and returns the user's selection. It
  performs no validation and no filesystem operations.
- Import execution runs synchronously inside the dialog. The dialog
  displays a busy cursor while the import runs. Long imports across many
  files are not scheduled on a background thread at this stage because
  the coordinator's work is bounded and the interface reports progress
  through the summary line.
- The dialog emits a single `imported` signal after a successful
  import. Callers connect the signal to refresh their views.

## Document Processing Conventions

- Extractors live in
  `academic_platform.infrastructure.document_processing`. They never
  import Qt.
- Extractors return typed result objects. They never return raw
  library data structures.
- Extractors open files read-only. They never modify the source file.
- Extractors stream their input. They never load the whole document
  into memory when the underlying library supports incremental access.
- Page-level failures are isolated in non-strict mode. Strict mode is
  used by tests and by callers that require complete extraction.
- Extractors raise only `DocumentProcessingError` subclasses. They
  translate library-specific exceptions at their boundary.
- The application service wraps an extractor and persists its result
  through the repository layer. It never commits; it runs inside a unit
  of work supplied by the caller.
- Re-extraction replaces derived data (chunks) atomically. A failed
  re-extraction does not remove the previous chunks unless the caller
  explicitly asks for a reset.
- Embedded metadata that has been reviewed by the user is preserved
  across re-extraction runs. Unreviewed metadata is replaced.
- Normalization helpers are documented in the extractor module. Their
  behaviour is deterministic and independent of the operating system.

## Metadata Extraction Conventions

- Metadata extractors live in
  `academic_platform.infrastructure.document_processing`. They never
  import Qt.
- Extractors return typed result objects. They never return raw library
  data structures.
- Extractors are deterministic. The same input produces the same
  output.
- Extractors never invent a value. A field that cannot be extracted is
  left `None` and its confidence is 0.0.
- Confidence values are documented per field. They reflect the
  reliability of the evidence, not the size of the field.
- The extractor accepts a `PdfExtractionResult` when one is already
  available. It does not re-extract text unnecessarily.
- Placeholder values written by common office tools are rejected. The
  rejection list is maintained in the extractor module.
- The extractor is a pure transformation over the input. It does not
  persist anything; persistence is the responsibility of the
  application service.
- Heuristics that recognize a well-known pattern (DOI, arXiv
  identifier) are compiled as module-level regex constants with
  explanatory comments. Their behaviour is documented in the module
  docstring.

## Duplicate Detection Conventions

- The duplicate detection subsystem lives in
  `academic_platform.application.deduplication`. It never imports Qt.
- Detection policies live in `policy.py` and are immutable. A policy
  that disables every signal is rejected at construction.
- The detector exposes the individual signals it evaluates. A decision
  is not a boolean alone; it carries the matches and the decisive
  signal so the presentation layer can explain the outcome.
- Normalization helpers used by the detector are module-level
  functions. They are deterministic and independent of the operating
  system.
- Title normalization includes Unicode NFKC normalization, case
  folding, punctuation removal, and whitespace collapse. Author
  normalization is identical, followed by sorting.
- The detector never merges existing documents. It reports a candidate
  as a duplicate of an existing document. Merging existing rows is a
  separate operation that is not implemented at this stage.
- The detector is deterministic. The same candidate and library produce
  the same decision on every run.
- The detector never trusts the checksum of a file it did not compute.
  Callers must supply a checksum produced by the file storage service.
- The metadata fallback is bounded. The detector reads at most
  `metadata_candidate_limit` rows when it performs a metadata
  comparison.

## OCR Conventions

- OCR components live in
  `academic_platform.infrastructure.document_processing`. They never
  import Qt.
- The extractor produces `PdfExtractionResult`-compatible output so
  that downstream consumers do not need to distinguish OCR-produced
  text from native text.
- Tesseract is invoked through the `pytesseract` wrapper. The extractor
  does not call the Tesseract binary directly.
- The availability probe never raises. It reports the reason a backend
  is unusable through `OcrAvailability`.
- Language validation is performed before any page is processed. A
  missing language pack raises `OcrLanguageError`.
- Per-page failures are isolated in non-strict mode. Strict mode is
  used by tests and by callers that require complete extraction.
- Raster images are held in memory and released as soon as Tesseract
  returns. The extractor never writes intermediate files to disk.
- Word-level block extraction is optional. When the
  `image_to_data` call fails, the extractor logs a warning and returns
  page-level text without blocks. A block extraction failure never
  aborts the page.
- The `min_characters_per_page` threshold distinguishes meaningful
  pages from pages that produced very little text. A page below the
  threshold is recorded with its actual text and a warning; the
  extractor never discards the page silently.
- The document extraction service records the OCR outcome on the
  document asset's `ocr_state` field. States are `completed`, `failed`,
  and `not_required`.

## Full-Text Search Conventions

- The full-text search subsystem lives in
  `academic_platform.infrastructure.full_text_search`. It never imports
  Qt.
- FTS5 table names and column names are declared once in
  `academic_platform.infrastructure.database.models.fts`. Other modules
  import them; they never duplicate the string literals.
- FTS5 row identifiers are derived deterministically from the
  underlying entity. The indexer never scans the FTS5 table to find a
  row to replace.
- The indexer deletes previous rows for the target entity before
  inserting new ones. The operation is idempotent.
- The indexer never modifies the primary tables. It reads values the
  application layer has already persisted.
- The query service passes MATCH expressions to FTS5 unchanged. It
  validates only that the query is not empty.
- Snippets are produced by FTS5's `snippet` function. The marker
  strings are module-level constants; the presentation layer replaces
  them with the UI's highlight styling.
- The rebuilder clears every FTS5 table before repopulating it.
  Partial indexes are never left behind.
- The rebuilder records per-entity failures as warnings; it does not
  abort the rebuild for a single failure.
- Rebuilding the index is an explicit operation. It is not performed
  automatically on startup; the application rebuilds only after a
  schema change or a detected inconsistency.

## Library Page Conventions

- The library page lives in `academic_platform.ui.pages.library`. It
  reads only through the application-layer `LibraryService`.
- The page never touches the database or the filesystem directly.
- The table is rendered with a `QAbstractTableModel`. The model holds
  value objects (`LibraryEntry`); it never holds ORM rows.
- Sorting is performed by the application service, not by the model.
  The model exposes the sortable columns; the service performs the sort
  and returns an ordered page.
- Search is debounced. Typing starts a short timer; the query runs when
  the timer fires or when the user presses Enter.
- Filters are updated explicitly. The page holds a `LibraryFilter`
  instance; the service reads it on each refresh.
- The detail panel is populated from the entry alone. Loading chunks on
  demand is deferred to the reader, which is delivered in a later
  phase.
- Removing a document from the library removes the ORM row and the FTS5
  rows. It never deletes the underlying file. Deleting the file is a
  separate operation performed by the file storage service when the
  user confirms it.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The page emits typed signals for actions the shell handles. Signals
  use the imperative form (`open_document_requested`,
  `add_to_collection_requested`, `add_to_project_requested`).
- Notifications are published through the notification service. The
  page does not display transient messages itself.

## Document Reader Conventions

- The reader is a hidden destination. It is not listed in the primary
  navigation. The shell activates it programmatically when the user
  opens a document.
- The reader page lives in `academic_platform.ui.pages.reader`. It
  reads through the application-layer `DocumentReaderService`.
- The application service returns PNG-encoded image bytes. The
  presentation layer converts them into a Qt pixmap. The service never
  imports Qt.
- Page rendering is synchronous. A background pipeline is delivered in
  a later phase if needed.
- Rendered pages are cached in a bounded LRU cache. The cache key
  includes the document key, the page number, and the DPI. The cache is
  evicted when the document is closed.
- The reader never modifies the source PDF. Files are opened read-only.
- The reader never disposes the document handle while the user is
  reading it. The handle is released when the user closes the reader or
  opens a different document.
- The reader participates in the shell's lifecycle contract. Its
  `on_deactivated` method is a no-op because the document remains open
  while the user navigates elsewhere.
- The reader emits typed signals for actions the shell handles:
  `close_requested` and `page_changed`. Signals use the imperative
  form.
- Keyboard shortcuts are installed with the
  `WidgetWithChildrenShortcut` context so that they only fire when the
  reader is focused.
- Error reporting uses the standard message dialog with the error kind.
  Page-level rendering errors are displayed inline in the page view
  instead of as a dialog, because they are recoverable by scrolling
  away.

## Annotation Conventions

- The annotation application service lives in
  `academic_platform.application.annotations`. It never imports Qt.
- Annotation kinds and colors are closed enumerations. Adding a new
  kind or color requires a schema migration and an update to the
  application service's view model.
- The kind of an annotation cannot be changed after creation. Updates
  apply only to mutable fields: body, text excerpt, anchor, color, and
  page number.
- The annotation service keeps the FTS5 note index in sync. Creating or
  updating an annotation re-indexes it; deleting an annotation removes
  its FTS5 row.
- The service never modifies the source PDF. Annotations are separate
  records linked to the document and its page.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Exports are read-only. Exporting annotations never writes to the
  database.
- The annotation panel is a self-contained widget. It reads and writes
  through the application service and emits typed signals for actions
  the reader handles.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The panel is told which document and page are current by the reader
  page. It never inspects the reader's internal state.

## In-Document Search Conventions

- The in-document search subsystem lives in
  `academic_platform.application.document_search`. It never imports Qt
  and never reads the PDF file.
- The service reads the `document_chunk` table so that results match
  what the extractor, the OCR pipeline, and the indexer produced.
- Literal substring matching is the default. Regular expressions are
  opt-in. The service never interprets a query as a regular expression
  without an explicit request.
- An invalid regular expression raises `DocumentSearchError` with a
  descriptive message. The panel surfaces the error to the user.
- Empty queries return an empty result. The service never searches the
  empty string.
- Snippets carry highlight markers around matched terms. The marker
  strings are module-level constants. The presentation layer replaces
  them with the UI's highlight styling.
- The match limit is enforced. The result's `truncated` flag records
  whether the limit was reached.
- The service never modifies the database or the PDF. It is a pure
  read operation over persisted chunks.
- The panel is a self-contained widget. It reads through the
  application service and emits typed signals for actions the reader
  handles.
- Keyboard access is provided through the standard Find shortcut
  (`Ctrl+F`), installed with the reader's shortcut context.

## Document Linking Conventions

- The document linking subsystem lives in
  `academic_platform.application.document_linking`. It never imports
  Qt.
- Linking is a purely relational operation. The service never resolves
  the document's file path.
- A project link is implemented through a project-linked collection.
  The service creates the collection on demand and reuses it. The
  collection's key is `project-<project-key>`; its title is
  `<project-title> — documents`.
- The service is idempotent. Duplicate link and unlink operations are
  no-ops; they return `affected = 0` rather than raising.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The linking dialog computes a diff between the initial state and the
  user's selection. It applies only the difference.
- Failures during apply are reported as an aggregate error. The dialog
  reloads its state so the user sees what succeeded.
- The reader's "Link to…" action is enabled only when a document is
  open.
- The library's context menu actions for linking are handled by the
  shell; the library page emits typed signals
  (`add_to_collection_requested` and `add_to_project_requested`).
- The dialog is a modal Qt widget. Its internal fields are accessed by
  tests via the underscore-prefixed attributes, which is the project's
  convention for Qt widgets whose state is intentionally exposed to UI
  tests.

## Assistant Handoff Conventions

- The handoff subsystem lives in
  `academic_platform.application.assistant_handoff`. It never imports
  Qt.
- The handoff payload is immutable. It is a read-only snapshot of the
  reader's current context.
- Metadata is read from the metadata repository. The service never
  re-extracts metadata.
- The page excerpt is bounded. The default bound is 2000 characters; a
  truncated excerpt ends with an ellipsis.
- The handoff store is process-local. It is bounded and evicts the
  oldest entry when the bound is exceeded. Later phases replace it with
  a persistent store; the interface is stable.
- The dialog rebuilds the payload on every option change so the
  preview matches the user's selection.
- The dialog emits a typed signal for actions the shell handles.
  Navigation to the assistant is the shell's responsibility.
- The dialog is a modal Qt widget. Its internal fields are accessed by
  tests via the underscore-prefixed attributes, which is the project's
  convention for Qt widgets whose state is intentionally exposed to UI
  tests.

## Research Project Conventions

- The research project service lives in
  `academic_platform.application.projects`. It never imports Qt.
- The service returns immutable value objects, never ORM rows.
- Validation is fail-closed. `ProjectValidationError` carries every
  issue at once.
- Creating a project also creates its linked collection. The
  collection's key is `project-<project-key>`; its title is
  `<project-title> — documents`.
- Updating a project's title synchronizes the linked collection's
  title.
- Deleting a project removes its children and its linked collection
  through the model's cascade. Linked documents are not deleted.
- Every mutation writes an audit event through the audit repository.
  Action identifiers are stable and follow the
  `<entity>.<operation>` convention.
- Audit event failures are logged but never prevent the primary
  mutation. The audit trail is diagnostic, not authoritative.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Question kinds are restricted to the closed set declared by the
  schema. Adding a new kind requires a schema migration and an update
  to the validation helper.
- Task positions are assigned sequentially on creation. The service
  does not enforce a contiguous range; the reader should not assume
  one.

## Projects Page Conventions

- The projects page lives in `academic_platform.ui.pages.projects`. It
  reads and writes only through the application-layer `ProjectService`.
- The page never touches the database directly.
- The list is rendered with a `QAbstractTableModel`. The model holds
  value objects (`ProjectView`); it never holds ORM rows.
- The stage filter is a view-level operation. It filters the model
  rather than querying the service with a filter, because the service
  returns the full list and the model is small.
- The detail panel is populated on selection. It reloads the project's
  questions and tasks on every selection and after every mutation.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The form dialog is used for creation and editing. The page never
  constructs ad-hoc input widgets.
- The page emits typed signals for actions the shell handles. Signals
  use the imperative form.
- The page never modifies documents. Document linking is delivered by
  the reader and library flows.
- The empty state carries an enabled action that opens the create
  dialog.
- Column definitions live in the table model's `COLUMNS` tuple.
  Adding a column is a matter of adding an entry to `COLUMNS` and a
  corresponding branch in `_display_value`.

## Collection Service Conventions

- The collection service lives in
  `academic_platform.application.collections`. It never imports Qt.
- The service returns immutable value objects, never ORM rows.
- Validation is fail-closed. `CollectionValidationError` carries every
  issue at once.
- The project-linked collection key convention `project-<project-key>`
  is shared with the document linking service. Adding a new convention
  requires updating both services in the same phase.
- Manual items are permitted only on collections whose kind allows
  them. Project-linked and smart collections reject manual item
  additions.
- Reordering is atomic: new positions are applied in a single flush.
- Every mutation writes an audit event through the audit repository.
  Action identifiers use the `<entity>.<operation>` convention.
- Audit event failures are logged but never prevent the primary
  mutation. The audit trail is diagnostic, not authoritative.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Smart and saved-search collections require a JSON object as their
  filter payload. The service validates the payload's shape but does
  not interpret its contents.

## Collections Page Conventions

- The collections page lives in
  `academic_platform.ui.pages.collections`. It reads and writes only
  through the application-layer `CollectionService`.
- The page never touches the database directly.
- The list is rendered with a `QAbstractTableModel`. The model holds
  value objects (`CollectionView`); it never holds ORM rows.
- The kind filter is a view-level operation. It filters the model
  rather than querying the service with a filter, because the service
  returns the full list and the model is small.
- Project-linked collections are read-only from this page. The edit
  button is disabled and the error message guides the user to the
  project's page and the document linking workflow.
- The items tab exposes add, edit note, move up, move down, and remove
  actions. Reordering is applied through the service's atomic
  `reorder_items` operation; the page never mutates item positions
  directly.
- The filter editor is enabled only for smart and saved-search
  collections. Other kinds have no filter payload; the editor is
  disabled and its content cleared on selection.
- The filter editor's contents are validated as JSON before being
  submitted to the service. A malformed payload produces an error
  dialog rather than a service call.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The form dialog is used for creation and editing. The page never
  constructs ad-hoc input widgets.
- Column definitions live in the table model's `COLUMNS` tuple.

## Smart Collection Conventions

- The smart-collection subsystem lives in
  `academic_platform.application.smart_collections`. It never imports
  Qt.
- The filter is an immutable value object parsed from JSON. Unknown
  fields are rejected; malformed values are rejected with a list of
  issue messages.
- Every filter field is optional. An empty filter matches every
  document.
- The evaluator is a pure read operation. It never persists anything.
- The evaluator's item type is `document`. New item types require a
  schema extension and an update to the evaluator.
- The evaluator batches its metadata and annotation lookups per
  document so that a filter that references metadata or annotations
  does not issue a query per item.
- The evaluator applies its limit after filtering. The limit does not
  bound the underlying query.
- The collection service short-circuits to the evaluator for smart
  collections. Callers that want to evaluate a smart collection
  explicitly use `evaluate_smart_collection`.
- The presentation layer disables manual item actions for smart
  collections and displays a hint label explaining that the items are
  computed. The user changes the item set by editing the filter.
- The Filter tab is selected automatically when a smart collection is
  first shown.

## Research Task Conventions

- The task subsystem lives in
  `academic_platform.application.tasks`. It never imports Qt.
- Statuses and priorities are closed enumerations. Adding a new value
  requires a schema migration and an update to the validation helper.
- The legacy `completed` boolean is derived from the status. Any code
  that sets the status must also set `completed` consistently; the
  service does this in a single place.
- Setting a task to `done` records a completion timestamp if one is not
  already present. Moving a task out of `done` clears it. The service
  is the single place that manages the timestamp.
- Milestones are tasks with the `is_milestone` flag set. There is no
  separate table. Marking and clearing the flag writes dedicated audit
  events.
- Due dates are stored as UTC. The service accepts a datetime or an
  ISO-8601 string. `clear_due_at` is distinct from `due_at=None`.
- Progress summaries are computed on demand. The service does not
  maintain a materialized progress record.
- Every mutation writes an audit event through the audit repository.
  Action identifiers use the `<entity>.<operation>` convention.
- Audit event failures are logged but never prevent the primary
  mutation. The audit trail is diagnostic, not authoritative.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The projects page hosts the milestones panel as a third tab. The
  panel is told which project is current by the page; it never inspects
  the page's state.

## Project Export Conventions

- The export subsystem lives in
  `academic_platform.application.project_export`. It never imports Qt.
- The service is a pure read operation. It never writes to the
  database.
- The output schema is versioned. The version is recorded under
  `schema_version`. Adding new fields is forward-compatible; removing
  fields requires a version increment.
- The Markdown output is deterministic. Given the same project and
  options, the service produces the same text.
- Existing files are not overwritten unless the caller passes
  `overwrite=True`. The dialog exposes an overwrite checkbox and
  defaults it to off.
- The export does not embed binary content. Documents are referenced
  by their keys and metadata.
- Documents that are missing from the library are reported with a
  `missing_from_library` flag rather than silently omitted.
- Sections are independent and selectable. The service composes the
  payload only from the selected sections; unselected sections do not
  appear in the output at all.
- The milestones section duplicates entries from the tasks section when
  both are selected. The duplication is deliberate and is documented in
  the service module.
- Suggested filenames are derived from the project's key or title and
  are sanitized so that they contain only letters, digits, hyphens, and
  underscores.

## Validator Script Conventions

- Every phase validator lives in `scripts/validate_phase_<letter>.py`.
- Validators use a temporary directory and an in-memory database. They
  never touch the user's data and never contact the network.
- Validators print a per-check report and write a JSON document when
  `--report` is supplied.
- Validators do not import `pytest`. A local approximate comparator is
  used when an approximate comparison is required.
- Validators exit with code `0` when every check passes and code `1`
  when any check fails.
- Each check reports a stable, human-readable name and a short detail
  string that identifies what was verified or what failed.
- The corresponding acceptance document lives at
  `docs/phases/phase_<letter>_acceptance.md` and records the scope,
  the acceptance criteria, the automated acceptance procedure, and the
  known limitations.

## Research Assistant Conventions

- The research assistant page lives in
  `academic_platform.ui.pages.research_assistant`. It never touches
  the database directly.
- Every section inherits from `AssistantSection`, which inherits from
  `BasePage`. Sections participate in the page's lifecycle and expose
  two additional contracts: `summary` and `reset`.
- Sections never communicate with each other directly. Cross-section
  coordination goes through the page or, in later phases, through the
  research plan service.
- The page owns a single `QStackedWidget` and a `SectionHost` per
  section. Sections remain constructed for the lifetime of the page so
  that work is preserved across navigation.
- The sidebar renders the section's name and summary. The page never
  fabricates a summary; the summary comes from the section itself.
- The review section's summary provider is set by the page at
  construction time. The section never inspects other sections
  directly.
- Sections that hold work override `summary` to describe their state
  and `reset` to clear it.
- Sections use the shared helpers in
  `academic_platform.ui.pages.research_assistant.sections._shared` for
  form widgets. The helpers are private to the sections package.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
- The page emits typed signals for actions the shell handles. Signals
  use the imperative form.

## Topic Workspace Conventions

- The topic workspace lives in
  `academic_platform.application.topic_workspace`. It never imports Qt.
- The workspace stores its extended fields in the project's
  `project_metadata` JSON column under the key `topic_workspace`. The
  project's dedicated `topic` column carries the broad subject.
- The `topic_workspace` key is stable. Renaming it is a breaking change
  that requires a migration.
- When the workspace is not attached to a project, it holds a draft in
  memory. The draft can be attached later through
  `merge_into_project`.
- Validation is fail-closed. `TopicWorkspaceValidationError` carries
  every issue at once. Empty values are permitted.
- Every successful write records an audit event. Action identifiers
  use the `<entity>.<operation>` convention.
- The workspace never commits. It runs inside a unit of work supplied
  by the caller.
- The section integration writes on every editor change. Writes are
  idempotent because the service persists the whole draft on each
  change.
- The completeness report treats the broad subject and the research
  problem as essential. The other fields contribute to the ratio but
  do not block readiness.

## Clarifying Question Conventions

- The clarifying-question engine lives in
  `academic_platform.application.clarifying_questions`. It never
  imports Qt.
- The engine is a pure function over its inputs. It never mutates the
  draft, never persists anything, and never calls an AI provider.
- Rules are small functions that return either a `ClarifyingQuestion`
  or `None`. They never raise on missing data; they return `None`.
- Rules emit a question only when the missing information materially
  affects the next workflow step.
- Questions carry a stable identifier derived from the target field
  and a rule-specific suffix. The identifier is used by the
  presentation layer to persist a dismissal.
- The engine sorts questions by priority and bounds the number of
  returned questions.
- The engine treats an unexpected rule exception as an error. A rule
  that raises is not silently ignored.
- The engine does not persist the user's answers. Persisting the answer
  is the workspace's responsibility.
- The presentation layer tracks dismissed identifiers for the duration
  of the session. Persisting dismissals across sessions is delivered in
  a later phase.

## Title Builder Conventions

- The title builder lives in
  `academic_platform.application.title_builder`. It never imports Qt.
- The engine is a pure function over its inputs. It never persists
  anything and never calls an AI provider.
- Patterns are small functions that return either a `TitleCandidate` or
  `None`. They never raise on missing data; they return `None`.
- Patterns emit a candidate only when the draft carries the fields the
  pattern requires. The engine never invents values the draft does not
  support.
- The alignment score is a bounded, documented formula. Weights are
  declared in the engine module and are covered by tests.
- The engine bounds the number of returned candidates.
- The service is the only component that writes. It persists candidates
  in the research title candidate repository and records audit events.
- Regeneration replaces only proposed candidates; accepted, rejected,
  and archived candidates are preserved.
- The presentation layer reads the current topic draft through the
  assistant page. The section never inspects the topic workspace
  service directly.
- The presentation layer exposes actions to accept, reject, and use a
  candidate. Destructive actions use the standard confirmation prompt.

## Title Comparison Conventions

- The comparison panel lives in
  `academic_platform.ui.pages.research_assistant.sections.title_comparison_panel`.
  It reads and writes only through the title builder service.
- The panel never recomputes a candidate's rationale or alignment. The
  service is the single source of truth.
- The panel refreshes from the service after every action. Local
  caching of candidate state is not permitted.
- Each candidate is rendered as a card. The card's state is exposed as
  a dynamic Qt property so that the stylesheet can key on it without
  rebuilding the stylesheet.
- The panel emits a typed signal for the working-title promotion. The
  signal carries the title text; the panel never writes to the working
  title field directly.
- Editing a candidate's title uses the standard prompt dialog with a
  validator. The service performs a second validation pass before
  persisting.
- The panel's actions are disabled when no candidate is selected. An
  action that would be a no-op (for example, accepting an already
  accepted candidate) is disabled rather than hidden.
- The service preserves the candidate's rationale, strengths,
  problems, and assumptions when the title is edited. Recomputing the
  alignment requires a fresh generation pass.
- The service records an audit event for every state change and for
  every title edit.

## Research Question Workspace Conventions

- The research-question workspace lives in
  `academic_platform.application.research_questions`. It never imports
  Qt.
- The workspace is anchored to a research project. Writes without an
  attached project raise `ResearchQuestionWorkspaceNotAttachedError`.
- The topic lives on the project's dedicated ``topic`` column. The
  problem and the gap live in the project's ``project_metadata`` JSON
  column under the ``research_question_workspace`` key. The primary
  question is mirrored as a research-question row with the
  ``is_primary`` flag set.
- The ``research_question_workspace`` key is stable. Renaming it is a
  breaking change that requires a migration.
- Validation is fail-closed for inputs. The service raises
  `ResearchQuestionWorkspaceValidationError` with every issue at once.
- The validation report is a separate operation. It describes the
  draft; it never blocks a write. Issues carry a severity of ``error``
  or ``warning``.
- Every successful write records an audit event. Action identifiers
  use the ``question.<operation>`` convention.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The presentation layer renders the validation report as a label
  whose severity drives its styling through a dynamic Qt property.
- Promoting a question clears the previous primary flag and updates
  the workspace metadata's primary question text in the same
  operation.