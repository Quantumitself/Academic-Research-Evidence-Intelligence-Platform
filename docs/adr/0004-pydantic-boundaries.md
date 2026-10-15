# 0004. Use Pydantic for validation at system boundaries

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

The application ingests data from untrusted or unreliable sources: user
input, HTTP responses from external search providers, AI model outputs,
imported documents, and the external API surface. The product specification
requires that validation occur at system boundaries, not only in the UI.

## Decision

Pydantic v2 is used for validated data structures at every system boundary:

- External API request and response schemas.
- Search provider request parameters and response parsing.
- AI provider request and response payloads.
- File import metadata and OCR results.
- Persisted configuration records.

Internal domain models may use plain dataclasses when no external boundary is
involved. Validation is mandatory at boundaries and is not duplicated inside
UI event handlers beyond basic input shaping.

## Consequences

- Malformed data is rejected at the boundary with a precise error message,
  rather than propagating into the domain layer.
- Boundary schemas are self-documenting and reusable by the OpenAPI
  specification generator.
- Contributors must not bypass Pydantic for external inputs even when the
  source appears trusted; trust is not assumed.
- Pydantic v2's strict mode is used where the schema is fully controlled by
  the application.

## Alternatives

- **Manual validation with isinstance checks**: rejected because it is
  repetitive, easy to omit, and produces inconsistent error messages.
- **marshmallow**: rejected because it is less integrated with the typing
  system and adds a separate dependency for the same purpose.
- **attrs with cattrs**: viable but rejected because Pydantic's JSON Schema
  generation directly supports the OpenAPI requirement.

## References

- Product specification, sections 19.5 (Type Annotations and Validation) and
  21 (External API Bridge).