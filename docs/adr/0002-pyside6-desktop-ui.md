# 0002. Use PySide6 (Qt) for the desktop UI

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

The primary platform is Windows desktop with a native-feeling interface. The
application requires a mature widget set, robust internationalization, a
threading model suitable for long-running background work (search, OCR,
statistical analysis, model inference), and a clear path to later use the same
business logic from an Android client.

Candidate UI frameworks include PySide6 (Qt for Python), PyQt6, Tkinter, and a
web-based interface rendered inside a native shell.

## Decision

PySide6 is used for the desktop UI. All Qt-specific code is confined to the
`academic_platform.ui` subpackage. Domain, application, and infrastructure
modules must not import from PySide6.

## Consequences

- The UI has a native look and consistent behavior across Windows versions.
- Qt provides mature support for tables, trees, docking, model/view
  architecture, and background execution, which the research workflows
  require.
- The LGPL licensing of PySide6 is compatible with the distribution model.
- Contributors must keep Qt imports inside the UI package; a boundary test
  enforces this.
- The Android client will not reuse Qt widgets but will reuse the shared
  domain and application modules.

## Alternatives

- **PyQt6**: rejected because of the GPL/commercial licensing model, which is
  incompatible with the intended distribution.
- **Tkinter**: rejected because it lacks the widget depth, accessibility, and
  performance characteristics required for document reading and evidence
  tables.
- **Web UI in a native shell**: rejected because it introduces a browser
  runtime dependency and complicates offline operation and packaging on
  Windows.

## References

- Product specification, section 5 (Visual and Interaction Design).