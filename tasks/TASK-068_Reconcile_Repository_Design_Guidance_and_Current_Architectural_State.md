# TASK-068 --- Reconcile Repository Design Guidance and Current Architectural State

> **Status:** Complete

## Objective

Reconcile RFI-1's governing documentation, architectural guidance,
roadmap, task index, and developer orientation material with the
repository as it is actually implemented.

The completed repository documentation must allow a coding agent to
determine, without reconstructing project history from old task tickets
or broad exploratory code searches:

-   what RFI-1 currently contains;
-   which architectural contracts and invariants are established;
-   which capabilities are integrated into the operating product;
-   which capabilities exist as implemented architectural POCs but are
    not yet product-composed;
-   which mechanisms remain provisional, narrow, or deterministic
    substitutes;
-   which capabilities are genuinely absent or intentionally deferred;
-   where authoritative implementation and design evidence can be found;
    and
-   what engineering frontier remains for subsequent agent work.

The purpose is to reduce repeated repository rediscovery, stale-context
errors, and incorrect implementation assumptions during the remaining
RFI-1 work.

------------------------------------------------------------------------

## Governing Principle

**Repository reality must drive current-state documentation.**

For statements about what is implemented or currently behaves a
particular way, Codex shall prefer evidence in this order as
appropriate:

1.  Public repository contracts and committed implementation.
2.  Executable tests and validation evidence.
3.  Accepted architectural decisions and completed task records.
4.  Current design documents.
5.  Historical roadmap and planning material.

Historical planning documents must not override executable repository
facts.

Conversely, the existence of code alone does not establish architectural
intent. Governing principles, ADRs, accepted task boundaries, public
contracts, tests, and repository conventions must be used to distinguish
intentional architecture from incidental implementation residue.

Where evidence conflicts or intent cannot be determined confidently, the
documentation must expose the ambiguity rather than silently resolving
it.

------------------------------------------------------------------------

## Scope

The implementation shall:

1.  Perform a repository-grounded architectural inventory.
2.  Classify capability maturity explicitly.
3.  Establish an explicit documentation authority model.
4.  Provide a concise current-state orientation artifact.
5.  Reconcile `ARCHITECTURE.md`.
6.  Reconstruct `ROADMAP.md` around the actual remaining engineering
    frontier.
7.  Reconcile `TASKS.md` and high-level task guidance.
8.  Improve repository entry-point guidance (`README.md`).
9.  Reconcile materially contradictory downstream documentation.
10. Preserve historical and architectural provenance.

This is a documentation reconciliation task. It shall not implement new
product capabilities or perform architectural refactoring.

------------------------------------------------------------------------

## Required Design Properties

-   Current state is explicit.
-   Architecture and maturity are separate concepts.
-   Product composition is explicitly identified.
-   Documentation authority is explicit.
-   Known limitations remain visible.
-   Material claims are traceable to repository evidence.
-   Documentation remains maintainable rather than becoming a symbol
    inventory.

------------------------------------------------------------------------

## Required Deliverables

-   Reconciled `README.md`
-   Reconciled `ARCHITECTURE.md`
-   Reconciled `ROADMAP.md`
-   Reconciled task/index guidance
-   Current-state orientation document (or demonstrated equivalent)
-   Updates to other materially contradictory guidance
-   Completed TASK-068 record
-   Complete TASK-068 review package

------------------------------------------------------------------------

## Acceptance Criteria

-   Repository state accurately reflects implemented capabilities.
-   Documentation distinguishes implemented architecture from product
    integration.
-   POC limitations remain explicit.
-   Documentation authority is clearly defined.
-   README provides an efficient orientation path.
-   Roadmap reflects genuine remaining work.
-   Current-state guidance exists and is concise.
-   Historical task information is preserved while current status is
    clarified.
-   No production behavior is changed.
-   Any newly discovered implementation work is captured as follow-on
    backlog items rather than expanding TASK-068.

------------------------------------------------------------------------

## Validation

Validation shall emphasize factual reconciliation rather than
implementation.

At minimum:

-   Documentation validation.
-   Link/reference validation.
-   `git diff --check`.
-   Inspection of complete documentation diffs.
-   Verification that referenced contracts, tests, ADRs, and
    implementation surfaces exist.
-   Focused tests where they materially support documented capability
    claims.
-   Repository-standard validation required for documentation changes.
-   Confirmation that no production behavior changed.

------------------------------------------------------------------------

## Required Review Package

Include:

-   Executive summary.
-   Documentation drift findings.
-   Repository capability inventory.
-   Capability maturity matrix.
-   Documentation authority model.
-   Changed-file inventory.
-   Before/after contradiction summary.
-   Current-state orientation artifact.
-   Roadmap reconciliation summary.
-   Task guidance reconciliation summary.
-   Evidence supporting capability claims.
-   Validation commands and results.
-   Patch/diff evidence.
-   Branch and repository state.
-   Manifest, checksums, ZIP, and SHA-256.

------------------------------------------------------------------------

## Non-Goals

TASK-068 does **not**:

-   implement research workspace capabilities;
-   compose POC subsystems into the browser product;
-   add internet evidence or research APIs;
-   broaden retrieval or semantic coverage;
-   replace deterministic planning;
-   redesign persistence or subsystem APIs;
-   refactor production code;
-   redesign the UI;
-   rewrite historical task provenance.

New implementation work discovered during reconciliation shall be
recorded as future tasks.

------------------------------------------------------------------------

## Completion Standard

A new coding agent reading the repository documentation shall be able to
determine:

1.  what RFI-1 currently is;
2.  which architectural layers already exist;
3.  which documents are authoritative;
4.  what is product-integrated;
5.  what remains POC-only or provisional;
6.  what is genuinely missing;
7.  where implementation evidence resides; and
8.  what engineering work should happen next,

without reconstructing repository history from task tickets or
exploratory code search.

------------------------------------------------------------------------

## Completion Record

Completed on branch `codex/task-068-documentation-reconciliation`.

The repository-grounded inventory, drift findings, capability maturity matrix, documentation
authority model, contradiction reconciliation, changed-file inventory, evidence references,
validation commands/results, limitations, and required Architectural Status Summary are recorded
in `docs/TASK-068-review.md`. The concise current-state orientation artifact is
`docs/current-state.md`.

Validation includes machine-readable contract/composition inventory, Markdown link/reference
checks, design-baseline integrity, 126 focused capability-claim tests, committed-range diff/scope
checks, and the complete repository-standard validation gate. The commit-aware review generator
produces the manifest, complete patch, repository state, ZIP, and SHA-256 only from the clean final
commit.
