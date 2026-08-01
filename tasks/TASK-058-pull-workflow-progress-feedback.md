# TASK-058 — Pull Workflow Progress Feedback

## Status

Complete

## Objective

Make long-running Pull Sources executions visibly active by exposing durable, operator-facing
progress from the shared Pull Workflow and rendering both a numeric percentage and a concise
description above the browser progress bar.

## Problem Statement

The Pull Sources page previously calculated progress from nine coarse workflow stages. The
`execute_retrieval` stage can contain several slow source requests, so the bar and stage label
could remain unchanged for long periods even while retrieval was proceeding normally.

## In Scope

- Add a durable Pull Workflow progress snapshot containing a bounded 0–100 percentage, concise
  message, completed-source count, total-source count, and update timestamp.
- Publish progress at conceptual stage boundaries and before and after each enabled source is
  processed.
- Allocate most of the displayed range to the long-running retrieval stage.
- Display the percentage and descriptive message above the Pull Sources progress bar.
- Keep the progress bar's accessible value synchronized with its visual value.
- Preserve browser compatibility with older durable pull records that do not contain the new
  progress snapshot.
- Add focused workflow and browser-contract regression coverage.

## Out of Scope

- Byte-level download progress.
- Periodic synthetic progress while one provider request is blocked.
- Changes to acquisition results, source attemptability, repository ingress, or artifact storage.
- A new queue, scheduler, or workflow engine.
- Changes to CLI output or pull-result classification.

## Required Invariants

- Pull Workflow remains the sole acquisition orchestration path used by GUI, CLI, and REST.
- Progress publication must not create an alternate artifact or result authority.
- Displayed progress must remain within 0–100 and reach 100 only when workflow summarization
  completes successfully.
- Retrieval progress must reflect actual enabled sources processed rather than fabricated time
  estimates.
- Existing durable run records remain readable and renderable.
- Artifact and firm failures remain independent and retain their existing outcome semantics.

## Acceptance Criteria

1. The Pull Sources panel shows a numeric percentage above the progress bar.
2. The panel shows a short description of the active stage or source.
3. A running retrieval identifies the current source and firm.
4. Progress advances across enabled sources during `execute_retrieval`.
5. The status API exposes the durable progress snapshot.
6. The final successful progress snapshot is 100 with a completion message.
7. Older status records without the additive progress field use the existing stage-derived browser
   fallback.
8. Focused workflow, REST, and related browser integration tests pass.

## Implementation Resolution

`PullWorkflow` now records a `progress` object in the existing durable pull-run journal. Early
planning stages occupy 5–25 percent, actual enabled-source processing advances through 25–90
percent, and the existing ingestion, result-recording, and summary stages advance to 100 percent.
Before a source executes, the durable message identifies its ordinal, label, and firm. Completion
updates the processed and total counts.

The Pull Sources browser reads this repository-owned status field, renders a tabular numeric
percentage and concise live-region message above the bar, updates `aria-valuenow`, and falls back
to the former completed-stage calculation for historical records.

No acquisition, ingestion, artifact, or result contracts changed.

## Verification Evidence

The following commands passed on 2026-08-01:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_task015
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_task017 tests.test_task024 tests.test_task046
make lint format-check typecheck
make task015-proof
git diff --check
```

Focused evidence includes a deliberately blocked retrieval proving that a status read while the
same workflow remains running reports 25 percent and identifies the exact active source. The
focused Pull Workflow suite passed 10 tests; related browser integration coverage passed 10 tests;
and the deterministic TASK-015 proof reported `PASS` for all checks.

## Review Artifacts

- Implementation commit: `559e48b` (`fix: expose pull workflow progress details`).
- Changed production boundaries:
  - `src/rfi/pull/workflow.py`
  - `src/rfi/admin/pull_sources.html`
- Focused regression coverage: `tests/test_task015.py`.
- This task ticket and `TASKS.md` provide the task-specific scope and evidence record.

## Limitations

- A single active provider request cannot expose byte-level or transport-phase progress because the
  current adapter contract does not publish it. The display truthfully remains on that named source
  until the request returns.
- Progress is an operator-facing workflow estimate weighted toward retrieval; it is not an elapsed
  time forecast.

## Architectural Status Summary

- Pull Workflow orchestration: **Complete and unchanged** as the shared GUI, CLI, and REST entry
  point.
- Durable pull-run journal: **Complete** for additive operator progress snapshots.
- Pull Sources progress presentation: **Complete** for percentage, current activity text, and
  accessible bar state.
- Historical run compatibility: **Complete** through the browser's stage-derived fallback.
- Provider-internal progress: **Not Started** and outside this task; active source identity is the
  current truthful granularity.
- Next architectural milestone: continue planned acquisition adapter coverage without changing the
  Pull Workflow orchestration authority.
