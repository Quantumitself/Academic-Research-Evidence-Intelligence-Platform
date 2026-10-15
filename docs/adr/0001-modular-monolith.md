# 0001. Use a modular monolith architecture

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

The application must run as a desktop product while also offering an optional
external API for third-party integrations. Candidate architectures include a
single-process monolith, a modular monolith with clear internal boundaries,
and a set of independently deployed microservices.

The desktop product requires fast startup, no mandatory network dependency,
and the ability to run entirely offline for local workflows. Deploying and
operating microservices for a single-user desktop tool would introduce
operational overhead without any product benefit. However, mixing UI code,
SQL queries, and provider-specific HTTP logic in a single layer would make the
codebase unmaintainable as the feature set grows.

## Decision

The application is implemented as a modular monolith. Internal layers are
strictly separated: presentation, application, domain, infrastructure, API,
and platform. Domain and application modules must not import from the
presentation layer. Infrastructure adapters are registered through explicit
interfaces at external system boundaries.

The desktop UI and the optional external API share the same application
services rather than duplicating business logic.

## Consequences

- The desktop application runs entirely offline and starts quickly.
- A single codebase is easier to test, package, and reason about than a
  distributed system.
- Clear internal boundaries allow individual modules to be replaced or
  extracted later if a genuine requirement emerges.
- Contributors must respect module boundaries. A CI check enforces the
  direction of imports at review time.
- No independent deployment or scaling of subsystems is possible. This is
  accepted because the workload is single-user and local.

## Alternatives

- **Microservices**: rejected because the workload is single-user, the
  application must run offline, and the operational overhead is unjustified.
- **Unstructured monolith**: rejected because it makes long-term maintenance
  and scientific correctness reviews impractical.
- **Desktop-only architecture with no API layer**: rejected because the
  product specification requires a documented integration surface.

## References

- Product specification, sections 17 (Technical Architecture) and 21
  (External API Bridge).