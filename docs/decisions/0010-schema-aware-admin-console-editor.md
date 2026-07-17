# ADR-0010: Schema-aware admin-console editing

## Status

Accepted for TASK-010.

## Decision

The Concept Catalog remains governed by `ConceptService` and its public draft/revision contracts.
The browser editor projects those generic contracts into typed metadata, repeated-item, method,
deterministic-input, and sample-family controls. It reconstructs structured records only at the
service boundary; raw JSON is not part of normal operator editing.

Operator field semantics live in one repository-owned registry exposed read-only to the console.
Concept-specific context continues to come from the selected immutable concept revision and its
method records. The two sources are intentionally separate: the registry explains system behavior,
while revision data explains the current business concept.

Saving is a four-stage edit, validate, preview, and append-revision workflow. The browser performs
focused usability validation and the service remains the authoritative validation/publication
boundary. Optimistic conflicts and persistence errors retain distinct recovery messages.

The implementation uses browser-native controls and the standard-library HTTP server. This keeps
the dependency footprint small and establishes reusable admin patterns without introducing a
frontend framework or a second concept authority.

## Consequences

- Operators can edit common method and sample families without knowing serialization structure.
- Generic historical sample shapes remain preserved and inspectable while typed families evolve.
- New method or sample families require another typed projection, not a storage migration.
- Accessibility and dirty-state behavior are explicit console conventions for future tabs.
- Authentication, multi-user locking, and a universal sample schema remain outside this milestone.
