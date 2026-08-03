# TASK-062 — Separate Candidate Identity from Discovery Occurrence

## Status

Complete

---

## Summary

Separate durable candidate identity from the trial-local occurrence through which a
candidate was discovered.

The same transcript candidate can be reached from multiple learned or configured seeds.
Discovery timestamps, proposal ranks, traversal depth, parent path, and seed attribution
may differ even when durable acquisition semantics are identical. Those differences shall
remain observable without causing false malformed-adapter conflicts.

This milestone changes duplicate classification only. Existing traversal, ranking,
selection, validation, persistence, learning, checkpoint, and replay behavior remains
authoritative.

---

## Objective

Introduce one explicit candidate-identity contract and one explicit discovery-occurrence
contract. Use the identity contract for global per-run duplicate conflict detection while
retaining bounded occurrence diagnostics.

Equivalent occurrences shall be processed at most once. The first deterministic occurrence
shall remain authoritative for execution order and persistence attribution. Reusing a
candidate ID with genuinely conflicting identity semantics shall continue to fail closed.

---

## Scope

### In Scope

- Add an explicit immutable `CandidateIdentity` representation.
- Add an explicit immutable `DiscoveryOccurrence` representation.
- Define candidate identity with an allowlist of stable acquisition fields.
- Deduplicate candidates globally across every page and trial in one acquisition run.
- Preserve the first deterministic occurrence as authoritative for execution.
- Retain bounded occurrence totals and representative diagnostics.
- Add realistic Amazon-, IBM-, and Western Digital-shaped regression coverage.
- Reuse the existing acquisition result and repository models without introducing a
  parallel persistence representation.

### Out of Scope

Do not change:

- transcript traversal, search, ranking, or eligibility policy;
- `latest` or `first_in_date_range` selector semantics;
- validation-date behavior;
- persistence, learning, checkpoint, or replay policy;
- seed planning or seed-injection behavior;
- repository state or schema;
- request or HTTP API shapes;
- LLM recovery or operator UI;
- run-level traversal budgets or diagnostic presentation.

Do not repair or reinterpret existing Amazon, IBM, or Western Digital repository state.

---

## Candidate Identity Contract

`CandidateIdentity` shall contain only stable acquisition semantics:

- candidate ID;
- document ID;
- candidate position;
- candidate revision;
- disposition and disposition reason;
- immutable acquisition target, when present;
- discovery method;
- provider identifiers;
- canonical resolved candidate locations;
- allowlisted metadata that affects firm/artifact identity, validation, selection,
  persistence, or checkpoint semantics.

The identity projection shall be constructed directly from this allowlist. It shall not be
implemented by copying complete provenance and subtracting an exclusion list.

At minimum, the allowlisted transcript metadata shall retain:

- `firm_id`;
- `canonical_artifact_id`;
- `resolved_url`;
- `allowed_hosts`;
- `firm_identity_terms`;
- `checkpoint_reporting_period`;
- `expected_reporting_period`;
- `deferred_candidate_evaluation`;
- `acquisition_target`.

Changing any identity field for the same candidate ID shall preserve the existing
fail-closed ambiguity error.

---

## Discovery Occurrence Contract

`DiscoveryOccurrence` shall retain trial-local discovery attribution without contributing
to candidate identity. At minimum it shall contain, when available:

- discovery timestamp;
- exact observed locations and aliases;
- requested URL and observed link label;
- proposal rank;
- deterministic selection rank;
- trial ID;
- seed kind;
- seed source;
- starting seed;
- traversal depth, parent path, and ranking reasons.

The current adapter may not emit every optional occurrence field. Absence shall remain
explicit and shall not cause fabricated metadata.

The first deterministic occurrence remains authoritative for execution order, retrieval,
repository attribution, and existing diagnostics. A representative occurrence selected for
bounded diagnostic display, if any, shall never affect execution or durable behavior.

---

## Required Architectural Invariants

1. Candidate identity and discovery occurrence have one explicit definition each.
2. Candidate identity uses a stable-field allowlist, not scattered exclusions.
3. Deduplication is global within one acquisition run and spans pages and trials.
4. Each stable candidate is checkpoint-filtered, retrieved, validated, and processed at most
   once per run.
5. The first deterministic occurrence remains authoritative.
6. Equivalent later occurrences create no artifact, observation, learned anchor, or checkpoint
   change beyond the existing duplicate-outcome audit behavior.
7. Candidate-ID reuse with conflicting identity remains a fatal malformed-adapter result.
8. Existing selectors, persistence, learning, checkpoint, replay, and rollback behavior are
   unchanged.
9. No seed-origin special case is introduced.
10. No repository migration or state repair is introduced.

---

## Required Diagnostics

For candidates with repeated equivalent occurrences, expose bounded run diagnostics containing:

- candidate ID;
- total occurrence count;
- the authoritative occurrence;
- a bounded representative occurrence list;
- whether additional occurrences were omitted.

Occurrence diagnostics shall use existing URL-redaction conventions where applicable and
shall not add unbounded URL, path, or trial logs.

---

## Required Tests

Add focused tests proving:

1. The same candidate discovered through learned and configured trials with different
   timestamps, proposal ranks, deterministic ranks, depths, parent paths, and seed attribution
   is deduplicated without error.
2. The candidate is processed at most once.
3. First-occurrence ordering and terminal behavior remain deterministic.
4. `latest` behavior remains unchanged.
5. `first_in_date_range` behavior remains unchanged.
6. Checkpoint filtering occurs once before later occurrences are classified as duplicates.
7. The same candidate ID with a changed stable field raises the existing fail-closed ambiguity
   error.
8. Equivalent duplicate occurrences preserve existing duplicate audit persistence while creating
   no additional artifact, observation, learned anchor, or checkpoint change.
9. Occurrence diagnostics are bounded and retain exact total counts.
10. Configured-pipeline and operator-supplied single-seed behavior remain unchanged.

Use captured topology shapes for:

- Amazon: learned transcript pages and configured archive converge on Q4 2016 and Q2 2026;
- IBM: learned pages converge on the same archive candidates;
- Western Digital: multiple learned transcript pages converge on the same candidate graph.

---

## Validation

Run:

- focused TASK-062 tests;
- TASK-057 regressions;
- TASK-058 regressions;
- TASK-059 regressions;
- TASK-060 regressions;
- TASK-061 regressions;
- relevant engine, discovery, repository, and API tests;
- full `make validate`.

Perform a deliberate complexity and robustness review confirming:

- there is one allowlisted identity definition;
- there is one occurrence definition;
- candidate-ID conflict protection remains fail closed;
- selectors and durable repository behavior are unchanged;
- no seed-origin special case, second checkpoint model, or repository migration exists;
- occurrence diagnostics are bounded.

---

## Repository Requirements

Work on:

```text
codex/task-062-separate-candidate-identity-discovery-occurrence
```

Commit completed work. Do not merge.

If corrective work is performed after the review package is generated, delete the existing
TASK-062 review package and architectural review report before beginning the correction. Generate
a completely new package only after final code and validation are complete.

---

## Review Package

Generate a complete verified TASK-062 review package containing:

- architectural summary;
- candidate identity schema and allowlist;
- discovery occurrence schema;
- proof of first-occurrence authority;
- proof of global per-run deduplication;
- proof that genuine conflicts remain fail closed;
- selector, persistence, checkpoint, learning, and replay compatibility evidence;
- bounded diagnostic contract and evidence;
- Amazon, IBM, and Western Digital topology regressions;
- focused and full validation results;
- complexity and robustness review;
- assumptions and limitations;
- package manifest and SHA-256 verification.
