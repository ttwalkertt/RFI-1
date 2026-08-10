# TASK-072 — Design Agent-Legible RFI MCP Surface

**Status:** Complete

**Type:** Architecture/design experiment

**Scope:** Read-only MCP surface over existing RFI retained truth and governed knowledge-access capabilities

## Objective

Design, but do not yet implement, an MCP surface that allows a capable general-purpose investigative agent such as Codex Work to discover, query, inspect, and retrieve RFI retained truth without depending on RFI persistence internals or on the custom TASK-071 investigative harness.

The design shall test the architectural hypothesis that RFI can own the epistemic substrate—retained truth, canonical identity, provenance, exact evidence, repository semantics, data dictionary, indices/query semantics, and governed IQA-style access—while a general-purpose agent runtime owns planning, iterative investigation, context management, tool orchestration, stopping behavior, synthesis, and report construction.

The MCP surface must be designed as a rich, agent-legible repository interface, not as TASK-071's investigative harness translated into MCP calls.

## Architectural Question

Determine:

> What is the smallest semantically rich MCP surface that exposes RFI's retained knowledge well enough for an unfamiliar capable agent to investigate the corpus proficiently while preserving the boundary between repository/access semantics and investigative behavior?

The task should also identify deficiencies in RFI's existing repository and knowledge-access contracts that become apparent when attempting to expose them cleanly to an external agent.

## Required Starting Point

Inspect the current implementation rather than designing from TASK-071 documentation alone.

Treat as architectural inputs:

- RFI retained-truth and artifact models;
- canonical identity and repository authority;
- immutable retained content;
- provenance and observation semantics;
- transcript classification and temporal semantics;
- repository-owned artifact query contracts;
- the retained-truth catalog produced by TASK-071;
- existing IQA/query/index/view capabilities;
- TASK-071's model-facing data dictionary and capability surface;
- exact-evidence retrieval paths;
- representative TASK-071 investigative traces;
- current failure and insufficiency semantics.

Identify which existing public contracts can be exposed substantially unchanged, which require an MCP adapter, and which reveal missing repository-level capabilities.

Do not assume that TASK-071's access surface is the correct MCP surface.

## Governing Boundary

Preserve this conceptual split:

```text
RFI
    retained truth
    canonical identity
    integrity
    provenance
    authoritative metadata
    deterministic derived metadata
    repository relationships
    data dictionary
    indices / views / query semantics
    governed knowledge access
    exact evidence retrieval
            |
            | MCP boundary
            v
General-purpose investigative runtime
    question interpretation
    planning
    investigation strategy
    iterative tool use
    hypothesis formation
    counterevidence search
    context management
    stopping decisions
    synthesis
    report construction
```

The MCP design shall strengthen this boundary rather than blur it.

## Design Principles

### 1. Semantic rather than physical

Expose RFI concepts and repository semantics.

Do not require an agent to understand:

- SQLite tables;
- SQL joins;
- content-store filesystem paths;
- internal event/replay representation;
- provider-specific implementation details;
- acquisition implementation structure.

A generic SQL interface is not an adequate substitute for repository semantics.

### 2. Rich but procedurally weak

The MCP shall make retained knowledge easy to discover and manipulate without prescribing how an investigation proceeds.

Good MCP capabilities answer questions such as:

- What retained evidence exists?
- What does this object mean?
- What are its authoritative identity and metadata?
- What relationships does it have?
- What evidence matches these governed query criteria?
- What exact retained content supports this result?
- Where did this evidence come from?
- What query or access capabilities are available?

The MCP shall not answer procedural questions such as:

- What should I investigate next?
- Have I gathered enough evidence?
- Which hypothesis should I pursue?
- What evidence should I cite?
- What conclusion should I reach?
- Is my report complete?

Those belong to the investigative runtime.

### 3. Agent-legible discovery

Assume the consumer is capable but initially unfamiliar with RFI.

Names, descriptions, schemas, result contracts, error semantics, data dictionaries, and resource organization must allow the agent to discover:

- what RFI contains;
- what operations are available;
- what returned fields mean;
- which fields are authoritative;
- which information is derived;
- how canonical identity works;
- how provenance can be inspected;
- how exact evidence can be retrieved;
- what insufficiency or unavailable evidence means.

Avoid relying on a large RFI-specific system prompt to compensate for an opaque MCP interface.

### 4. Preserve epistemic authority

MCP must not create a second source of truth.

Retained artifact identity, content, integrity, provenance, observation history, canonical classification, and repository authority remain owned by existing RFI contracts.

Derived access structures remain replaceable.

Generated analytical conclusions must not become retained repository truth through this task.

## Required MCP Surface Design

Evaluate and propose appropriate use of:

- MCP resources;
- MCP resource templates;
- MCP tools;
- MCP prompts, including whether RFI should expose none.

For every proposed MCP element specify at least:

1. name;
2. MCP primitive;
3. purpose;
4. intended agent use;
5. input schema or URI structure;
6. output/result contract;
7. authoritative versus derived fields;
8. underlying RFI contract or capability;
9. failure and insufficiency semantics;
10. pagination/bounding behavior where applicable;
11. provenance/evidence traceability;
12. why the capability belongs in RFI rather than the investigative runtime.

Prefer orthogonal composable capabilities over large convenience operations.

## Explicit Anti-Goals

Do not encode TASK-071's investigative harness into MCP.

In particular, do not introduce capabilities whose semantics amount to:

- `investigate_question`;
- `analyze_sentiment`;
- `find_supporting_quotes`;
- `find_counterevidence`;
- `evaluate_hypothesis`;
- `choose_next_step`;
- `build_evidence_package_for_answer`;
- `decide_if_sufficient`;
- `synthesize_answer`;
- `generate_report`.

Do not expose TASK-071 planner state, investigation state, hypothesis state, stopping criteria, token/context policy, evidence-selection heuristics, or model-specific prompt strategy.

Question-specific convenience tools are prohibited unless the design can demonstrate that the operation is actually a stable repository semantic independent of the proving investigation.

## Resource-versus-Tool Analysis

Explicitly analyze which RFI concepts are naturally:

- addressable resources;
- parameterized resource templates;
- callable tools;
- discoverable descriptive/schema resources;
- inappropriate for MCP exposure.

Do not mechanically turn every existing Python/service method into an MCP tool.

The proposed surface should reflect the repository's conceptual model rather than its current code decomposition.

## Data Dictionary and Capability Discovery

Design how an unfamiliar agent learns RFI semantics.

Cover at least:

- retained object types;
- canonical identity;
- artifact versus document identity where applicable;
- authoritative metadata;
- deterministic derived metadata;
- provenance;
- temporal semantics;
- transcript classification;
- relationships;
- query/index semantics;
- exact-content/evidence access;
- result completeness and insufficiency;
- available filters and ordering;
- bounded result behavior.

Determine which of this information belongs in tool descriptions, result schemas, resources, resource templates, or another MCP-supported discovery mechanism.

## Failure and Insufficiency Semantics

Design failures so that diagnostic attribution remains possible.

The agent must be able to distinguish, where applicable:

- invalid request;
- unknown object;
- no matching retained evidence;
- unsupported query;
- unavailable derived index;
- incomplete or indeterminate coverage;
- exact evidence unavailable;
- integrity failure;
- provenance unavailable or malformed;
- result truncated by a named bound;
- repository read failure;
- successful empty result.

Do not collapse repository/access failure into an apparent absence of evidence.

## Seagate Validation Case

Use the same retained Seagate earnings-call transcript corpus and substantive quality questions used to evaluate TASK-071.

This is a design validation case, not the source of the design.

Walk through how an unfamiliar capable agent could use only the proposed MCP surface to:

1. discover the available Seagate transcript corpus;
2. understand relevant corpus and metadata semantics;
3. identify potentially relevant evidence;
4. progressively inspect and expand that evidence;
5. retrieve exact retained passages;
6. inspect provenance and canonical identity;
7. search for contradictory or qualifying evidence;
8. recognize when the retained corpus is insufficient to answer a question;
9. construct its own evidence-supported conclusion.

The walkthrough must identify which decisions are made by RFI/MCP and which remain decisions of the investigative runtime.

Do not introduce an MCP capability merely because it makes this walkthrough shorter.

## Diagnostic Attribution Analysis

Demonstrate that the proposed boundary permits failures to be attributed meaningfully.

At minimum analyze these cases:

### Repository/MCP failure

Relevant retained evidence exists, but the MCP cannot expose or retrieve it correctly or makes its semantics materially opaque.

### Investigative-runtime failure

The MCP exposes appropriate evidence and semantics, but the agent fails to discover it, ignores relevant evidence, stops prematurely, or reasons poorly from it.

### Repository-authority failure

The agent uses the MCP correctly, but canonical identity, provenance, retained metadata, or exact evidence supplied by RFI is incorrect or ambiguous.

### Synthesis failure

Evidence discovery and retrieval are adequate, but the resulting conclusion is unsupported, overstated, or poorly constructed.

The design should preserve enough observable information to distinguish these failure classes during the later experiment.

## Gap Analysis

Produce an explicit gap analysis between the proposed MCP surface and current RFI capabilities.

Classify each proposed capability as:

- directly reusable existing contract;
- thin MCP adaptation required;
- existing capability requiring semantic cleanup;
- missing repository/IQA capability;
- intentionally deferred.

Pay particular attention to places where TASK-071 may currently compensate for weak or missing repository semantics.

Do not implement those gaps in this task.

## Minimal Implementation Recommendation

Conclude with a proposed first MCP implementation slice.

It should be sufficient to run a meaningful Codex Work experiment over the retained Seagate transcript corpus while remaining small enough that poor results can be diagnosed before broadening the surface.

Recommend:

- the minimum resources/resource templates;
- the minimum tools;
- any required data-dictionary exposure;
- transport/deployment assumptions;
- required instrumentation;
- required tests;
- capabilities explicitly deferred.

Do not optimize primarily for minimizing MCP call count.

Optimize for:

1. semantic clarity;
2. evidence integrity;
3. agent discoverability;
4. composability;
5. diagnostic attribution;
6. implementation economy.

## Required Deliverables

Produce:

1. `docs/rfi_mcp_surface_design.md` — primary design document;
2. current-state RFI capability inventory relevant to MCP;
3. proposed MCP resource/resource-template catalog;
4. proposed MCP tool catalog with schemas and semantics;
5. data-dictionary/discoverability design;
6. failure and insufficiency taxonomy;
7. repository/MCP/investigative-runtime responsibility matrix;
8. Seagate investigation walkthrough;
9. diagnostic-attribution analysis;
10. current-capability gap analysis;
11. rejected alternatives and anti-patterns;
12. minimal first implementation recommendation;
13. unresolved questions and risks;
14. recommendation for the next bounded implementation/experiment task.

Update durable architecture documentation only if this design establishes a sufficiently mature architectural decision.

## Out of Scope

Do not:

- implement an MCP server;
- add an MCP dependency;
- modify TASK-071's harness;
- replace or remove TASK-071 functionality;
- modify retained artifact or repository authority;
- change acquisition behavior;
- add new transcript providers;
- add internet research;
- add persistent investigative state;
- add report-generation functionality;
- add generated analytical claims to retained truth;
- design a general consulting workspace;
- design multi-user authorization;
- optimize for distributed deployment;
- expose arbitrary SQL or raw persistence access merely for convenience;
- redesign RFI around MCP;
- assume Codex Work is the permanent investigative runtime.

## Acceptance Criteria

The task is complete when:

1. the relevant existing RFI read/query/evidence capabilities have been inspected in implementation rather than inferred solely from documentation;
2. a coherent read-only MCP surface has been proposed using appropriate MCP primitives;
3. every proposed capability has a clear repository-semantic justification;
4. the surface exposes retained truth, canonical identity, provenance, exact evidence, data semantics, and governed query/navigation without encoding investigative procedure;
5. an unfamiliar capable agent can plausibly orient itself and investigate the Seagate corpus from the proposed interface;
6. the design supports meaningful attribution of repository/MCP failures versus investigative-runtime and synthesis failures;
7. gaps in current RFI capabilities are explicitly identified rather than hidden behind MCP convenience operations;
8. TASK-071-specific planning, hypothesis, evidence-selection, stopping, and synthesis behavior remain outside the MCP surface;
9. a bounded first implementation slice is recommended;
10. no MCP server or speculative supporting implementation is introduced as part of this task.

## Design Disposition

End the design with an explicit recommendation:

**Proceed with MCP experiment**

or

**Do not proceed with MCP experiment**

or

**Resolve identified RFI access gaps before MCP experiment**

State the reasons, principal risks, required first implementation slice, and what result from the subsequent Codex Work experiment would falsify or weaken the architectural hypothesis.

## Completion Record

TASK-072 completed the design-only milestone without implementing MCP, adding dependencies, or
changing production behavior.

The primary design is [`docs/rfi_mcp_surface_design.md`](../docs/rfi_mcp_surface_design.md). It
contains the repository-grounded capability inventory, resource/resource-template/tool catalog,
data dictionary, result and failure contracts, responsibility matrix, Seagate walkthrough,
diagnostic-attribution analysis, gap classification, rejected alternatives, minimal implementation
slice, risks, falsification criteria, and required Architectural Status Summary.

[`ADR-0028`](../docs/decisions/0028-agent-legible-rfi-mcp-boundary.md) accepts the rich-but-
procedurally-weak boundary for a bounded experiment. [`docs/TASK-072-review.md`](../docs/TASK-072-review.md)
is the human architectural review record.

### Disposition

**Proceed with MCP experiment.** The first implementation slice must add immutable artifact-ID
exact reads, transcript access generation/health/typed outcomes, complete bound/diagnostic
reporting, and a standalone data dictionary. It then exposes only read-only catalog query,
transcript selection, addressable exact resources, and bounded byte reads through local `stdio`.

Planning, investigation strategy, context/tool orchestration, stopping, sufficiency, synthesis, and
report construction remain with Codex Work or another capable runtime. TASK-071 remains evidence
and a comparison case; its harness is not the MCP interface.

### Verification

The commit-aware TASK-072 review package captures documentation checks, baseline verification,
focused current-contract tests, full project validation, documentation-only scope proof, relevant
implementation evidence, Seagate proving records, the complete committed patch, and independently
verified member checksums.

### Next milestone

Authorize TASK-073 to implement and evaluate the minimal local read-only transcript MCP slice over
the five retained Seagate cases. Attribute poor results before adding convenience tools or another
evidence type.
