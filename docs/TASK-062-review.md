# TASK-062 Architectural Review — Candidate Identity and Discovery Occurrence

## Result

TASK-062 is complete. Candidate duplicate conflict detection now compares one explicit
allowlisted `CandidateIdentity`, while trial-local attribution is represented by one explicit
`DiscoveryOccurrence`.

Repeated discovery of the same stable candidate across pages and learned, configured, or
operator-supplied trials no longer fails because timestamps, proposal ranks, deterministic ranks,
traversal paths, aliases, labels, or seed attribution differ. The first deterministic occurrence
remains authoritative for execution and existing repository attribution. Reusing a candidate ID
with conflicting stable identity remains a fatal malformed-adapter result.

## Root Cause

The engine previously compared candidate representations that mixed durable candidate semantics
with discovery-path attribution. The first corrective projection removed timestamps, proposal
ranks, and selected trial fields, but retained `deterministic_selection_rank`. A candidate reached
at depth two from a learned transcript page and depth one from a configured archive therefore
received two different ranks and was falsely classified as ambiguous.

The captured Amazon reproduction used the same Q4 2016 candidate with ranks equivalent to:

```text
learned transcript page: [0, -8068, -2, 0]
configured archive:      [0, -8068, -1, 0]
```

Western Digital exhibited the same cross-seed graph shape. Earlier IBM evidence showed the same
class of learned-trial overlap. TASK-062 represents all three as equivalent discovery occurrences
of one candidate identity.

## Candidate Identity Contract

`CandidateIdentity` is an exported frozen model. It includes:

- candidate ID and document ID;
- position and revision;
- disposition and disposition reason;
- immutable acquisition target;
- discovery method and provider identifiers;
- canonical candidate locations;
- allowlisted metadata affecting identity, validation, selection, persistence, or checkpoints.

Canonical HTTP(S) resolved locations use the existing conservative URL-identity normalizer. Host
case, default ports, fragments, and path normalization therefore do not manufacture distinct
candidate identities, while query-distinct URLs remain distinct.

The metadata projection is constructed from one module-level stable-field allowlist. It does not
copy full provenance and subtract trial-local fields. Known SEC, fixture, direct-URL, and transcript
identity metadata remains represented so the generic engine's existing conflict protection is not
weakened.

## Discovery Occurrence Contract

`DiscoveryOccurrence` is an exported frozen model containing:

- discovery timestamp;
- trial ID;
- starting seed;
- seed kind and source;
- exact observed locations;
- proposal and deterministic ranks;
- requested URL, observed aliases, and link label;
- traversal depth, parent path, and ranking reasons when emitted.

No missing occurrence field is fabricated. The engine supplies existing trial attribution when a
trial exists and otherwise uses explicit candidate metadata when present.

## First-Occurrence Authority and Global Deduplication

The engine maintains one candidate-identity map for the entire run, outside the page and trial
loops. The first occurrence stores:

- the complete existing canonical candidate used by checkpoint and persistence logic;
- its `CandidateIdentity` used only for later duplicate conflict checks;
- its `DiscoveryOccurrence` used as authoritative diagnostic attribution.

Later equivalent occurrences follow the existing duplicate-outcome path and never enter
checkpoint filtering, retrieval, validation, terminal selection, success persistence, learning, or
checkpoint advancement. Existing duplicate audit semantics remain unchanged.

No later occurrence can replace the authoritative candidate. Diagnostic representative selection
therefore cannot reorder candidates or change `latest` or `first_in_date_range` behavior.

## Fail-Closed Conflict Proof

The focused regression changes the document ID on the second occurrence while preserving the
candidate ID. The resulting `CandidateIdentity` differs, and the engine returns:

```text
status: failed
failure_class: malformed_adapter
message: ambiguous duplicate candidate: <candidate-id>
```

The checkpoint remains unchanged and no retrieval occurs. Existing repository conflict and
integrity handling is untouched.

## Bounded Occurrence Diagnostics

Runs with repeated candidates emit one `candidate_occurrences` diagnostic containing exact:

- candidates-with-multiple-occurrences count;
- duplicate-occurrence count;
- per-sampled-candidate occurrence count.

Diagnostics retain at most eight candidate samples and three occurrences per sampled candidate.
Nested occurrence collections retain at most eight items, strings retain at most 512 characters,
and every truncation sets an explicit omission flag. Samples preserve first-occurrence order.

The focused bound test discovers ten candidates five times each. It reports ten repeated
candidates and forty duplicate occurrences while retaining eight candidate samples and three
occurrences per sample with both omission flags set.

## Selector and Persistence Compatibility

Focused execution proves:

- `latest` still persists the first validated candidate and terminates the successful trial;
- `first_in_date_range` still validates globally distinct candidates and persists the earliest
  qualifying validated event date;
- checkpoint filtering occurs only for the first occurrence;
- later equivalent occurrences remain duplicate audit outcomes;
- no duplicate artifact, observation, learned anchor, or checkpoint advancement is introduced;
- configured and operator-supplied behavior continues through the same engine contracts.

No traversal, search, ranking, validation-date, seed planning, learning, checkpoint, replay,
repository schema, request, or HTTP behavior changed.

## Captured Topology Evidence

The focused tests include:

- Amazon learned transcript pages plus configured StockAnalysis archive converging on the Q4 2016
  candidate with depth-two versus depth-one ranks;
- IBM learned transcript-page trials converging on one archive candidate;
- Western Digital learned transcript pages plus archive converging on one candidate graph.

Every topology completes with one unique candidate, zero retrievals after checkpoint filtering,
one authoritative checkpoint-filtered outcome, later duplicate outcomes, unchanged checkpoint,
and no ambiguity failure.

## Complexity and Robustness Review

- One candidate identity model and one stable metadata allowlist exist.
- One discovery occurrence model and one occurrence-field allowlist exist.
- The engine has one global per-run identity map; no page-local or trial-local shadow identity
  model was added.
- Existing canonical candidates remain the sole checkpoint and persistence inputs.
- Candidate-ID conflict protection remains fail closed.
- The first occurrence cannot be replaced by a later rank or seed.
- No seed-origin branch was introduced.
- No repository schema, migration, state rewrite, second checkpoint model, or replay-only
  persistence branch was introduced.
- Diagnostic totals are exact and diagnostic detail is independently bounded.

## Validation Results

- `make task062-test`: PASS, 5 focused tests.
- Engine plus TASK-062 focused regression: PASS, 24 tests.
- `make task057-test`: PASS, 104 tests.
- `make task058-test`: PASS, 109 tests.
- `make task059-test`: PASS, 121 tests.
- `make task060-test`: PASS, 133 tests.
- `make task061-test`: PASS, 5 tests.
- Relevant acquisition, engine, discovery, repository, selector, replay, and API suites: PASS.
- Lint, formatting, type checking, import, documentation, baseline, and build checks: PASS.
- Full `make validate`: PASS.

The review-package generator reruns and retains the complete output of the required validation
commands from the final committed branch head.

## Assumptions and Limitations

- TASK-062 corrects duplicate equivalence; it does not reduce repeated graph traversal or network
  cost across seed trials.
- Existing duplicate-outcome audit persistence remains unchanged.
- The identity allowlist must be extended deliberately when future adapters introduce new metadata
  that affects identity, validation, selection, persistence, or checkpoints.
- Existing Amazon checkpoint and learned-state inconsistencies are not repaired or reinterpreted.
- IBM and Western Digital evidence is represented by captured deterministic topology shapes; no
  live repository mutation is part of validation.
- The Pull Sources diagnostic presentation remains unchanged. Compact operator presentation is a
  separate milestone.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Limitations / next milestone |
|---|---|---|---|
| Candidate identity | Stable allowlisted duplicate-conflict semantics | Complete | Future behavior-affecting adapter metadata requires deliberate allowlist extension |
| Discovery occurrence | Trial-local path, rank, seed, alias, and timestamp attribution | Complete | Diagnostic presentation remains the existing Pull result surface |
| Global run deduplication | Process one stable candidate and classify later occurrences | Complete | Does not eliminate repeated discovery graph fetches |
| Candidate conflict protection | Fail closed on stable identity disagreement | Complete | No automated repository-state repair |
| Selector and persistence behavior | Existing latest/range selection and durable lifecycle | Complete and unchanged | Historical backfill remains out of scope |
| Transcript traversal efficiency | Avoid repeated graph work across learned seeds | Usable with limitations | Recommended next milestone |

The recommended next architectural milestone is to simplify transcript trial execution so a
validated learned artifact can terminate without expanding the full archive graph and so aggregate
run-level resource bounds constrain repeated seed traversal.
