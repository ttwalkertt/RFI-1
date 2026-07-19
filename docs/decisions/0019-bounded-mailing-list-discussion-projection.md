# ADR 0019 — Bounded mailing-list discussion projection over SQLite

## Decision

Retain each selected mailing-list email through the existing immutable acquisition repository.
Store bounded acquisition manifests in the existing SQLite authority and rebuild header-derived
reply/discussion indexes from those manifests plus retained bytes. Expose discussion organization
through a repository query service and a sibling projection in the existing artifact browser.

## Rationale

Email is still the evidence unit, but interpreting an isolated reply can be materially misleading.
Ancestor closure is therefore an admission invariant, while descendant expansion is bounded and
may end only at a visible frontier. SQLite recursive and indexed relational queries are sufficient
for direct children, ancestors, discussion membership, search, and validation at this scale.

A graph database would create a second structured authority, complicate replay and backup, and leak
persistence concerns into the browser without solving a demonstrated workload. Subject-derived
threading was rejected because it can silently connect unrelated discussions. Archive mirroring was
rejected because Lore already owns the broad corpus and RFI needs selected, governed evidence.

## Consequences

Schema version 2 adds mailing-list tables and a version-1 migration. Exact email bytes remain in the
content store. Missing connectors and cycles never receive connected discussion membership. Live
ancestor-only acquisitions conservatively report descendant truncation. Later patch-series or
revision heuristics must be explicitly labeled and cannot replace header authority.
