# Candidate-pool coverage analysis

## Summary

The pool contains 66 candidates backed by 35 compact synthetic fixtures:

| Slice | Supported | Defective | Indeterminate | Total |
|---|---:|---:|---:|---:|
| Objective core | 31 | 25 | 6 | 62 |
| Borderline quarantine | 0 | 2 | 2 | 4 |
| Entire candidate pool | 31 | 27 | 8 | 66 |

The objective core is organized as 31 matched pairs. Each pair fixes the question, explicit answer
requirements, evidence, and authority while changing the submitted investigator answer. Every pair
contains one supported control and one defective or indeterminate submission. The supported member
is not always the second case (see RFIQA-053/RFIQA-054), which avoids making identifier parity a
perfect label shortcut.

Difficulty is deliberately front-loaded toward trustworthy adjudication:

| Difficulty | Cases | Purpose |
|---|---:|---|
| `atomic` | 22 | Direct field, statement, status, unit, or simple calculation checks. |
| `cross_evidence` | 28 | Boundaries, identity joins, filtering, deduplication, provenance, and synthesis. |
| `evidence_limits` | 12 | Missing identity/date, partial coverage, ambiguous reference, and causal insufficiency. |
| `judgment_dependent` | 4 | Quarantined materiality or undefined-language candidates. |

Across case executions, 54 use complete fixtures, eight use fixtures complete only for an explicit
dimension, and four use partial fixtures. The partial and dimension-complete cases are concentrated
where evidence limitations are the behavior under test rather than being sprinkled into otherwise
deterministic arithmetic cases.

## QA capabilities exercised

| QA capability | Representative candidates | Reference behavior |
|---|---|---|
| Exact numeric and date fidelity | RFIQA-001–004, 025–028 | Detect transposition, percentage, unit, and boundary errors; pass exact controls. |
| Claim-to-evidence mapping | RFIQA-005–006, 021–022 | Reject a non-supporting locator and an explicitly required missing locator without rejecting the correctly mapped mate. |
| Attribution and ambiguous identity | RFIQA-007–008, 045–046 | Preserve unnamed speakers and unresolved pronouns instead of choosing a plausible identity. |
| Qualifications and causal limits | RFIQA-009–010, 019–020, 023–024 | Carry population/window caveats; distinguish possibility and association from proof or cause. |
| Whole-answer reconciliation | RFIQA-011–012, 039–040, 043–044 | Detect internal inconsistency, omitted dissent, and meaning reversed by lost negation. |
| Earliest/latest reasoning | RFIQA-003–004, 013–014, 051–052 | Evaluate complete sets and use event chronology rather than ingestion chronology. |
| Presence and absence semantics | RFIQA-015–016, 047–048, 053–054 | Separate overlooked matching evidence, bounded zero results, and sound negative findings over a complete register. |
| Corpus authority and completeness | RFIQA-017–018, 047–050 | Refuse completeness, universal absence, or imputed dates when the authority does not permit them. |
| Identity, versions, and source authority | RFIQA-029–034, 055–056 | Deduplicate revisions, follow legal identity, apply supersession, and prefer the governing audited source. |
| Scope and record eligibility | RFIQA-035–042, 059–060 | Enforce calendar scope, completion/finality, eligibility filters, denominator rules, and inclusive boundaries. |
| Time normalization | RFIQA-057–058 | Convert an authoritative UTC timestamp to the requested site-local date. |
| Cross-record aggregation | RFIQA-029–030, 035–036, 041–042, 061–062 | Count governed identities, filter before totaling, and sum complete mutually exclusive rows. |
| False-positive restraint | All 31 supported controls | Preserve correct facts, valid negative claims, careful uncertainty, qualifications, and stable mappings. |

The 35 non-supported cases exercise 36 material findings across 32 defect classes; the objective
core contributes 31 of those cases, 32 findings, and 31 classes. Most defect classes occur once
because the pool favors distinct reasoning over cosmetic variants. `chronology_boundary_incorrect`,
`qualification_omitted`, and `provenance_authority_error` recur where the second context changes the
reasoning materially. The four quarantined cases account for both uses of
`undefined_evaluation_criterion` and one of the qualification/provenance recurrences.

## Defect-taxonomy coverage

The objective core covers:

- source fidelity: numeric mismatch, denominator, unit, and aggregation errors;
- chronology: wrong boundaries, wrong date basis, imputed dates, time-zone conversion, interval
  endpoints, and temporal scope;
- evidence governance: wrong/missing mapping, identity conflation, duplicate identity, source
  authority, explicit supersession, status, and eligibility;
- epistemic calibration: unsupported attribution, ambiguous referent, partial-corpus completeness,
  bounded-search absence, causal insufficiency, claim-strength overstatement, and source
  qualifications; and
- synthesis integrity: internal inconsistency, omitted contrary evidence, false absence, quotation
  distortion, and a directly contradicted unsupported claim.

This breadth is enough to discard several candidates during independent selection without losing
entire capability families. It is not a recommendation that all 66 cases be retained, nor is it a
proposed final size.

## Why the pool is reasonably broad without being inflated

The 31 pairs are repetitions only in the intentional control sense: each pair keeps the evidence
fixed so false-positive behavior can be measured. Across pairs, the reasoning operation changes
(for example, stable-identity joining is not a renamed numeric mismatch, and a partial-index absence
claim is not a renamed complete-register absence claim). The collection avoids multiplying cases by
swapping names or perturbing values while leaving the adjudication logic unchanged.

Cases remain compact enough that a knowledgeable human can reconstruct the reference result from
the listed adjudication evidence. The four cases where that claim is weakest are explicitly outside
the objective core.

## Repeatability use

The same candidate can be executed multiple times with fresh QA contexts. The stable case ID,
fixture authority, exact evidence locators, expected disposition, defect class, affected claim, and
reference rationale permit run-to-run comparison without exposing an answer key to the reviewer.
The pool deliberately does not define a success threshold, a semantic finding-matching algorithm,
or a calibration/validation partition.

## Important behaviors still difficult to test objectively

The following remain important but resist low-disagreement synthetic reference truth:

- whether a long narrative omitted a fact material enough to change a decision;
- how exhaustive an open-ended counterevidence search must be before stopping;
- corpus completeness when real acquisition coverage is only probabilistic or operationally
  observed rather than declared by a fixture;
- authority conflicts where two sources have different mandates but neither explicitly supersedes
  the other;
- causal synthesis across heterogeneous observational sources with defensible competing models;
- whether a citation is sufficiently granular when it supports a paragraph only in combination
  with unstated background evidence;
- severity calibration and whether several individually minor errors become material in aggregate;
- domain-language boundaries such as “substantial,” “near term,” “material,” “likely,” or
  “effective” without an externally governed definition;
- factual equivalence of paraphrases, especially indirect speech, sarcasm, or technical shorthand;
- answer completeness for broad “what happened and why” questions where no exhaustive claim list
  can be specified without turning the benchmark into an answer-key match; and
- retrieval failures in a live repository, where failure to surface existing evidence must be
  distinguished from correct QA reasoning over the evidence actually made available.

The quarantined candidates illustrate three of these boundaries. Future candidate authoring should
prefer adding a governed threshold, explicit source hierarchy, enumerated claim obligation, or
declared evidence scope rather than silently resolving the ambiguity in the reference answer.
