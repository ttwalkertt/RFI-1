# ADR 0021 — Canonical stream YAML as an adapter to the revision contract

## Decision

Use one strict, versioned YAML document as the human-authored interchange format for artifact
streams. Decode YAML into the existing repository-owned `StreamDraft`, normalize and validate it
in `StreamService`, and encode canonical YAML from that same normalized contract. Browser and CLI
invoke these shared operations. SQLite revisions remain the only structured authority.

Organize the browser editor around Identity, Input, Selection, Context and limits, and Review and
save. Keep common schema-aware controls visible and the full bounded typed Boolean policy behind
Advanced policy. Keep draft operations separate from saved-revision execution.

Semantically identical import is an `already_current` no-op. A changed existing identity requires
explicit revision mode and normal optimistic revision creation. A missing identity requires
explicit new mode. Canonical export may include read-only revision number and creation time, but
those fields do not become reusable semantic input or persistence identity.

## Rationale

Operators need a reviewable source-control format and a simpler browser workflow, but a parallel
YAML model or browser-only defaults would let surfaces drift from execution. A thin strict adapter
preserves TASK-025 capability, DAG, revision, governed-source, publication, and evidence-retention
boundaries while making definitions portable and inspectable.

Safe parsing, exact field sets, stable ordering, normalized scalars, semantic fingerprints, and
path-aware errors make imports deterministic and fail closed. Explicit import modes protect
history, while identical no-op behavior avoids meaningless revisions.

## Consequences

No SQLite schema migration is required. Optional non-executable notes live in the revision's
existing canonical definition JSON. YAML cannot configure source transport, secrets, acquisition
state, executable predicates, or source profiles. Comments and original formatting do not
round-trip. Bulk documents, arbitrary plugins, workflow engines, and automatic run-on-import
remain out of scope.
