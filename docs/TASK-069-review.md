# TASK-069 Corrective Verification Report

## Result

TASK-069 is Complete after a corrective live-verification repair. The public `rfi pull` command
still accepts `latest` and `first_in_date_range`; omitted selection remains `latest`. Range mode
still requires two inclusive ISO dates and carries the existing typed selection through the
durable `PullRequest`, Pull Workflow, transcript adapter, and provider-neutral acquisition engine.

The repair covers the production state shape that the original two-pull proof omitted: the newest
transcript and a newer checkpoint already exist before historical range acquisition begins. After
staging the newest 2026-06-15 transcript, three identical public range pulls selected 2025-06-03,
2025-09-08, and 2025-12-09. Each invocation retained exactly one distinct immutable artifact. None
selected or retrieved the already-retained newest document.

No automatic loop, provider branch, qualification change, repository identity change, alternate
checkpoint, provenance path, or acquisition route was added.

## Root-cause analysis

The supplied 20-iteration Seagate trace showed that repository hydration was working: the archive
candidate for Q4 2026 reused immutable bytes and the repository-known trusted event date
`2026-07-28`. The archive trial also retrieved and validated many other in-range transcript dates.
Nevertheless, its terminal diagnostic reported zero qualified candidates.

Independent code tracing identified the mismatch in the neutral engine. For range selection, it
qualified every retrieved or hydrated candidate, then rejected any validated reporting-period
position at or before the source checkpoint. That rule is correct for forward `latest` progress,
but a checkpoint established by an already-retained newest transcript is necessarily later than
every historical backfill candidate. The blanket checkpoint comparison therefore discarded both
the retained newest candidate and every unretained older candidate before global range reduction.
The learned direct-document occurrence then rediscovered the already-seen newest identity, leaving
the qualified set empty and producing `no_match` plus a duplicate occurrence.

The original TASK-069 regression began with an empty repository. Its first range pull selected an
early quarter and established a low checkpoint; its second selected a later quarter. It proved
forward advancement, but did not reproduce a preexisting high checkpoint from ordinary `latest`
acquisition and therefore could not expose this fault.

## Architectural boundary justification

The CLI remains an adapter. `argparse` owns spelling, enum vocabulary, and ISO-date syntax. The
existing acquisition contract owns mode/boundary/reversed-range validation and inclusive
containment. `PullRequest` is the smallest public application-contract extension: it defaults to
`TranscriptAcquisitionSelection.latest()`, serializes the selection into the durable run request,
and restores the same typed contract before execution.

The workflow passes that selection to an earnings-transcript adapter only through its existing
`with_selection` seam. It does not select providers, qualify dates, inspect repositories, or know
candidate identities. The existing transcript policy still owns trusted-date qualification and
global earliest selection.

The repair is confined to the engine boundary where repository authority and the adapter-owned
terminal policy already meet. A retained deferred transcript is hydrated first and passes through
the same `qualify()` call as a newly retrieved candidate. If it qualifies, the engine records it as
already completed and excludes it from the remaining acquisition candidates. An unretained
qualified historical candidate is not rejected merely because an unrelated newer artifact set the
monotonic source checkpoint. Terminal persistence remains unchanged, and the existing checkpoint
finalizer still refuses to move progress backward.

This is candidate-level completion based on canonical repository identity, not a second checkpoint
model. It preserves immutable reuse, repository integrity checks, qualification rules, provider
dispatch, global reduction, provenance, learning, and monotonic checkpoint ownership. The
`latest` path has no terminal range policy and does not execute the changed branch. Other artifacts
and adapters remain unchanged.

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
  --start-date 2025-06-03 --end-date 2026-06-15
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

Default `latest` first retained 2026-06-15 and established the newest checkpoint. The same range
command was then invoked three times against that durable repository:

| Invocation | Selected validated event date | Pull result |
|---|---:|---|
| Precondition: omitted/default `latest` | 2026-06-15 | completed, one success |
| First identical range pull | 2025-06-03 | completed, one success |
| Second identical range pull | 2025-09-08 | completed, one success |
| Third identical range pull | 2025-12-09 | completed, one success |

The evidence records four different content-addressed artifact IDs. The checkpoint remains at
position 8106 from the newest staged transcript rather than moving backward. Every subsequent pull
hydrates and qualifies already-completed candidates from repository facts, excludes them from the
remaining selection set, and chooses the earliest unretained candidate. The newest document URL
has exactly one HTTP retrieval across staging and all three range pulls.

`validation/repeated-pulls.json` contains exact summaries, artifact identities, checkpoint state,
retained-qualification counts, and learned-trial request accounting.

## Learned direct-document behavior

Provider-backed planning still schedules configured provider discovery followed by learned direct
document seeds. This remains appropriate for the general global-selection contract: distinct
learned seeds can expose qualifying candidates not present in the configured archive, so the
engine cannot stop solely because one trial has candidates.

In the reported Seagate shape, however, the learned seed identifies the same Q4 candidate already
seen in the archive. Stable candidate identity deduplicates that occurrence before retrieval. The
large `bytes` value printed on the learned trial is the shared run-budget total after the archive
trial's candidate validations, not bytes fetched by the direct-document occurrence. The corrective
fixture proves every learned direct-document trial has `candidate_evaluated_count: 0`, and the
newest document is requested exactly once across initial staging plus three range pulls. The
learned retry is therefore a redundant discovery occurrence in this topology, but not a second
network refetch or a separate correctness defect. Retaining generic trial completeness is safer
than adding provider-specific early termination.

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

## Changed files in the corrective repair

- `src/rfi/acquisition/engine.py`: qualifies hydrated retained facts, removes only already-retained
  candidates from range acquisition, leaves unretained historical candidates eligible below a
  newer checkpoint, and adds retained-qualification diagnostics.
- `tests/test_task069.py`: reproduces a newest-retained/high-checkpoint repository and proves three
  repeated public-boundary advancements, unchanged default `latest`, immutable distinct artifacts,
  and zero learned direct-document reevaluation.
- `scripts/task069_review_evidence.py`: captures the staged precondition, three identical CLI
  pulls, checkpoint state, artifact identities, and learned-seed request accounting.
- `docs/TASK-069-review.md`: records the live root cause, repair boundary, verification, and
  learned-seed conclusion.

## Verification results

- Focused TASK-069 tests: PASS, 6 tests, including the retained-newest three-pull reproduction.
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
- Advancement retains the existing reporting-period checkpoint granularity. Historical successes
  below a newer checkpoint are tracked by canonical retained-candidate identity; no second cursor
  or backward checkpoint movement was introduced.
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
| Checkpoint/repository | Preserve monotonic source progress and identify completed candidates | Complete | Historical completion uses retained candidate identity below a newer checkpoint |
| Provider dispatch | Resolve configured provider below the application boundary | Complete, unchanged | Current production provider coverage remains narrow |
| Evidence/provenance | Retain immutable bytes, observations, diagnostics, and attribution | Complete, unchanged | Local single-operator product limits remain |
| Historical workflow | Repeat the same public command to walk the range | Usable with limitations | Manual repetition; no loop or continuation cursor |

The next milestone should be separately authorized. This task does not imply a GUI selector,
automatic corpus backfill, broader provider coverage, or research-workspace behavior.
