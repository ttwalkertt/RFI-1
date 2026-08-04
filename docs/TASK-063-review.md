# TASK-063 Architectural Review — Bounded Transcript Resolution Session

## Result

TASK-063 is complete with its corrective classifier review applied. Production transcript
acquisition canonicalizes learned repository history into one ordered resolution phase, classifies
only supplied pages, admits direct transcript documents or one-hop transcript links, and uses at
most one configured fallback under the same ephemeral run budget.

The resolver now depends on an explicit public structural document assessment rather than the
retriever's private validation method. Firm identity, event date, selection, checkpoints,
persistence, and learning remain downstream concerns and cannot reclassify a structurally
recognized transcript page as a listing or unsupported page.

## What `_transcript_validation_failure()` Checks

Before the corrective review, `_transcript_validation_failure(response, label)` performed these
checks:

1. Reject empty or whitespace-only content.
2. For HTML or XHTML:
   - require an HTML or doctype signature;
   - reject a short page instructing the caller to enable or requiring JavaScript;
   - require transcript terminology in the link label or extracted page text;
   - require earnings, quarterly, financial-results, results-call, or conference-call terminology
     in extracted page text; and
   - require speaker or section evidence such as Operator, prepared remarks, questions and answers,
     CEO, or CFO.
3. For PDF:
   - require a `%PDF-` signature; and
   - require transcript plus earnings-call terminology in the label and final URL evidence.
4. Reject every other media type.

It did **not** check HTTP status, governed host, firm identity, publication/event date, requested
date range, selector eligibility, reporting-period checkpoint, retained-artifact replay,
persistence, learning, or checkpoint advancement. The caller performs HTTP and host checks before
this method, establishes date evidence separately, and performs firm, selection, checkpoint, and
durable lifecycle checks elsewhere.

The method therefore contained structural candidate validation, not durable qualification.
Nevertheless, using a private validator method to choose resolver topology made that separation
implicit and fragile.

## Explicit Classifier and Validator Boundary

`TranscriptDocumentStatus`, `TranscriptDocumentAssessment`, and
`classify_transcript_document()` now define one public, pure structural assessment. Its inputs are
only the fetched response and observed label. Its output states whether the page has transcript
document structure and, when it does not, the exact structural reason.

The resolver calls only `classify_transcript_document()`. A positive assessment produces a direct
document proposal and prevents link parsing. A non-document HTML assessment may proceed through
the existing one-hop listing parser.

`_transcript_validation_failure()` remains the candidate validator's compatibility mapping. It
maps the structural assessment to the existing stable `CandidateFailureCode` values. Changing
firm, date, selector, checkpoint, persistence, or learning validation no longer changes resolver
page roles. Changing structural classification requires an explicit change to the public
assessment contract and its focused tests.

Focused negative controls prove:

- a structurally valid Other Corp transcript is classified `transcript_document`, does not follow
  its archive link, and then fails the existing Firm A identity validation;
- a structurally valid 2026 transcript remains `transcript_document`, does not follow its archive
  link, and is then rejected by a requested 2025 date range; and
- patching the private `_transcript_validation_failure()` to raise does not affect resolver
  classification, proving the resolver no longer calls it.

## Resolution Architecture

```text
repository learning order
  -> canonical learned-seed phase
       -> public structural page assessment
       -> direct document, or immediate transcript links only
  -> existing retrieval and durable qualification
  -> one configured fallback only when no terminal learned result exists
```

No recursive listing traversal or search-engine fallback occurs in the production engine path.
The pre-existing graph-discovery class remains only as a compatibility seam for legacy callers of
aggregate `discover()`; normal engine trials and injected trials use `BoundedTranscriptResolver`.

## Ordering and Terminal Behavior

The orchestrator reads learned anchors in repository order, considers resolved then requested URL
forms, and applies the conservative transcript URL normalizer. The first canonical occurrence is
authoritative and duplicate counts remain observable.

Proposal order remains learned-seed FIFO position, existing within-page rank, existing
deterministic tie-breakers, then configured fallback. `latest` stops after the first validated
result. Candidate retrieval failures within a consolidated learned phase continue to the next
ordered candidate, preserving the former useful per-seed fallthrough. Contract, integrity, and
repository conflicts remain fail closed.

`first_in_date_range` still qualifies distinct candidates and uses its existing global terminal
policy to select the earliest validated content date. No selector moved into classification or
resolution.

## Run-Level Resource Session

`BudgetedTranscriptTransport` remains the one run-local owner of page, byte, distinct-host,
redirect, elapsed-time, response-cache, and unique-candidate accounting. The adapter resets this
state during normal or injected planning and reuses it across learned and configured-fallback
phases. Canonical requested and redirect-resolved aliases share cached responses.

Budget exhaustion is explicit. An exhausted phase with no proposal raises the existing typed
adapter failure; candidate-cap exhaustion prevents fallback from receiving a fresh allowance.
Neither condition is presented as successful empty coverage or unchanged replay.

## Amazon Evidence and Before/After Work

The original review incorrectly described all Amazon, IBM, and Western Digital tests as captured
topologies. That claim is corrected:

- Amazon now has a checked-in sanitized fixture derived from the operator-provided failure capture.
  It retains the public seed/archive topology and exact work counters while removing run,
  repository-source, candidate-hash, and timestamp identifiers.
- IBM and Western Digital remain deterministic synthetic shapes. They demonstrate the same
  shared-archive pattern but are not represented as captures.

The Amazon capture contained two independent learned-seed trials, beginning at the Q3 2016 and Q4
2016 transcript pages. Both expanded the same archive and exposed the same Q2 2026 candidate graph.

| Work for the two learned seeds | Before TASK-063 capture | TASK-063 sanitized regression |
|---|---:|---:|
| Seed/graph pages fetched | 26 | 2 seed pages |
| Outward pages fetched | Included in the 26 | 0 |
| Response bytes | 9,130,104 | Not compared; fixture content is sanitized |
| Raw hyperlinks examined | 2,932 | 0 |
| Normalized unique hyperlinks | 2,296 | 0 |
| Eligible/traversed hyperlinks | 152 / 152 | 0 / 0 |
| Candidate proposals | 128 | 2 direct document proposals |
| Candidates selected under per-trial caps | 80 | 2 admitted before engine terminal behavior |
| Search queries | 0 | 0 |

The after-state test fetches only the two learned document URLs. It does not fetch the shared
archive or any Q2 2026/Q1 2026/Q4 2025 archive candidate. During a full engine run, a fetched direct
document is subsequently validated from the same run-local response cache.

## Invocation and Durable-State Boundaries

- Normal acquisition has one learned phase and at most the first configured HTTP(S) hint as
  fallback.
- A configured fallback canonically equal to a learned seed is removed during planning.
- Operator injection resolves exactly the supplied normalized seed and adds no learned or
  configured seed.
- Production resolution submits no search query.
- TASK-062 `CandidateIdentity` remains the sole stable candidate equivalence definition.
- No repository schema, durable resolver session, learning representation, checkpoint model,
  persistence branch, or state repair was introduced.

TASK-059 regressions retain `latest` and range selection. TASK-060 retains injected/learned
equivalence, mutation-free replay, monotonic newer-content advancement, and fail-closed checkpoint
cursor conflict. TASK-061 inspection and TASK-062 candidate-conflict protection remain green.

## Complexity and Robustness Review

- One public structural document assessment defines page-document classification.
- Firm/date/selector/checkpoint qualification is absent from that assessment.
- The resolver has no dependency on the private candidate validator.
- One transport object owns all run resource accounting and response reuse.
- The resolver has no recursive queue, pagination loop, discovered-listing traversal, or search
  submission.
- Seed origin affects planning and occurrence attribution, not persistence or checkpoints.
- Candidate conflict protection remains unchanged and fail closed.
- Diagnostics and fixture evidence are bounded; fixture provenance and sanitization are explicit.
- IBM and Western Digital evidence is labeled synthetic rather than captured.

## Validation Results

- `make task063-test`: PASS, 11 focused tests.
- Classifier/resolver boundary regressions: PASS.
- Sanitized Amazon before/after regression and synthetic IBM/WDC shapes: PASS.
- `make task057-test`: PASS, 104 tests.
- `make task058-test`: PASS, 109 tests.
- `make task059-test`: PASS, 121 tests.
- `make task060-test`: PASS, 133 tests.
- `make task061-test`: PASS, 5 tests.
- `make task062-test`: PASS, 5 tests.
- Relevant acquisition, engine, discovery, repository, API, replay, and checkpoint suites: PASS.
- Formatting, lint, type checking, import, documentation, design-baseline, build, and diff checks:
  PASS.
- Full `make validate`: PASS.

The review-package generator reruns and retains complete output from the final committed branch
head. Counts above reflect the final regenerated package.

## Assumptions and Limitations

- The HTML structural classifier uses bounded text extraction rather than semantic DOM roles.
- PDF classification can verify the file signature but relies on label/final-URL attribution for
  transcript and earnings-call terminology because PDF text extraction is not part of the current
  retriever.
- The resolver intentionally does not discover links behind pagination or nested listing pages.
- Every distinct learned seed page is fetched in FIFO order before candidate validation begins.
- The response cache is ephemeral and source-run scoped.
- The old graph crawler remains reachable only through the legacy aggregate discovery seam.
- Amazon evidence is sanitized from a real operator capture; IBM/WDC evidence remains synthetic.
- No existing Amazon durable state is deleted, rewritten, or reinterpreted.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Limitations / next milestone |
|---|---|---|---|
| Structural transcript classifier | Media/signature/transcript document assessment | Complete | HTML regex/text assessment; PDF has no text extraction |
| Durable candidate validator | Firm, date, selection, checkpoint, and content qualification | Complete and separate | Existing validation policy remains authoritative |
| Transcript resolver | Classify supplied pages and admit direct documents/links | Complete | No pagination or nested-listing discovery |
| Learned orchestration | Canonical FIFO consolidation | Complete | Every distinct learned seed is probed |
| Configured fallback | One conditional archive phase | Complete | Only first configured HTTP(S) hint participates |
| Run resource control | Shared budget, response cache, candidate ceiling | Complete | Ephemeral and process-local |
| Candidate identity and persistence | TASK-062 equivalence and existing durable lifecycle | Complete and unchanged | No historical state repair |
| Legacy graph discovery | Direct aggregate-caller compatibility | Usable with limitations | Remove after remaining callers migrate |

The next milestone should remove the legacy aggregate crawler after caller migration or add an
explicit provider adapter for archives requiring pagination; it should not weaken the classifier
boundary or expand this resolver into a general crawler.
