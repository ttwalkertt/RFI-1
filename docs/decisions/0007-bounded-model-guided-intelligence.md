# ADR-0007: Bounded model-guided intelligence over evidence packages

- Status: accepted
- Scope: TASK-007

## Context

TASK-006 established provider-independent retrieval queries and provenance-complete evidence
packages. A reasoning layer must interpret information needs, iterate when coverage is missing, and
produce useful synthesis without learning storage layouts, promoting model prose to evidence, or
hiding unsupported claims and autonomous behavior.

## Decision

Create `rfi.intelligence` as a downstream non-authoritative subsystem. Give it replaceable
`Planner`, `EvidenceGateway`, and `Reasoner` ports. Permit only the evidence gateway to execute
governed TASK-006 queries and consume packages. Keep the public plan, claim, result, trace, budget,
and runtime-policy contracts provider-neutral.

Project each package into a bounded `ModelEvidence` value that preserves separate source and
derived items plus exact contexts and package limitations. Require every claim to declare source,
derived, or inference authority, resolve to consumed evidence IDs, explain its support, and carry
confidence. Require inferences to state uncertainty. Preserve contradictions, ambiguity, missing
evidence, incomplete status, and explicit stopping reasons.

Let the orchestrator, not a model provider, own budgets, package validation, follow-up admission,
claim validation, completion status downgrade, and execution tracing. Fail closed for invalid
plans, mismatched or provenance-incomplete packages, model failure, and invalid mappings. Provide
deterministic planner/reasoner implementations and wording variants through the same contracts for
offline and replacement proof.

Default retention to metadata-only, keep credentials external, cap disclosed model input, and make
full retention an explicit operator choice. Do not add open-ended tools or saved investigation
state.

## Consequences and tradeoffs

The intelligence layer can change providers, prompts, or orchestration strategies without changing
upstream authorities or public result semantics. Full traces and repeated evidence identities cost
space but make the execution auditable. Hard bounds and whole-package validation favor trustworthy
incompleteness over fluent completion.

Mechanical validation proves mapping completeness and authority consistency, not general semantic
entailment. The deterministic substitute provides reproducibility and broad failure coverage but
weak language interpretation and no model-quality claim. A future provider adapter must add
structured-output parsing, disclosure policy, invocation telemetry, and semantic evaluation behind
the established ports.

## Alternatives considered

- Direct model access to source, knowledge, or retrieval storage was rejected because it bypasses
  TASK-006 governance and couples rapidly changing reasoning to private persistence.
- A single free-form answer plus citations was rejected because it cannot preserve claim-level
  authority, inference, contradiction, and missing-evidence semantics.
- Letting the model choose arbitrary tools or termination was rejected because actions and bounds
  would be hidden and difficult to reproduce.
- Persisting model outputs as repository knowledge was rejected because output is neither source
  evidence nor validated canonical interpretation.
- Requiring identical replacement prose was rejected because wording is implementation-owned;
  status, authority, provenance, and mapping obligations are repository-owned.

## Proof limits

The proofs establish bounded multi-step orchestration, real SEC corpus consumption, claim mappings,
inference labels, insufficiency, ambiguity, provider-neutral replacement, operator inspection,
retention, and failure behavior. They do not establish frontier-model accuracy, general semantic
entailment, broad financial extraction, prompt-injection resistance for live providers, cost or
latency fitness, production routing, or consulting-workflow maturity.
