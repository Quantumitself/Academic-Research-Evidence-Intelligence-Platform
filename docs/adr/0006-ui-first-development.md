# 0006. Require UI-first development for every feature phase

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

Long backend-only development cycles produce code that cannot be evaluated by
users or stakeholders until late in the process. The product specification
requires that every implementation phase deliver something visible and
usable, and explicitly prohibits postponing the interface until the backend
is complete.

## Decision

Every feature phase produces a visible, interactive UI before or alongside
the underlying business logic. Where real services are not yet implemented,
demonstration data must be visibly labeled and must never be presented as a
working feature. A phase is not complete until its UI is navigable, its
primary controls are functional, and its interactions have been visually
verified.

## Consequences

- Progress is observable at every stage of development.
- Early UI work surfaces design problems before backend code is committed to
  a specific data shape.
- Placeholder content is explicit and never mistaken for completed
  functionality.
- Contributors must design interaction states (loading, empty, error) before
  wiring business logic.

## Alternatives

- **Backend-first development**: rejected because it defers feedback and
  hides usability problems until late.
- **Frontend-prototype-only development**: rejected because it produces
  shells that cannot be evaluated for real workflows.
- **Simultaneous full-stack development without phase boundaries**: rejected
  because it makes review, testing, and progress measurement impractical.

## References

- Product specification, sections 5.3 (UI-First Development Rule) and 20.1
  (Mandatory Phase Workflow).