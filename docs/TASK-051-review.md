# TASK-051 Review

## Outcome

Pull Workflow aggregation now preserves inconclusive coverage as the canonical
`indeterminate` artifact outcome. A complete engine run with no failures and no acquired artifact
is no longer sufficient by itself to assert `no_change`.

## Root Cause

`PullWorkflow._engine_outcome` previously classified every complete, failure-free, zero-result
engine run as `no_change`. It did not inspect the engine's coverage diagnostics, including
`bounds_exhausted`, `exhausted_budget`, and `coverage`. The paired diagnostic formatter then used
checkpoint-specific text for the incorrectly selected outcome even when no checkpoint decision
had occurred.

The defect was at the workflow/domain aggregation boundary. Persistence, REST serialization, and
the operator console faithfully propagated the incorrect aggregation result.

## Outcome Semantics and Precedence

The workflow applies this deterministic precedence:

1. Any operational failure or non-complete engine status is `retrieval_failure`.
2. A durable acquisition is `success`.
3. An exact duplicate is `duplicate`.
4. A genuine checkpoint-filter decision or unchanged ingress is `no_change`.
5. Affirmative `coverage: complete` with no artifact is `no_change`.
6. Exhausted bounds, incomplete or indeterminate coverage, or a zero-result run without
   affirmative completeness evidence is `indeterminate`.

Policy exhaustion is not a retrieval failure. Checkpoint wording is emitted only when an existing
checkpoint and a `checkpoint_filtered` engine outcome prove that a checkpoint decision occurred.
Conclusive empty discovery and unchanged ingress use separate explanations.

## Canonical Representation

The acquisition domain already defines `IntervalCoverage.INDETERMINATE` with serialized value
`indeterminate`. Pull Workflow now exposes the same canonical term as
`ArtifactOutcome.INDETERMINATE` and records an `indeterminate` summary count. This is a domain
outcome selected by workflow aggregation, not an earnings-transcript adapter exception or a
presentation-only status.

## Cross-Layer Evidence

The focused cross-layer regression executes an empty discovery carrying all three bounded signals:

- `bounds_exhausted: true`;
- `exhausted_budget: max_links_per_page`;
- `coverage: indeterminate`.

It proves that the typed workflow result and durable SQLite-backed pull record both contain
`outcome: indeterminate`, the JSON-compatible REST results representation retains that outcome and
summary count, and the operator page renders the count and the workflow-provided diagnostic. The
diagnostic states that no artifact was acquired and discovery did not conclusively establish that
none exists. It contains no checkpoint claim.

The same focused suite proves:

- a real repeated pull with checkpoint filtering remains `no_change` and retains checkpoint text;
- affirmative complete empty discovery remains conclusive `no_change` but does not use checkpoint
  text;
- an adapter retrieval failure remains `retrieval_failure`;
- failure wins over a simultaneous acquisition/coverage signal;
- indeterminate coverage wins over generic failure-free zero-result handling;
- successful exact-byte acquisition remains `success`.

## Verification

The review package retains complete transcripts for:

```sh
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_task015.PullWorkflowCase.test_no_change_successful_and_failed_workflow_aggregation \
  tests.test_task015.PullWorkflowCase.test_indeterminate_and_complete_empty_discovery_cross_layer_contract \
  tests.test_task015.PullWorkflowCase.test_engine_outcome_mixed_signal_precedence \
  tests.test_task015.PullWorkflowCase.test_production_direct_url_adapter_ingests_exact_whole_artifact -v
make validate
git diff --check
```

The package also contains the task ticket, complete committed patch and changed-file statistics,
branch/upstream/commit identity, clean-status evidence, copied focused tests, validation result
summary, manifest hashes, ZIP checksum, and independent ZIP integrity result.

## Repository State

The reviewed branch is `agent/TASK-051-preserve-indeterminate-coverage`, pushed with upstream
tracking to `origin/agent/TASK-051-preserve-indeterminate-coverage`. The reviewed head is recorded
in the package metadata after this review document and generator are committed. No merge was
performed.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Acquisition diagnostics | Preserve adapter coverage and bounded-discovery evidence | Complete |
| Pull aggregation | Select truthful artifact outcomes with deterministic precedence | Complete |
| Pull persistence | Retain outcome, diagnostic, attempts, and summary durably | Complete |
| REST projection | Return the durable Pull Workflow result without reclassification | Complete |
| Operator presentation | Display outcome counts and accurate human-readable detail | Complete |
| Regression coverage | Protect checkpoint, complete, indeterminate, failure, and success paths | Complete |

Architectural change: zero-result outcome selection is now an explicit evidence-based decision at
the workflow/domain boundary. There are no known TASK-051 limitations or deferred implementation
items. The next milestone should continue to require adapters to publish affirmative coverage
evidence whenever they intend an empty discovery to be conclusive.
