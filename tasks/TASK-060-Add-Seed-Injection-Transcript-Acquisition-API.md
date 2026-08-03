# TASK-060 --- Add Seed-Injection Transcript Acquisition API

## Status

Complete

# Summary

This task is the third step in the planned evolution of deterministic
transcript acquisition.

Overall feature arc:

1.  TASK-058 (completed) --- Externalize transcript acquisition
    orchestration.
2.  TASK-059 (completed) --- Add immutable transcript acquisition
    selection contracts.
3.  TASK-060 (this task) --- Add an operator-supplied seed injection
    API.
4.  Future task --- Add bounded LLM-assisted seed recovery using an
    OpenAI model with integrated web search.
5.  Future task --- Add a bounded recovery workspace.
6.  Future enhancement --- Expand the repository learning surface.
7.  Future enhancement --- Add deterministic historical backfill and
    continuation cursors.

This task intentionally implements only Step 3.

Design reference: docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md

# Objective

Add a bounded acquisition API that executes the existing deterministic
transcript acquisition pipeline beginning from one operator-supplied
starting URL. The supplied URL is a starting seed, not an asserted
artifact location.

# Motivation

The operator should be able to inject a starting seed without modifying
configuration. Injecting a seed is not itself a learning operation. Any
repository changes resulting from the acquisition shall continue to
occur exclusively through the existing validated acquisition and
repository learning workflow.

# Scope

In scope: - Accept immutable acquisition target, selection contract
(default latest), and one operator-supplied starting URL. - Invoke the
existing deterministic acquisition implementation using that seed. -
Preserve traversal, ranking, validation, diagnostics, persistence,
checkpoint, and learning behavior. - Record complete structured
provenance.

Out of scope: - LLM invocation - Web search - Recovery workspace -
Provider context handles - Expanded learning - Traversal changes -
Backfill - Continuation cursors

# Required Architectural Invariants

1.  The supplied URL is a starting seed only.
2.  The seed-injection API invokes the existing deterministic
    acquisition implementation rather than a parallel path.
3.  Target and selection contract remain immutable.
4.  Validation alone determines success.
5.  An operator-supplied seed participates only as an acquisition input.
    Repository learning remains governed exclusively by validated
    acquisition outcomes.
6.  Existing acquisition semantics remain unchanged.

# Testing

Prove: - injected and learned seeds converge to the identical
deterministic acquisition implementation after seed selection; -
acquisition may succeed from a different validated URL; - unsuccessful
injected seeds do not modify repository learning; - TASK-058 and
TASK-059 regressions remain unchanged.

# Validation

Focused TASK-060 tests, TASK-059 regression, TASK-058 regression,
transcript regression suite, full make validate, and manual
compatibility proof.

# Review Package

Include architectural summary, API contract, seed provenance,
compatibility proof, focused tests, full validation, and confirmation
that no LLM, recovery workspace, provider context, expanded learning, or
backfill capability was introduced.
