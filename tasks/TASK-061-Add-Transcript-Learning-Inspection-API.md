# TASK-061 — Add Transcript Learning Inspection API

## Status

Complete

---

# Summary

This task adds a narrow, read-only API that exposes the transcript learning state for a specified firm.

**Endpoint**

```http
GET /api/transcript-acquisitions/learning/{firm_id}
```

This task is intentionally observational only. It does not modify acquisition, discovery, learning, checkpoint, ranking, or seed-promotion behavior.

---

# Feature Context

1. **TASK-058 (completed)** — Externalize transcript acquisition orchestration.
2. **TASK-059 (completed)** — Add immutable transcript acquisition selection criteria.
3. **TASK-060 (completed)** — Add operator-supplied seed injection and reliable replay semantics.
4. **TASK-061 (this task)** — Expose transcript learning state for operator inspection and testing.

Future work may improve deterministic search, retained-anchor quality, and learning policy. This task provides the observability needed before those changes.

---

# Objective

Add a read-only API that exposes the current transcript learning state for a specified firm.

The endpoint shall present the repository's current learning state exactly as persisted without reinterpretation or mutation.

---

# Scope

## In Scope

- Add the GET endpoint.
- Resolve the firm's transcript learning state.
- Return the repository learning state in repository execution order.
- Reuse existing repository models wherever practical.
- Add focused API, repository, and regression tests.
- Update API documentation as required.

## Out of Scope

Do not add:

- editing, deleting, promoting, demoting, or reordering learned entries;
- search or learning-policy changes;
- checkpoint changes;
- acquisition changes;
- LLM recovery;
- recovery workspace;
- UI;
- historical backfill;
- continuation cursors.

---

# Required Architectural Invariants

1. The endpoint is observational only.
2. It shall not invoke acquisition, discovery, learning, checkpoint advancement, or any repository mutation.
3. Repository learning order shall be preserved exactly.
4. The endpoint shall not fabricate metadata that is not already persisted or deterministically derivable.
5. The caller supplies only `firm_id`.
6. Empty learning state is a successful result.
7. Unknown firms shall fail using existing API conventions.

---

# Behavioral Requirements

The endpoint shall:

- accept one canonical `firm_id`;
- expose the repository's transcript learning state;
- preserve repository learning order;
- return HTTP 200 with an empty learning array when appropriate;
- avoid any repository mutation during the request.

---

# Testing

Add focused tests proving:

- empty learning state returns success;
- populated learning state preserves repository order;
- unknown firms follow existing error conventions;
- repeated reads are mutation-free;
- injected acquisition followed by this endpoint exposes the learned state correctly.

---

# Validation

Run:

- focused TASK-061 tests;
- TASK-060 regression tests;
- transcript acquisition regression suite;
- relevant admin/API tests;
- full `make validate`.

Perform a complexity and robustness review focused on:

- accidental repository mutation;
- duplicated learning representations;
- preservation of repository order;
- empty-state behavior.

---

# Repository Requirements

Work on the TASK-061 branch.

Commit and push.

Do not merge.

If additional commits are made after a review package is generated, invalidate the previous review package and regenerate it from the final branch head.

---

# Review Package

Include:

- architectural summary;
- endpoint contract;
- response schema;
- proof of preserved repository order;
- proof that the endpoint is read-only;
- empty-state and unknown-firm behavior;
- integration proof from injected acquisition to visible learned state;
- focused test results;
- TASK-060 regression results;
- full validation results;
- assumptions and limitations;
- package manifest and SHA-256.
