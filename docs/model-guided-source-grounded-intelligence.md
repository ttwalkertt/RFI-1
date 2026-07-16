# Model-guided retrieval planning and source-grounded intelligence

TASK-007 adds a downstream reasoning subsystem that turns an information need into bounded TASK-006
retrieval activity and a provider-neutral intelligence result. It is an orchestration and control
layer, not a new evidence authority. Its deterministic implementations prove the contracts offline;
they do not establish frontier-model answer quality.

## Boundary and dependency direction

```text
InformationNeed
      |
      v
Planner -> RetrievalPlan -> IntelligenceOrchestrator -> EvidenceGateway
                                                   |            |
                                                   |            v
                                                   |    TASK-006 EvidencePackage
                                                   v
                                             ModelEvidence -> Reasoner
                                                   |              |
                                                   +------> draft + grounding validation
                                                                  |
                                                                  v
                                                        IntelligenceResult + ExecutionTrace
```

`rfi.intelligence` imports only public TASK-006 contracts. `PackageGateway` is constructed from a
public retrieval callable and public evidence-assembly callable; no intelligence module imports or
opens source, knowledge, acquisition, retrieval-index, or artifact storage. Upstream packages do
not import intelligence. Evidence packages remain query projections, model output remains
non-authoritative, and the intelligence result is derived analysis.

## Public contracts and authority separation

`InformationNeed`, `IntelligenceBudget`, `RetrievalStep`, and `RetrievalPlan` define planning.
`ModelEvidence` is the bounded model-facing projection of consumed packages. Every
`IntelligenceClaim` declares exactly one of:

- `source-evidence`: an exact source-object assertion;
- `derived-knowledge`: a repository interpretation, with its status and provenance retained; or
- `model-inference`: synthesis by the reasoner, with mandatory uncertainty.

Every claim has one or more `evidence_ids` and a support explanation. Each ID resolves to an
`EvidenceReference` carrying the package, authority class, object, document, and source-object
identities. The orchestrator rejects missing, unconsumed, or cross-authority mappings. The public
`IntelligenceResult` contains no provider, prompt, model, token, or storage fields.

`ExecutionTrace` retains the original need, structured plan, ordered events, every query and
package identity, bounded model input, raw draft, iterations, failures, and stop reason. The
operator therefore sees planning, retrieval, evidence consumption, follow-up decisions, model
exchange, grounding validation, and termination through one JSON-inspectable record.

## Bounded orchestration and stopping

`IntelligenceBudget` limits iterations, package count, total verified evidence bytes, and model
input characters. Each retrieval query separately retains TASK-006 candidate, result, context, and
evidence-byte limits. A step states required result classes and optional evidence terms. Missing
requirements, omissions, or coverage gaps may cause one planner-supplied follow-up. Follow-ups are
ordinary visible retrieval steps and cannot exceed the same budgets.

Stopping reasons are `requirements-satisfied`, `evidence-insufficient`, `iteration-limit`,
`evidence-budget`, `refused`, or `failure`. Incomplete evidence cannot yield a complete status.
Unsafe requests that ask to bypass governance are refused before retrieval. No tool other than the
configured evidence gateway is available and no hidden autonomous action exists.

## Validation and failure semantics

Planner output fails closed if malformed, duplicated, unbounded, budget-changing, or based on an
unsupported retrieval constraint. Retrieval failure is retained and produces an incomplete result
when no safe evidence is available. A package is rejected if its query differs, its identity or
budget is invalid, its retrieval trace reports failures, or any source/derived provenance lacks a
verified TASK-006 context.

Reasoner invocation failure and empty, duplicate, unmapped, unconsumed, cross-authority, or
unlabeled-inference claims produce a failed result. Context truncation, package omissions, missing
terms, uncertain knowledge, and contradictions produce an incomplete result. Semantic entailment
cannot be proved mechanically for an arbitrary model; provider adapters remain responsible for
constrained generation, while the repository validator enforces explicit authority, mapping, and
support obligations. Human evaluation of semantic claim quality is deferred.

## Runtime configuration, disclosure, and retention

`RuntimePolicy` names planner/reasoner selections, retention mode, sensitive-content permission,
and credential environment-variable names. It stores names, never credential values. Provider
adapters are expected to read credentials from the process environment or an external secret
manager. No credential is accepted in a plan, result, trace, or repository configuration.

Model disclosure is limited to selected public package objects and already bounded exact contexts.
The projection is capped by `max_model_input_chars`; truncation forces an incomplete result. A
production adapter should default `sensitive_content_allowed=false` and apply a source policy
before invocation.

Retention is explicit:

- `none` writes nothing;
- `metadata` stores identities, status, stop reason, package/trace/claim IDs, iteration count, and
  failures without need text, evidence content, or model exchange;
- `full` stores the complete record only when deliberately selected.

The default is metadata. The POC does not automatically persist execution records. Review proof
artifacts deliberately retain full checked-fixture and bounded SEC runs for milestone audit.

## Offline and real-corpus proof

Run the complete checked-fixture proof:

```sh
make task007-proof
```

Run the bounded accepted TASK-004 corpus proof:

```sh
.venv/bin/python scripts/task007_operator.py real-proof \
  --acquisition-state .artifacts/runtime/TASK-004-edgar \
  --state .artifacts/runtime/TASK-007
```

Both outputs include the plan, requests, complete consumed packages, model-facing projection, raw
draft, result mappings, events, iterations, and stopping reason. The real question compares
Seagate and Western Digital annual-filing coverage across separate governed packages. The proof
also runs revenue insufficiency, conflict/ambiguity, implementation replacement, refusal,
retrieval-failure, and unsupported-claim scenarios.

## Limits

The deterministic planner recognizes a bounded SEC issuer vocabulary and simple evidence needs;
it is a model substitute, not natural-language planning-quality evidence. The reasoner synthesizes
the narrow TASK-005 issuer and filing ontology and does not analyze filing bodies, financial
measures, tables, XBRL, or business performance. Claim validation proves complete mappings and
authority consistency, not general semantic entailment. There is no live provider adapter, prompt
registry, cost router, long-lived investigation, operator correction workflow, or consulting UI.

## Architectural Status Summary

- **Repository foundation — Complete.** Task governance, validation, and review packaging remain
  active.
- **Acquisition substrate — Complete.** Immutable artifacts and append-only history remain the
  evidence authority.
- **Acquisition engine — Complete.** Provider orchestration remains replayable and independent.
- **Live SEC providers — Usable with Limitations.** The accepted native EDGAR corpus exists;
  continuous scheduling does not.
- **Immutable evidence — Complete.** Exact bytes and identities anchor every consumed context.
- **Source-object subsystem — Usable with Limitations.** SEC SGML structure is stable; semantic
  body sections, tables, XBRL, PDFs, and broader formats remain absent.
- **Derived-knowledge subsystem — Usable with Limitations.** Independent versioning, status, and
  provenance are complete; the ontology is narrow.
- **Retrieval and evidence assembly — Complete contracts; provisional quality.** Governed queries,
  packages, traces, budgets, and fail-closed provenance are established; learned recall and ranking
  quality are not.
- **Source/knowledge inspection — Complete.** Operators can inspect upstream authority and the
  exact packages exposed downstream.
- **Model-guided retrieval planning — Complete contracts; provisional quality.** Structured plans,
  bounded follow-up, refusal, budgets, replaceable planners, and full traces are established. The
  deterministic planner does not prove frontier-model planning quality.
- **Source-grounded intelligence — Complete contracts; usable with limitations.** Claim mappings,
  authority separation, inference/uncertainty, contradictions, gaps, replaceable reasoners, and
  fail-closed output validation are established. Answer quality and semantic entailment evaluation
  remain immature.
- **Consulting workspace — Not Started.** Saved investigations, review/correction, and consulting
  projections remain TASK-008.

TASK-007 introduces a fifth architectural layer: governed intelligence execution. It consumes
retrieval projections and produces non-authoritative, inspectable analysis. The next milestone is
TASK-008 consulting workflow and operational hardening, informed by explicit planning and answer
quality evaluation rather than contract work alone.
