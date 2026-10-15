# 0005. Adopt a package-reuse-first policy

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

The product scope spans literature search, PDF extraction, OCR, statistical
analysis, plotting, local model inference, and API service hosting. Each of
these has mature, well-maintained libraries. Implementing custom versions of
such functionality would consume development time, introduce bugs, and shift
the maintenance burden onto this project.

## Decision

The project adopts a package-reuse-first policy. Before writing custom code,
the following sequence is required:

1. Identify the requirement precisely.
2. Search the existing project for relevant code.
3. Check whether an installed dependency already provides the capability.
4. Evaluate established packages for the requirement.
5. Review compatibility, licensing, maintenance status, security, and
   platform support.
6. Reuse or extend an existing solution where appropriate.
7. Write custom code only for missing application-specific behavior.

Every dependency introduced must have a documented purpose in
`docs/dependency_inventory.md` and, when significant, an entry in this ADR
series.

## Consequences

- Development focuses on application-specific logic rather than
  reimplementing solved problems.
- The dependency surface is broader than a minimal implementation, which
  requires active dependency management and periodic review.
- Custom implementations are reserved for cases where no suitable library
  exists or where integration constraints require them.
- Contributors must record every dependency's purpose and license.

## Alternatives

- **Minimal-dependency policy**: rejected because it would require
  reimplementing PDF extraction, statistical routines, and HTTP clients,
  which is impractical and risky.
- **Unbounded dependency adoption**: rejected because it leads to conflicts,
  duplicated capabilities, and unclear maintenance responsibility.

## References

- Product specification, section 18 (Technology Stack and Existing Libraries).