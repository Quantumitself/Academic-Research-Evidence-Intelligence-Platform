# Security

## Secrets

- API keys and credentials are never stored in plain-text configuration files.
- The operating system's secure credential storage is used where available.
- Credentials are never logged, echoed, or included in diagnostics.

## Imported documents

Imported documents are untrusted inputs. Embedded scripts, macros, and
instructions are treated as content to analyze, never as privileged commands.

## Network

- External URLs are validated before requests are issued.
- Only HTTPS is accepted unless HTTP is explicitly justified per source.
- Requests have timeouts and response-size limits.
- Redirects are restricted and destinations revalidated.

## Local services

The optional API service binds to loopback by default and requires explicit
user enablement and authentication before any network exposure.

## Configuration File Handling

- The configuration file is treated as untrusted input. It is validated
  against a strict schema on every load.
- Unknown fields and sections are rejected rather than ignored, so that a
  hand-edited file cannot silently introduce unintended state.
- The file must not contain secrets. API keys and credentials are stored in
  the operating system keyring. The schema forbids fields that would suggest
  secret storage.
- Writes are atomic and rotate the previous file to a `.bak` sibling. A
  crash during a save cannot leave a partially written configuration file.
- A file whose `schema_version` is newer than the application supports is
  rejected at startup rather than coerced. Downgrade is not attempted.
- The `--settings` diagnostic prints the effective configuration to stdout.
  It never prints secret values because none are stored in the file.

## UI Shell

- Keyboard shortcuts use `Qt.ShortcutContext.ApplicationShortcut`, which
  confines them to the application window and prevents interference with
  other running applications.
- The shell never executes content derived from page content. Pages emit
  typed signals; the shell dispatches only over the registered destination
  identifiers.
- Navigation requests with unknown identifiers are logged and ignored. They
  do not construct pages on demand and cannot be used to load arbitrary
  modules.
- The `can_close` contract allows pages to veto application exit while
  holding unsaved user input. It is not a security boundary and does not
  attempt to prevent forced termination.

## Database

- The SQLite database file lives under the application data directory and
  is never written outside it.
- The engine is created with `check_same_thread=False`. Application code
  obtains sessions through the `Database.session()` context manager, which
  is safe to call from worker threads. Direct DBAPI connection access is
  not permitted.
- Foreign key enforcement is enabled on every connection. Referential
  integrity is not optional.
- The `busy_timeout` PRAGMA prevents a reader from failing a writer
  immediately; it does not permit unbounded blocking.
- Journal mode `WAL` writes a sidecar `-wal` file next to the database.
  Backups must include the `-wal` and `-shm` files or must be taken after
  a checkpoint.
- The engine never logs SQL text unless `echo` is enabled. `echo` is not
  read from user settings and is enabled only during diagnostics.

## Core Tables

- **`user_profile`** stores only user-provided profile data. No secrets,
  no credentials, no API keys. The `key` column is constrained to
  lowercase ASCII and used only as an identifier.
- **`app_settings`** stores only installation-level identifiers and
  version numbers. No configuration payloads, no credentials. The
  user-editable configuration lives in `config.toml`; secrets live in the
  operating system keyring.
- **`audit_event`** is append-only. Application code never updates or
  deletes events. The `payload_json` column must not contain secrets,
  tokens, or document content; only structural metadata such as field
  names and identifiers is permitted.
- The check constraint on `app_settings` (`id = 1`) is a correctness
  guard, not a security boundary. It prevents accidental double rows; it
  does not prevent an attacker with direct database access.
- Migrations are applied transactionally. A failed migration leaves the
  database in the state it had before the migration started.

## Document Assets

- Imported documents are untrusted inputs. The application never executes
  embedded scripts, macros, or instructions from a document.
- The `location` column stores an absolute path or an application-relative
  path. The application never trusts a path from a document; paths come
  from the import dialog or from the managed library.
- Managed copies live under the application's library directory. The
  application never writes outside that directory.
- Referenced files remain under the user's control. The application reads
  them but does not modify them. A missing file is recorded through the
  `missing` flag; the application never deletes the reference without the
  user's explicit confirmation.
- Chunks of extracted text may be sent to AI providers when the user
  enables that behavior. The default is disabled. When disabled, a
  per-request confirmation is required before any excerpt is transmitted.
- Annotations are user data. They are stored separately from the source
  file and are included in backups.

## Search Sources

- Search source configurations never store credentials. The `auth_type`
  column records the authentication method; `credential_reference`
  stores an opaque identifier for a credential in the operating system
  keyring. The database is never used as a credential store.
- User-defined source URLs are validated before they are persisted. The
  validation rules are described in the network security section.
- Provider identifiers are unique across the table. The adapter registry
  resolves a provider by identifier; a duplicate identifier would cause
  adapter confusion and is rejected at the schema level.
- Search sessions record the query text and the per-source status as
  JSON. The recorded text is not redacted; users who disable search
  history in the settings must not have their sessions persisted. The
  application enforces this; the schema does not.

## AI Providers

- Provider credentials are never stored in the database. The
  `credential_reference` column holds an opaque identifier for a
  credential in the operating system keyring. The application never logs
  the credential value.
- Local providers use the runtime's HTTP endpoint. The application never
  loads a GGUF file directly; it relies on the runtime to manage model
  memory and inference. This keeps the application out of the memory-
  management business and reduces the attack surface.
- Provider endpoints are validated before they are persisted. The
  application permits loopback addresses for local providers and rejects
  private, link-local, and cloud metadata addresses unless a careful
  local-development exception applies.
- Task routing is authoritative. A provider that is not enabled is never
  invoked. A model that is not enabled is never invoked. The application
  refuses to route to a disabled target rather than silently falling
  back.
- Prompt templates are versioned. The `prompt_template_version` field on
  every invocation records which template produced the request; this
  makes it possible to audit the exact prompt shape used for a
  historical run without storing the prompt body.
- The AI subsystem never computes statistical outputs. Statistical
  calculations are the responsibility of the statistical engine; the AI
  layer only narrates and structures. This is enforced at the
  application layer.

## Evidence and Analysis

- Evidence records store the raw source text from which they were
  extracted. That text is user-owned content; it is not transmitted to
  any external service without an explicit user action. The default is
  local-only.
- The AI invocation log does not store prompt or response bodies. It
  stores identifiers, sizes, token counts, and metadata. Content is
  preserved in the user's own records, not duplicated in the log.
- Analysis inputs are stored with the run. Inputs may include derived
  values that came from evidence records. The link to the source
  evidence is preserved so that a support investigation can trace the
  input back to its origin.
- Synthesis reports reference the evidence they consumed. The reference
  list is not an authorization boundary; it is a provenance record.
- The evidence extraction pipeline treats document text as untrusted
  content. Instructions embedded in documents are never executed as
  application commands. The AI layer is instructed to treat document
  text as content to analyze, not as privileged instructions.

## Knowledge, Guides, Achievements, and Plans

- Knowledge nodes carry a stable, application-constructed key. The key
  is never derived from a user-supplied path or from document content
  without sanitization. Duplicate keys are rejected at the schema level.
- AI-proposed knowledge relationships carry the `ai_proposed` grounding
  state. The application presents them as proposals and does not treat
  them as facts until the user confirms.
- Research guides preserve citations. The quoted text and page number
  are recorded so that a claim can be verified without re-extracting the
  source. Guides never fabricate a citation; a missing source is
  recorded as an absent citation, not a fabricated one.
- Achievement unlocks are transparent. Definitions are stored in the
  database; unlocks are recorded with a trigger event. The system never
  awards an achievement for unreviewed AI-generated content or for
  actions the user did not perform.
- User activity records are append-only. The repository enforces the
  append-only contract; the database does not store prior versions.
- Research plans are versioned by insertion. Successive saves create new
  rows; the previous plans are preserved for auditability.

## Search Source URLs

- Every user-supplied URL is validated before it is stored and again
  before a request is issued. The validator rejects unsupported schemes,
  embedded credentials, loopback addresses (unless explicitly allowed
  for a local source), private addresses, link-local addresses, and
  cloud metadata addresses.
- The host is resolved and the resulting addresses are revalidated to
  reduce the risk of DNS rebinding. A domain that initially resolves to
  a public address and later resolves to a private address is rejected
  on the second resolution.
- The validator never performs a network request. It uses the operating
  system resolver only when the caller asks for resolution. The
  resolution is synchronous and is performed once per request.
- The default policy requires HTTPS. HTTP is accepted only when the
  caller explicitly allows it for a specific source. The setting is
  per-source, not global.
- Built-in sources ship with HTTPS base URLs and no credentials. User
  sources that require authentication must reference a credential by
  identifier; the credential itself lives in the operating system
  keyring and is never stored in the database.

## HTTP Client

- Every outbound request revalidates the absolute URL and the resolved
  destination through the URL safety validator. A URL that passed
  validation when a source was saved can later resolve to a different
  address; the client catches that.
- Redirects are not followed automatically. A redirect response is
  rejected after revalidating the destination. This prevents an attacker
  from using a trusted host as an open redirect to a private address.
- Response bodies are read incrementally and aborted as soon as they
  exceed the configured size limit. The limit is a per-source
  configuration value with a conservative default.
- Content types outside the configured allow-list are rejected. Missing
  content type is permitted so that providers that omit it remain
  usable; adapters validate the body shape in that case.
- Retries are limited to GET and HEAD requests and to transient status
  codes. Non-idempotent methods are never retried automatically.
- Credentials are injected as request headers and never logged. They are
  never written to the database; the application layer resolves them
  from the operating system keyring and passes them to the factory for
  the lifetime of the client.
- TLS verification is enabled by default. Disabling it is a per-source
  configuration action and is recorded in the source's configuration so
  that it is visible to the user.
- The client logs retry attempts at DEBUG level. It never logs request
  bodies, response bodies, headers that carry credentials, or the
  credential values themselves.

## File Storage

- **Managed root confinement.** Managed copies are created under the
  configured managed root. The service refuses to write or delete a
  path outside the root. Directory traversal sequences in file names
  are neutralized because managed filenames are derived from the
  checksum, not from user-supplied names.
- **Original preservation.** Importing a managed copy never modifies or
  deletes the source file. Referenced files are never modified or
  deleted by the application.
- **Size limits.** Files exceeding the configured maximum are rejected
  before any copy begins. The limit is enforced again on the copied
  file's final size.
- **Regular files only.** The service rejects directories, device
  files, sockets, and other non-regular paths. This prevents the
  application from being tricked into reading from or writing to a
  special file.
- **Atomic writes.** A crash during a managed copy leaves no partial
  file under the managed root. The temporary file is created in the
  same directory as the target, fsynced, and renamed into place.
- **Checksum verification.** The service computes SHA-256 checksums by
  streaming. The checksum is stored in the database and re-verified on
  demand. A mismatch is reported rather than silently accepted.
- **No network access.** The file storage service never performs
  network operations and never spawns subprocesses. Paths are handled
  as opaque values.
- **Deletion is explicit.** Deleting a managed copy is an explicit
  operation invoked by the application layer. The service does not
  delete a file as a side effect of any other operation.