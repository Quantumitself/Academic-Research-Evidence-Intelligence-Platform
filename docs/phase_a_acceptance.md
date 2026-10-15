# Phase A Acceptance

This document records the acceptance evidence for Phase A: the
application shell, the settings service, the component library, the
dialog and notification infrastructure, and the first real pages.

## Scope of Phase A

- Repository audit and technical baseline.
- Architecture decision records.
- Project skeleton and build system.
- Application bootstrap and configuration service.
- Main window shell with all twelve destinations.
- Component library, part 1 (primitives).
- Component library, part 2 (content cards and configuration rows).
- Dialog and notification infrastructure.
- Dashboard page.
- Global search page (Local and Remote tabs).
- Settings page (six tabs).
- Phase A acceptance harness (this document, the capture script, and the
  validator script).

## Acceptance criteria

A criterion is satisfied when the corresponding automated test passes and
the visual verification record reflects a running application.

| # | Criterion | Verification |
| --- | --- | --- |
| 1 | The application package imports. | `test_phase_a_acceptance.py::test_shell_constructs_with_all_destinations` |
| 2 | Runtime directories resolve and are writable. | `test_configuration.py::test_directories_are_created` |
| 3 | The settings service loads and persists. | `test_settings_service.py`, `test_phase_a_acceptance.py::test_settings_persist_across_reload` |
| 4 | The main window constructs with all twelve destinations. | `test_phase_a_acceptance.py::test_shell_constructs_with_all_destinations` |
| 5 | Every destination is a `BasePage` subclass. | `test_phase_a_acceptance.py::test_every_page_inherits_base_page` |
| 6 | Navigation reaches every destination. | `test_phase_a_acceptance.py::test_navigation_reaches_every_destination` |
| 7 | The status bar reflects the active page. | `test_phase_a_acceptance.py::test_status_bar_reflects_active_page` |
| 8 | The stylesheet builds for light and dark themes and three densities. | `test_phase_a_acceptance.py::test_stylesheet_builds_for_all_variants` |
| 9 | The notification service and host construct and render. | `test_phase_a_acceptance.py::test_notification_host_constructs_and_renders` |
| 10 | The dialog factory constructs every standard dialog. | `test_phase_a_acceptance.py::test_dialogs_construct_without_error` |
| 11 | The Dashboard renders with a data provider and without one. | `test_dashboard_page.py` |
| 12 | The Global Search page renders both surfaces and reports per-source status. | `test_global_search_page.py` |
| 13 | The Settings page renders six tabs and persists changes. | `test_settings_page.py`, `test_settings_*_tab.py` |
| 14 | Implemented destinations return their concrete page; others return a placeholder. | `test_create_page_factory.py` |

## Visual verification record

The screenshot capture tool is `scripts/capture_screenshots.py`. It writes
one PNG per primary destination into
`docs/screenshots/phase_a/` and a `manifest.json` describing the capture.

To regenerate the record:

python scripts/capture_screenshots.py --offscreen

The manifest records the application version, the window size, the
generation timestamp, and per-destination metadata. Screenshots reflect
the running application; they are not mockups.

## Automated acceptance

The Phase A validator is scripts/validate_phase_a.py. It runs every
acceptance check in a temporary home directory, prints a per-check report,
and writes a JSON document when --report is supplied.

python scripts/validate_phase_a.py --report docs/phases/phase_a_validation.json

Exit code 0 means all checks passed. Exit code 1 means at least one
check failed; the report identifies which.

## Known limitations

- The Dashboard, Global Search, and Settings pages render without a data
provider. Every section that would show data renders an explicit empty
state instead. This is intentional: no content is fabricated.

- Global Search uses NullSearchController, which reports honestly that
local and remote search are not yet available.

- The Settings page's per-provider AI configuration is deferred to the
AI provider phase. The AI Providers tab currently configures the
default provider, default model, and external-provider policy only.

- Local GGUF model configuration is deferred to the AI provider phase.

- Android adaptation is deferred to a later phase.

## Files added or changed in Phase A

- pyproject.toml, README.md, .gitignore

- src/academic_platform/main.py, __main__.py

- src/academic_platform/app/ (configuration, logging, bootstrap, ADR
subsystem, settings subsystem)

- src/academic_platform/ui/main_window.py,
main_window_destinations.py

- src/academic_platform/ui/navigation/navigation_bar.py

- src/academic_platform/ui/pages/ (base, dashboard, placeholder, search,
settings)

- src/academic_platform/ui/components/ (section card, empty state, error
state, loading indicator, progress bar, search bar, filter panel, page
header, stat badge, tag list, metadata grid, article card, research
project card, collection card, AI provider card, search source row)

- src/academic_platform/ui/dialogs/ (message, confirm, prompt, form,
progress, factory)

- src/academic_platform/ui/notifications/ (model, service, host)

- src/academic_platform/ui/resources/styles.py

- scripts/ (audit, inventory, environment validation, ADR, run_dev,
capture_screenshots, validate_phase_a)

- docs/ (architecture, code style, security, testing, repository audit,
dependency inventory, ADRs, phases)

- tests/unit/ (per-module tests as described above)