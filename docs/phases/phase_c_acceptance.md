# Phase C Acceptance

This document records the acceptance evidence for Phase C: literature
discovery, provider adapters, publication normalization and
deduplication, the search orchestration service, source management, and
saved searches.

## Scope of Phase C

- Search provider adapter interface.
- Crossref, OpenAlex, Semantic Scholar, PubMed, Europe PMC, and arXiv
  adapters.
- Shared HTTP client infrastructure and URL safety validator.
- Search source registry service and built-in catalog.
- Publication normalization and deduplication.
- Search orchestration service.
- Discover page wiring to real search.
- Source management UI.
- Saved searches.

## Acceptance criteria

A criterion is satisfied when the corresponding automated test passes and
the validator reports success.

| # | Criterion | Verification |
| --- | --- | --- |
| 1 | The search source registry service is constructible against a live session. | `test_source_service.py` |
| 2 | The built-in source catalog is installed with the expected entries. | `test_catalog_installer.py` |
| 3 | The provider registry contains every adapter registered by the application. | `test_phase_c_acceptance.py::test_provider_registry_contains_expected` |
| 4 | A search executed through the orchestrator reaches every enabled source. | `test_search_orchestration_service.py` |
| 5 | A failure in one source does not abort the search; the outcome is reported as partial. | `test_phase_c_acceptance.py::test_orchestrator_partial_flag` |
| 6 | Publications returned by multiple sources with the same DOI are deduplicated. | `test_phase_c_acceptance.py::test_orchestrator_deduplicates` |
| 7 | The orchestrator records a search session with per-source status reports. | `test_search_orchestration_service.py` |
| 8 | The saved-search service persists a saved search and marks it executed. | `test_saved_search_service.py` |
| 9 | Source management operations succeed through the application service. | `test_source_service.py` |
| 10 | The publication service is idempotent with respect to DOI and key. | `test_publication_service.py` |

## Automated acceptance

The Phase C validator is `scripts/validate_phase_c.py`. It runs every
acceptance check against deterministic stub adapters and a temporary
database, prints a per-check report, and writes a JSON document when
`--report` is supplied.

python scripts/validate_phase_c.py --report docs/phases/phase_c_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Known limitations

- The Discover page's local surface remains a stub. Local search will
be enabled when the library's full-text index is populated.

- Provider-specific rate limits are enforced by the shared HTTP client.
The application does not currently implement a global rate limit
across providers.

- Saved-search filters are stored and reloaded faithfully, but the
filter state is not yet applied to the provider-neutral request in
the orchestrator's build_request_from_saved_search helper. The
helper maps year range, author, venue, DOI, open-access, language, and
sort filters; additional filters are reserved for future phases.

- The external API surface is delivered in a later phase. The
orchestrator and saved-search services are exposed to the presentation
layer only.

## Files added or changed in Phase C

- src/academic_platform/infrastructure/http/ — HTTP client
infrastructure.

- src/academic_platform/infrastructure/search_providers/ — adapter
interface, registry, URL validator, and the six concrete adapters.

- src/academic_platform/application/search_sources/ — source registry
service, catalog, and installer.

- src/academic_platform/application/publications/ — normalization and
deduplication.

- src/academic_platform/application/search_orchestration/ — orchestrator.

- src/academic_platform/application/saved_searches/ — saved-search
service.

- src/academic_platform/ui/pages/search/ — orchestration controller,
search worker, saved-searches panel.

- src/academic_platform/ui/pages/settings/sources_dialog.py — source
management dialog.

- scripts/validate_phase_c.py — Phase C validator.