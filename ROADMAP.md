# RFI-1 roadmap

This roadmap describes intended engineering direction from the implemented repository. It is not a
task plan or authorization. `TASKS.md` and an applicable ticket authorize work; `BACKLOG.md`
records unscheduled candidates. Repository evidence, not the historical phase model or design
study, determines the starting point.

## Current baseline

RFI-1 already contains more than an acquisition POC:

- a product-integrated local evidence acquisition and inspection application;
- governed configuration, immutable evidence, artifact streams, feeds, SEC and transcript
  retrieval, mailing-list workflows, and operational maintenance;
- implemented POCs for structural source objects, derived knowledge, governed retrieval,
  grounded intelligence, and durable consulting workspaces.

The main gap is that the downstream POCs are not composed with the operating product. See
[`docs/current-state.md`](docs/current-state.md) for the capability matrix and evidence.

## Engineering frontier

The following frontiers are ordered by dependency, not committed delivery date. Each requires a
new or refined ticket before implementation.

### 1. Compose evidence into governed research workflows

Define how product-retained artifacts enter source-object parsing, knowledge construction,
retrieval-index rebuild/freshness, bounded intelligence execution, and workspace retention.

The milestone should establish:

- explicit triggers and lifecycle for build, rebuild, failure, retry, and staleness;
- one product composition root over existing public contracts;
- operator-visible inspection from artifact through evidence package and conclusion;
- preservation of independent evidence, derived, intelligence, and annotation authorities; and
- truthful partial operation when an artifact or derived layer is unsupported.

This is composition work, not permission to collapse the layers or rewrite established POCs into
one repository abstraction.

### 2. Evaluate and broaden knowledge/retrieval quality

The existing source-object parser and derived ontology principally cover SEC submission/header
facts. Retrieval uses bounded deterministic local vectorizers, and intelligence uses deterministic
planner/reasoner substitutes.

Operating evidence should decide which semantic expansion matters first. Candidate concerns are:

- filing body sections, tables, XBRL, PDFs, transcripts, feeds, and email semantics;
- measurable retrieval recall/ranking quality under metadata and provenance constraints;
- a governed replaceable frontier-model planner/reasoner adapter;
- semantic-grounding evaluation beyond structural evidence-ID validation; and
- cost, disclosure, retention, correction, and operator-review policies.

Do not equate adding an embedding or model API with completing this frontier.

### 3. Establish usable consulting product composition

The workspace journal already proves append-only investigations, execution capture, comparison,
notes, exports, backup, and restore through a public executor port. It remains a proof-script
workflow.

A product milestone should be driven by real operator work and decide:

- investigation and question entry in the stable application;
- evidence/result inspection and correction workflow;
- rerun, comparison, export, and incomplete-evidence experience;
- workspace-to-repository availability and retention behavior; and
- which client deliverables are genuine product projections.

### 4. Resolve source-specific acquisition gaps

The most concrete blocked gap is official press releases. The WDC Business Wire adapter is
implemented and registered but direct production transport is not viable from the tested
environment. A future task must choose and validate an authorized issuer archive, licensed
full-text source, or explicit deferral. Registration and browser-capture replay are not acceptance.

Other source expansion should remain artifact-specific and evidence-driven. Current backlog items
cover exact-accession and older SEC filing retrieval. Broad crawling is not the default next step.

### 5. Harden operations when usage proves the need

The product is local, foreground, and primarily single-writer. Operational candidates include:

- external or internal recurrence with recoverable coordination;
- authentication and remote/multi-user threat boundaries;
- redirect-aware network policy and credentialed source policy;
- monitoring, repository health, retention, and cost instrumentation;
- multi-process or multi-host writer coordination; and
- scale/performance evidence and any server-database decision.

Select mechanisms only after a workload or deployment target supplies requirements. SQLite and
local operation remain correct until evidence establishes otherwise.

## Completed architectural foundation

The following progression is implemented, though not all layers are product-composed:

```text
Acquisition and immutable evidence                 product-integrated
    -> structural source objects                   implemented POC
    -> versioned derived knowledge                 implemented POC
    -> governed retrieval/evidence packages        implemented POC
    -> grounded intelligence                       implemented POC
    -> consulting workspace                        implemented POC
```

Parallel product-integrated capabilities include concepts/firms/source profiles, Pull Workflow,
artifact inspection, feeds, mailing-list evidence, revisioned streams, backup/restore, and operator
help. Historical task sequencing remains in `TASKS.md` and completed review records; it is not
repeated here as a current roadmap.

## Decision rules

- Prefer composition and evaluated operator value over additional isolated POCs.
- Preserve evidence and authority boundaries while changing implementations.
- Treat source/provider availability and model quality as evidence questions, not documentation
  assumptions.
- Keep architecture, bounded milestone completion, product integration, production readiness, and
  roadmap authorization separate.
- Record newly discovered work in `BACKLOG.md` until explicitly authorized.
- Update `docs/current-state.md` when a completed task changes maturity or product composition.
