# RFI-1 Task Roadmap

> The unit of work is an architectural milestone, not an implementation milestone.
>
> Each milestone receives its own detailed task ticket before implementation. The task ticket remains authoritative.

| Task | Architectural Milestone | Status |
|---|---|---|
| TASK-001 | Repository foundation and authoritative design baseline | Complete |
| TASK-002 | Immutable acquisition substrate and repository-owned evidence contracts | Complete |
| TASK-003 | Deterministic acquisition engine and provider adapter boundary | Complete |
| TASK-004 | First live production acquisition and provider-independent SEC evidence corpus | Live acceptance complete; final review and merge pending |
| TASK-005 | Canonical knowledge construction from immutable evidence | Complete |
| TASK-006 | Knowledge retrieval, evidence assembly, and source-object browser | Contracts complete; retrieval quality provisional |
| TASK-007 | Model-guided intelligence with explicit provenance and retrieval traces | Planned |
| TASK-008 | Consulting workspace, operational hardening, and POC assessment | Provisional |
| TASK-009 | Extensible business concept catalog and local admin console | Complete |
| TASK-010 | Admin-console usability and schema-aware concept editor | Complete |
| TASK-011 | Target firm catalog, browser, and admin editor | Complete |
| TASK-012 | Stable application CLI and operator help | Complete |
| TASK-013 | External target-firm catalog import | Complete |
| TASK-014 | Firm source profiles and canonical acquisition template | Complete |
| TASK-015 | Pull Workflow shared by GUI, CLI, and REST API | Complete |

## Architectural Progression

```text
Acquisition
    ↓
Immutable Evidence
    ↓
Canonical Knowledge
    ↓
Knowledge Retrieval and Inspection
    ↓
Model-Guided Intelligence
    ↓
Consulting Workflows
```

## Planned Milestones

### TASK-005 — Canonical Knowledge Construction

Transform immutable source evidence into versioned, provenance-rich knowledge objects.

Expected concerns:

- source structure, sections, spans, and stable source locations;
- canonical entities, periods, events, measurements, and factual observations;
- temporal validity, correction, and supersession;
- provenance from every knowledge object back to exact source evidence;
- deterministic rebuild of derived knowledge state.

### TASK-006 — Knowledge Retrieval and Source-Object Browser

Make the knowledge repository precisely accessible to machines and fully inspectable by the operator.

Expected concerns:

- vector retrieval combined with metadata filtering;
- entity, temporal, document-type, and provenance constraints;
- structured retrieval plans and iterative coverage checks;
- provenance-complete evidence packets;
- source-context expansion, deduplication, and truncation reporting;
- console browsing of sources, documents, artifacts, knowledge objects, and derivation paths;
- one retrieval and inspection model shared by human and model-facing interfaces.

### TASK-007 — Model-Guided Intelligence

Allow frontier models to consume governed evidence packets and produce derived intelligence with explicit lineage and uncertainty.

Expected concerns:

- free-form question interpretation;
- structured and iterative retrieval orchestration;
- comparisons, trends, claims, and hypotheses;
- contradictory or incomplete evidence;
- citations, provenance, and reproducible retrieval traces;
- replaceable reasoning models;
- later evaluation of a focused smaller retrieval-planning model.

### TASK-008 — Consulting Workspace and Operational Hardening

Turn the evidence, knowledge, retrieval, and intelligence layers into a durable consulting instrument.

Potential concerns:

- saved investigations and company/topic workspaces;
- comparison, timeline, and call-preparation workflows;
- operator review and correction;
- backup, restore, diagnostics, scheduling, and performance;
- retrieval and model cost tracking;
- final POC assessment and next-phase planning.

TASK-008 remains provisional and should be refined from TASK-005 through TASK-007 evidence.

## Governing Principles

- Architectural boundaries, invariants, acceptance criteria, and evidence define each task.
- Implementation prompts should remain small.
- Immutable evidence must remain distinct from knowledge and derived intelligence.
- Rapidly evolving components should depend on slowly evolving components, not the reverse.
- Frontier models should consume governed evidence through repository-owned retrieval contracts.
- Vector similarity is a candidate-generation mechanism, not the complete retrieval architecture.
- Whatever a model can retrieve must also be inspectable by the operator.
- Real-system behavior should test architectural assumptions.
- Honest blocking is preferable to fabricated completion.
- Every completed task must leave the repository usable, reviewable, and independently auditable.
