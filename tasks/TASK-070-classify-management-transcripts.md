# TASK-070 — Classify Management Transcripts Without Polluting Earnings Calls

**Status:** Complete
**Type:** Corrective transcript-classification milestone
**Scope:** Provider-neutral transcript classification, qualification, retention, and canonical mapping

## Objective

Correct the transcript acquisition path so only deterministically established earnings calls
qualify as the canonical `earnings_transcript` artifact, while valuable non-earnings management
transcripts remain immutable repository evidence under an appropriate alternate classification.

The motivating live evidence is a repeated Seagate historical pull in which conference and
investor-event transcripts were substantial, dated, retained, and incorrectly projected as
`earnings_transcript` because their provider observation was `event_disposition: unknown`.

## Required diagnosis

Trace and document responsibility across discovery metadata, event classification, artifact
qualification, and canonical artifact mapping. Do not infer the responsible layer from titles
alone. Preserve the supplied live trace as operator evidence and identify the exact contract that
admits an unknown event.

## Required behavior

- Genuine earnings calls continue to qualify as `earnings_transcript`.
- Conference presentations, investor days, analyst events, fireside chats, technology conferences,
  summits, and similar management events do not qualify as `earnings_transcript`.
- Substantial non-earnings management transcripts remain retained through ordinary repository
  ingress and are queryable under a provider-neutral alternate transcript artifact classification.
- Retain a small deterministic event subtype for precision, but avoid a separate canonical
  artifact type for every title variation.
- Unknown transcript events fail closed for earnings qualification and remain retainable as broad
  management transcripts when the existing substance and source-governance gates pass.
- Classification uses trusted deterministic metadata or event semantics, never an LLM.
- Behavior is independent of provider and firm identity. No StockAnalysis or Seagate special case
  may appear in classification or qualification policy.
- Repeated range pulls continue to advance across genuine earnings calls without reevaluating or
  duplicating already retained management transcripts.

## Architectural constraints

- Preserve provider adapter ownership of provider-local parsing and opaque metadata observation.
- Preserve repository ownership of immutable bytes, artifact identity, provenance, observations,
  duplicate handling, canonical association authority, and integrity validation.
- Preserve the Pull Workflow and acquisition engine as the only product ingress path.
- Do not mutate historical immutable observations. Express a current classification correction
  through repository-owned append-only evidence.
- Preserve source-profile revision identity, acquisition targets, candidate/document identity,
  selection contracts, checkpoint monotonicity, discovery learning, and backfill semantics.
- An alternate canonical mapping must be explicitly permitted by governed source policy and
  validated by the repository; provider diagnostics alone are not repository authority.
- Do not add provider-specific branches above the provider boundary.

## Preferred model

Prefer one broad `management_transcript` canonical artifact for non-earnings management speech,
with deterministic event-kind metadata such as `conference`, `investor_day`, `fireside_chat`,
`analyst_event`, or `other_management`. This keeps broad management research possible while the
existing `earnings_transcript` corpus remains precise.

Use a more elaborate hierarchy only if implementation evidence proves the existing artifact
catalog and query contracts cannot preserve the required distinction with the simpler model.

## Regression coverage

Add focused automated evidence proving:

1. a representative earnings-call title and transcript qualify as `earnings_transcript`;
2. representative conference, investor-day, fireside-chat, analyst-event, summit, and technology-
   conference titles classify deterministically as non-earnings management events;
3. an unknown substantial management transcript fails closed for earnings qualification;
4. a conference transcript is retained, immutable, queryable as `management_transcript`, and absent
   from `earnings_transcript` queries;
5. provider-observed disposition and repository-owned resolved classification remain separately
   inspectable;
6. repeated observations and duplicate content retain existing content-addressed identity;
7. repository provenance and source-profile authority remain intact;
8. historical range pulls advance across earnings calls while retained conference events are not
   reacquired and do not advance the earnings checkpoint; and
9. relevant Pull Workflow, transcript provider, selection, repository, and artifact-query suites
   remain green.

## Documentation and review package

Update the current task index and architectural orientation where this milestone changes current
claims. Produce the normal commit-aware review package containing root-cause analysis, boundary
justification, changed files, representative classifications, regression and full validation,
committed diff metadata, integrity manifests, and the required Architectural Status Summary.

## Acceptance criteria

The task is complete when a provider-neutral deterministic policy admits only established earnings
calls to `earnings_transcript`, retains other substantial management transcripts under governed
`management_transcript` authority, preserves immutable acquisition and historical selection
invariants, passes focused and full validation, and has a reproducible committed review package on
a pushed task branch without merging to `main`.
