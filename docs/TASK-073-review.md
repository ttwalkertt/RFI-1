# TASK-073 architectural review

## Outcome

TASK-073 implements the minimum local, read-only RFI MCP transcript surface and completes the five
Seagate Codex Work investigations. The experiment does not justify replacing TASK-071's bounded
investigative behavior: Codex Work returned a materially wrong first/latest chronology and weaker
evidence mapping even though RFI exposed the correct candidates and verified evidence.

The final disposition is **General runtime is not yet a proficient replacement for TASK-071
investigative behavior**. The surface was not broadened in response.

## Implemented boundary

RFI now exposes three tools—governed artifact selection, bounded lexical transcript candidates, and
immutable artifact-ID byte reads—and descriptive, identity, provenance, corpus, exact-segment, and
ordered-window resources over local `stdio`. A standalone versioned dictionary explains stable data
semantics without prescribing research procedure. Artifact history remains explicitly deferred.

The implementation adds the three required TASK-072 access improvements:

- immutable artifact-addressed whole/range reads with checksum and range-digest verification;
- replaceable transcript access generation identity, repository snapshot, health, staleness,
  indexed/eligible inventory, diagnostics, bounds, and typed outcomes; and
- a discoverable machine-legible data dictionary separating retained authority, derived access
  projections, coverage, empty results, failures, and answer sufficiency.

No MCP prompt, acquisition mutation, remote transport, filesystem tool, semantic retrieval, second
evidence type, investigation state, planner, stopping rule, adjudicator, model adapter, or report
generator is introduced. The MCP package does not import TASK-071's harness, adjudication, reporting,
or OpenAI adapter.

## Experiment and diagnostic result

The experiment used one minimal orientation sentence and the five TASK-071 question wordings. It
preserved separate Codex and MCP traces and proved the 21-document/2,268-segment retained state was
unchanged at `sqlite-revision-8237`.

The detailed comparison and per-class attribution are in
[`task073-codex-work-evaluation.md`](task073-codex-work-evaluation.md). In summary:

- no repository/MCP/access failure was observed;
- no material retrieval-quality failure was established;
- chronology stopping/selection and invalid-bound tool use were investigative-runtime failures;
- no new repository-authority error was observed, while known event-kind, speaker, and coverage gaps
  remained visible;
- false chronology, missing stable claim citations, and scope overstatement were synthesis failures.

The independent external analysis named by the ticket has no artifact or locator in this checkout or
the retained TASK-071 evidence. The package records that limitation and makes no unsupported external
comparison claim. TASK-071 is the only reproducible comparison baseline available here.

## Verification and review evidence

Focused tests cover discovery and schemas, artifact-query equivalence, known-empty versus unknown,
immutable reads, digests, stale cursors/generations, logical-document revision, drift prevention,
stable segments, corrupt/unavailable/partial access, bounds, repository failures, dependency
separation, corpus parity, and read-only operation. TASK-071 regression tests remain unchanged.

The normal commit-aware review package includes the complete committed diff, implementation,
dictionary, tests, experiment runner and verifier, raw five-case Codex event streams and answers,
raw correlated MCP traces, corpus inventory/parity proof, TASK-071 reports/traces, startup-failure
negative control, focused and full validation output, and package manifest/digests.

## Architectural Status Summary

- **Immutable evidence and acquisition history — Complete, unchanged.** RFI remains exact-byte,
  canonical identity, observation, and provenance authority.
- **Artifact query and immutable read contracts — Complete for the bounded slice.** Exact reads now
  resolve by immutable artifact ID; artifact history remains deferred.
- **Transcript acquisition/classification — Usable with limitations.** Historical event kind,
  speaker attribution, conference classification, and corpus coverage remain explicit gaps.
- **Transcript access generation — Implemented for the experiment.** Health, staleness, snapshot,
  inventory, build omissions, bounds, typed outcomes, candidate search, and verified expansion are
  externally visible.
- **Minimal local MCP surface — Complete for TASK-073.** Three read-only tools and required resources
  are implemented over local `stdio`; broader catalog/productization remains deferred.
- **Codex Work experiment — Complete.** All five cases ran with minimal orientation and preserved
  traces against the unchanged proving corpus.
- **General-runtime replacement — Not accepted.** Runtime chronology, evidence-admission, scope
  calibration, and synthesis quality were not proficient relative to TASK-071.
- **Independent external comparison — Evidence unavailable.** No independently reviewable reference
  was supplied or found; this remains a documented completion limitation.

Architectural change: RFI has a working, trustworthy transcript-only MCP epistemic substrate without
owning the investigative loop. The experiment demonstrates that substrate sufficiency does not by
itself guarantee proficient general-runtime investigation, so no broader MCP commitment follows.
