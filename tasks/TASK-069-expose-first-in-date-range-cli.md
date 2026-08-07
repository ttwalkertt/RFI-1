# TASK-069 — Expose Earnings Transcript `first_in_date_range` Selection in `rfi pull`

**Status:** Complete
**Type:** Bounded operator/CLI exposure
**Scope:** Earnings-call transcript acquisition selection only

## Objective

Expose the existing earnings-transcript acquisition selector `first_in_date_range` through the public `rfi pull` CLI so an operator can perform historical transcript backfill by repeatedly invoking the normal pull workflow over an inclusive date range.

This task does **not** add an automatic backfill loop. Each invocation should retain the existing acquisition behavior of selecting at most one qualifying transcript for the requested range. Repeated invocations are the intended backfill mechanism.

## Motivation

RFI already has an internal transcript acquisition selection model supporting:

- `latest`
- `first_in_date_range`

The public `rfi pull` command currently exposes only firm selection and therefore cannot request the historical selector.

The immediate use case is assembling a two-year Seagate earnings-call corpus for repository research into the evolution of HAMR management positioning.

## Required CLI Surface

Extend `rfi pull` with operator-facing transcript selection arguments equivalent to:

```zsh
rfi pull   --state ~/Documents/rfi/1/   --firm seagate   --selection first_in_date_range   --start-date 2024-08-07   --end-date 2026-08-07
```

Exact naming may be adjusted only if the current CLI conventions require it, but the public terminology should map clearly and directly to the existing transcript acquisition selection contract.

The existing command:

```zsh
rfi pull --firm seagate
```

must retain its current behavior and default to the existing `latest` selection semantics.

## Required Behavior

### `latest`

When no transcript-selection arguments are supplied:

- preserve current `rfi pull` behavior;
- use the existing `latest` transcript selection semantics;
- require no date range.

If `--selection latest` is explicitly supported, it must behave identically.

### `first_in_date_range`

When `first_in_date_range` is selected:

- require both start and end dates;
- interpret the range as inclusive;
- construct and pass the existing transcript acquisition selection object through the normal pull workflow;
- acquire the earliest qualifying transcript that remains eligible under existing repository/checkpoint semantics;
- preserve existing qualification, provider dispatch, retention, deduplication, provenance, diagnostics, and termination behavior.

Repeated execution of the same command must allow the existing checkpoint/repository logic to advance to the next eligible transcript rather than reacquiring the same retained transcript.

## Validation

Reject the request before acquisition when:

- `first_in_date_range` lacks either boundary;
- either date is malformed;
- the start date is later than the end date;
- date arguments are supplied in an invalid selection mode;
- an unsupported selection value is supplied.

Validation should follow existing CLI error and exit-code conventions.

Do not duplicate transcript qualification or date-selection logic in the CLI layer.

## Architectural Constraints

The CLI is an adapter only.

It must:

- translate operator arguments into the existing repository/application acquisition contracts;
- avoid implementing transcript-selection semantics itself;
- avoid provider-specific branching in the CLI;
- avoid direct repository or persistence access;
- preserve existing pull workflow orchestration and artifact independence;
- preserve current default behavior for all existing callers.

If the current public pull application contract cannot carry the existing transcript selection cleanly, make only the smallest contract extension necessary to pass that typed selection through the normal workflow.

## Out of Scope

Do **not** add:

- an automatic loop that fetches every transcript in a range;
- a new backfill command;
- UI controls for transcript historical selection;
- changes to transcript qualification criteria;
- changes to provider-specific discovery or parsing;
- changes to checkpoint semantics;
- changes to repository identity, artifact retention, or provenance;
- changes to date interpretation inside the existing selector;
- generalized date-range filtering for non-transcript source types;
- internet research or research-workspace behavior.

## Tests

Add focused automated coverage proving at least:

1. Existing `rfi pull --firm <firm>` behavior remains unchanged.
2. `first_in_date_range` accepts a valid inclusive date range.
3. CLI arguments are translated into the existing typed transcript acquisition selection.
4. Missing start or end boundaries fail before acquisition.
5. Malformed and reversed date ranges fail before acquisition.
6. Invalid selection/date combinations fail clearly.
7. Selection remains provider-neutral at the CLI/application boundary.
8. A repeated-pull scenario advances from the earliest eligible transcript to the next eligible transcript using existing checkpoint/repository behavior.
9. Existing qualification, deduplication, provenance, and pull-result semantics remain intact.
10. Relevant existing pull and earnings-transcript regression suites continue to pass.

The repeated-pull test should exercise the public or nearest public pull boundary rather than directly unit-testing the selector in isolation.

## Operator Documentation

Update CLI help and operator documentation so the historical workflow is clear.

The documentation should show:

```zsh
rfi pull   --firm seagate   --selection first_in_date_range   --start-date 2024-08-07   --end-date 2026-08-07
```

and state explicitly that:

- one qualifying transcript is selected per invocation;
- repeating the same command is the intended historical-backfill workflow;
- the existing repository/checkpoint state advances the selection;
- `latest` remains the default when no selection is specified.

## Review Requirements

Review specifically for:

- accidental changes to default `rfi pull` behavior;
- duplicated selection/date logic outside the existing contract;
- provider-specific CLI coupling;
- date-boundary off-by-one errors;
- failure to validate before acquisition;
- repeated pulls reacquiring the same transcript;
- unintended effects on non-transcript acquisition;
- weakening of qualification, checkpoint, deduplication, provenance, or repository authority semantics.

## Verification Package

Produce the normal task review package with enough evidence to independently verify:

- final CLI help output;
- the exact typed selection passed by the public pull path;
- successful valid-range execution;
- representative invalid-input failures;
- repeated-pull advancement across at least two eligible transcripts;
- regression results for relevant pull and earnings-transcript tests;
- changed files and architectural boundary justification.

## Acceptance Criteria

The task is complete when an operator can issue a public `rfi pull` command selecting `first_in_date_range` with an inclusive date range, repeat that same command to walk forward through eligible historical earnings-call transcripts, and do so without changing existing default pull behavior or any repository/provider qualification semantics.
