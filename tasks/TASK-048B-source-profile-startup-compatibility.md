# TASK-048B: Source-Profile and Startup Compatibility Repair

## Status

Complete

## Objective

Restore validation of immutable source-profile revisions created before `discovery_class`, and
remove ordinary admin startup's authority to append externally managed firm or source-profile
projection revisions.

## Invariants

- Historical revision JSON, identifiers, chains, and pointers are never rewritten or rehashed.
- Digest verification uses the authenticated canonical shape of each revision era.
- Newly published revisions authenticate `discovery_class` and an explicit digest schema marker.
- Ordinary admin startup validates external JSON and established repository state without writes.
- Fresh `rfi init` and explicit governed materialization retain their intentional write authority.
- Production validation occurs against a copy until the code repair is committed and pushed.

## Acceptance Criteria

- Pre-TASK-048A, transitional unversioned, and current versioned digest shapes are deterministic.
- Tampering fails closed in legacy and current shapes.
- Mixed legacy/current histories verify without changing revision identity or chain structure.
- First and repeated admin startup do not append firm or source-profile revisions or advance the
  authority revision, including when current projection logic contains additional/default fields.
- Focused TASK-041, source-profile, TASK-048A, startup, and complete validation pass.
- A copied production state proves stable row counts, history IDs, pointers, authority revision,
  database hash, and persistent-file manifest hash across startup.

## Architectural Status Summary

- **Digest canonicalization — Complete.** Revision-level schema selection reconstructs the exact
  historical canonical shape; current publications authenticate the explicit schema and complete
  candidate shape.
- **External configuration loading — Complete.** Ordinary startup validates and loads authoritative
  JSON without projection publication.
- **Governed writes — Complete.** `rfi init` and explicit materialization remain the intentional
  configuration publication boundary.
- **Production recovery — Separate guarded operation.** The reviewed accidental-revision manifest
  is applied only after this repair is committed, pushed, and independently verified.
- **Next milestone.** Continue artifact-family integration without changing immutable canonical
  shapes absent an explicit version contract.
