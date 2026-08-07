# TASK-069 Verification Report

## Result

TASK-069 is Complete. The public `rfi pull` command accepts the existing transcript modes
`latest` and `first_in_date_range`. Omitted selection remains `latest`. Range mode requires two
inclusive ISO dates, constructs the existing `TranscriptAcquisitionSelection`, and carries that
typed value through the durable `PullRequest` and normal Pull Workflow to the selection-aware
earnings-transcript adapter.

One invocation still selects at most one qualifying transcript. Two identical deterministic
fixture commands selected 2026-03-10 and then 2026-06-15, retained two distinct immutable
artifacts, and advanced the existing checkpoint from Q1 to Q2. No automatic loop, provider branch,
qualification rule, repository identity, provenance path, or alternate acquisition route was
added.

## Architectural boundary justification

The CLI remains an adapter. `argparse` owns spelling, enum vocabulary, and ISO-date syntax. The
existing acquisition contract owns mode/boundary/reversed-range validation and inclusive
containment. `PullRequest` is the smallest public application-contract extension: it defaults to
`TranscriptAcquisitionSelection.latest()`, serializes the selection into the durable run request,
and restores the same typed contract before execution.

The workflow passes that selection to an earnings-transcript adapter only through its existing
`with_selection` seam. It does not select providers, qualify dates, inspect repositories, or know
candidate identities. The neutral acquisition engine applies the existing checkpoint rule—an
already validated position at or before durable progress is ineligible—before the existing global
range reduction. This allows repeat invocations to advance while preserving checkpoint ownership,
replay `no_change`, retention, deduplication, learning, and terminal-result semantics. Other
artifacts and retrieval adapters continue through their prior registry projection unchanged.

## Public CLI help

```text
usage: rfi pull [-h] [--state PATH] (--firm FIRM_ID | --all-configured)
                [--selection {latest,first_in_date_range}]
                [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]

options:
  --selection {latest,first_in_date_range}
                        earnings-transcript selection mode (default: latest)
  --start-date YYYY-MM-DD
                        inclusive transcript range start; required for
                        first_in_date_range
  --end-date YYYY-MM-DD
                        inclusive transcript range end; required for
                        first_in_date_range
```

The installed help also states that range mode selects at most one transcript per invocation and
that repeating the same command advances through checkpoint state. The complete captured output is
`validation/pull-help.txt` in the review package.

## Representative successful execution

```sh
rfi pull --state STATE --firm oracle --selection first_in_date_range \
  --start-date 2026-03-10 --end-date 2026-06-15
```

The deterministic public CLI execution exited 0 with a completed run and one successful artifact:

```json
{
  "artifacts": 1,
  "firms": 1,
  "success": 1,
  "retrieval_failure": 0
}
```

The complete CLI JSON is retained as `validation/successful-cli.txt`.

## Validation failures before acquisition

All representative invalid commands exited 2, and the evidence harness proved `pull_sources` was
never called:

- missing range boundaries: `first_in_date_range requires date boundaries`;
- reversed range: `transcript selection start_date must not follow end_date`;
- malformed date: `invalid date 'not-a-date'; expected YYYY-MM-DD`;
- unsupported mode: `invalid choice: 'unsupported'`; and
- dates with `latest`: `latest transcript selection cannot include a date range`.

Exact commands, stdout, stderr, exit codes, and the acquisition call-count assertion are in
`validation/validation-failures.json`.

## Repeated-pull advancement

The same command was invoked twice against one durable fixture repository:

| Invocation | Selected validated event date | Pull result |
|---|---:|---|
| First | 2026-03-10 | completed, one success |
| Second | 2026-06-15 | completed, one success |

The evidence records two different content-addressed artifact IDs and terminal checkpoint position
8106 (2026 Q2). The second invocation checkpoint-filtered the already completed Q1 candidate before
the unchanged terminal selector chose Q2. `validation/repeated-pulls.json` contains the exact
summaries, artifact identities, and checkpoint.

## Default compatibility and typed propagation

Focused tests prove:

- omitted CLI selection sends `PullRequest(("oracle",))`, whose typed default is `latest` with no
  dates;
- explicit range syntax sends the exact existing typed selection;
- the durable run stores its canonical `to_dict()` representation and restores a
  `TranscriptAcquisitionSelection` before adapter invocation;
- the selection seam is provider-neutral at the CLI/application boundary; and
- direct non-selection-aware and non-transcript paths are unchanged.

The durable Pull Workflow result keeps the requested typed selection independently inspectable in
its request record without adding selection fields to source identity or provider configuration.

## Changed files

- Application and acquisition: `src/rfi/cli.py`, `src/rfi/pull/contracts.py`,
  `src/rfi/pull/workflow.py`, `src/rfi/acquisition/contracts.py`, and
  `src/rfi/acquisition/engine.py`.
- Tests and deterministic evidence: `tests/test_task069.py` and
  `scripts/task069_review_evidence.py`.
- Review tooling: `scripts/generate_task069_review.py` and `Makefile`.
- Operator documentation: `docs/application-cli.md`, `docs/pull-workflow.md`, and
  `docs/operator-guide.md`.
- Task authority/completion: `tasks/TASK-069-expose-first-in-date-range-cli.md`, `TASKS.md`, and
  this review.

## Verification results

- Focused TASK-069 tests: PASS, 6 tests.
- Pull and earnings-transcript regression gate (`make task069-test`): PASS, 190 tests spanning
  TASK-048/048A, TASK-052/053, TASK-056–065, TASK-069, and the shared Pull Workflow.
- Deterministic CLI/range/repeat evidence: PASS.
- Lint, format, lightweight type, import, documentation, baseline, and diff checks: PASS.
- Full repository-standard `make validate`: PASS, 686 tests plus every repository proof and build
  gate.

The commit-aware package captures the exact reviewed base/head/range, complete patch, changed-file
inventory, CLI help, successful execution, validation failures, repeat advancement evidence,
focused regression output, full validation output, manifest hashes, ZIP, and ZIP SHA-256.

## Limitations

- This is a single-invocation selector, not an automatic historical-backfill loop.
- The existing bounded discovery policies still determine observable coverage.
- Advancement retains the existing reporting-period checkpoint granularity; no same-day document
  continuation cursor was introduced.
- The CLI selection applies to the existing selection-aware earnings-transcript acquisition path;
  it does not generalize dates to other artifact types.

## Architectural Status Summary

| Subsystem | Responsibility | Status after TASK-069 | Important limitation / next milestone |
|---|---|---|---|
| Public pull CLI | Parse operator transcript selection and dates | Complete | CLI only; no GUI control |
| Pull request contract | Carry typed selection with a compatibility default | Complete | Transcript-specific optional policy |
| Durable pull journal | Preserve and restore canonical selection | Complete | Existing schema-less canonical JSON record |
| Pull orchestration | Apply invocation selection through the normal adapter path | Complete | At most one selected transcript per invocation |
| Transcript selector | Qualify inclusive dates and select the earliest eligible result | Complete, unchanged | Bounded discovery remains authoritative |
| Checkpoint/repository | Exclude completed reporting periods and advance durable progress | Complete | Existing reporting-period granularity |
| Provider dispatch | Resolve configured provider below the application boundary | Complete, unchanged | Current production provider coverage remains narrow |
| Evidence/provenance | Retain immutable bytes, observations, diagnostics, and attribution | Complete, unchanged | Local single-operator product limits remain |
| Historical workflow | Repeat the same public command to walk the range | Usable with limitations | Manual repetition; no loop or continuation cursor |

The next milestone should be separately authorized. This task does not imply a GUI selector,
automatic corpus backfill, broader provider coverage, or research-workspace behavior.
