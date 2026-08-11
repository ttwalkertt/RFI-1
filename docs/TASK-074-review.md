# TASK-074 architectural review

## Outcome

TASK-074 implements and evaluates the minimum independent QA and single bounded-repair loop over
the five preserved TASK-073 answers. It proves the exact lifecycle and preserves reviewer
independence, but the analytical result is negative enough that the loop is not accepted as closing
the general-runtime quality gap.

The final disposition is **QA is useful but additional runtime-side quality controls require a
future experiment**. Eight supported QA #1 findings and useful repairs demonstrate value, while
three missed known targets, three false QA #2 passes, residual repair failures, and one
repair-induced significant regression prevent a stronger conclusion.

## Implemented boundary

The new `rfi.investigation_qa` package provides frozen QA, repair, unresolved-item, resolution, and
terminal-review contracts; strict structured-output schemas and parsers; durable case identity; and
a hard one-cycle state machine. The experiment runner composes fresh isolated Codex stages against
the unchanged TASK-073 MCP and captures every prompt, schema, output, runtime event stream, MCP
trace, command, digest, timing, and lifecycle record.

The state machine permits only `first_pass_fixed -> qa1_complete -> repair_complete -> terminal` in
the proving cases and exposes no escalation transition. The repair receives durable bounded work
products rather than the original investigation trace. QA #2 is terminal even when it returns
`repair_required`.

TASK-071 contributed only architecture-neutral lessons: immutable typed contracts, strict
serialization, explicit case association, and state-machine enforcement. TASK-071's investigation
harness, protocol, evidence-admission policy, closed-record adjudicator, recovery work orders,
budgets, final-turn rules, and reporting architecture were not recreated.

No TASK-073 MCP implementation changed. No QA-specific MCP tool, prompt, semantic/vector retrieval,
additional evidence type, repository mutation, reviewer negotiation, second repair, recursive
review, or escalation path was added.

## Experiment result

All five fixed answers retained their TASK-073 digests, all 15 runtime stages used distinct fresh
contexts, retained repository bytes were unchanged, and each case performed exactly one repair and
one terminal QA #2. The preserved startup negative control records a schema-startup failure before
model review or evidence access; the schema-only correction did not alter the role prompts, and the
five proving cases were then run once.

Post-run adjudication found eight of eight QA #1 findings supported and no unsupported substantive
finding. QA detected five of eight known defect targets. It missed technology's broad stable-locator
deficit, chronology's false latest boundary, and the insufficiency control's absent speaker-metadata
qualification. Only one of four QA #2 `pass` dispositions was diagnostically sound. Sentiment
remained `repair_required`; its repair left evidence-mapping defects and introduced a significant
inventory-citation regression. One justified unresolved insufficiency item was explicitly retained.

The detailed metrics, finding-resolution matrix, false-positive/miss analysis, before/after quality
comparison, cost, and attribution are in
[`task074-qa-repair-evaluation.md`](task074-qa-repair-evaluation.md).

## Verification and review evidence

Focused tests cover finding/severity/disposition schemas, IDs and evidence references, repair
serialization, unresolved repair items, resolution states, immutable case/work-product association,
fresh reviewer packages, exact prompts, read-only frozen MCP capabilities, absence of first-pass
reruns, prohibition of escalation, and hard terminal behavior after one repair.

The experiment verifier independently re-hashes every preserved stage artifact, reconstructs every
prompt from the allowed durable inputs, checks 15 unique contexts, parses all outputs, replays all
lifecycle records, limits traces to the unchanged TASK-073 capabilities, proves retained state and
the fixed source stayed unchanged, and validates the post-run adjudication and startup negative
control. The normal commit-aware package contains the committed diff, implementation, tests,
prompts, outputs, traces, fixed TASK-073 inputs, diagnostic adjudication, focused/full validation,
and package digests.

## Architectural Status Summary

- **Immutable evidence and acquisition history — Complete, unchanged.** TASK-074 made no retained
  authority or acquisition mutation.
- **Minimal local MCP surface — Complete for TASK-073, unchanged.** The same three read-only tools
  and resources served QA and repair; no access failure justified broadening them.
- **Independent QA contracts — Implemented POC.** Strict findings, dispositions, references, and
  review outputs exist and are proven over five preserved answers; analytical quality is narrow and
  provisional.
- **Single bounded repair — Implemented POC.** Repair receives only authorized durable context,
  records feasible actions and unresolved items, and has no escalation path.
- **Terminal independent re-review — Implemented POC.** QA #2 uses a fresh context, records each
  QA #1 finding's resolution and new defects, and cannot trigger another repair.
- **General-runtime quality closure — Not accepted.** Useful true findings did not prevent three
  known misses and three false terminal passes.
- **Product composition — Deferred.** The proof runner and contracts are not added to stable CLI,
  browser, workspace, repository authority, or MCP interfaces.
- **Next experiment — First-pass prompting.** Evidence supports isolating investigator prompting;
  TASK-074 does not authorize additional repair cycles or escalation design.

Architectural change: RFI now has an independently reviewable experimental QA/repair boundary that
preserves substrate/runtime separation and enforces one-cycle termination. The experiment shows
that this boundary is useful infrastructure but not a reliable quality control by itself.
