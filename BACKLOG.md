# RFI-1 Backlog

`BACKLOG.md` is the durable repository record for unscheduled candidates, review observations,
deferred improvements, and future feature ideas.

It is deliberately distinct from the other planning records:

- `BACKLOG.md` records possibilities that are not authorized implementation work and have no
  implied sequence or commitment.
- `ROADMAP.md` records intended direction and sequencing.
- `TASKS.md` records authorized implementation work governed by task tickets.

A backlog entry cannot authorize implementation, override an invariant, or amend a task ticket.
Moving an entry into the roadmap or authorizing it as a task requires an explicit governance
decision outside this file.

## Lifecycle

```text
observation
    → backlog candidate
    → periodic triage
        → reject
        → retain
        → move to ROADMAP
        → authorize as a task in TASKS
```

Periodic triage records the result in `Status` and `Disposition`. Rejected entries may remain for
historical context. Moving or authorizing an entry requires updating the destination governance
record; changing backlog status alone is insufficient.

## Entry structure

Each entry uses these human-editable fields:

- `Backlog ID`: stable repository-local identity, formatted `BLG-NNN`.
- `Title`: short descriptive name.
- `Status`: `Candidate`, `Retained`, `Rejected`, `Moved to ROADMAP`, or `Authorized as TASK`.
- `Area`: affected subsystem or concern.
- `Source`: observation, review, task, or operational evidence that produced the entry.
- `Problem`: the unresolved condition or opportunity.
- `Potential value`: why future work may be worthwhile.
- `Trigger`: evidence or need that should cause reconsideration.
- `Constraints`: invariants and boundaries any future proposal must preserve.
- `Disposition`: current triage result and next governance action, if any.
- `Comments` (optional): informal operator context, reminders, concerns, or observations.

`Comments` accepts text only. When present, it must be a single plain-text paragraph. Comments are
not structured metadata, executable instructions, Markdown substructure, links, acceptance
criteria, or authoritative requirements. Markdown-looking text or URLs in Comments have no special
meaning. Omit the field when no informal context is needed.

## Candidates

### BLG-001 — Exact-accession Form 10-K retrieval

Backlog ID: BLG-001  
Title: Exact-accession Form 10-K retrieval  
Status: Candidate  
Area: Artifact-specific SEC retrieval  
Source: TASK-016 completion review  
Problem: The Form 10-K adapter selects the latest eligible filing visible in recent submissions and cannot request one known SEC accession directly.  
Potential value: Enable reproducible backfill, audit, correction review, and retrieval of a specifically identified filing without changing latest-filing behavior.  
Trigger: An authorized workflow requires a known historical or superseded Form 10-K accession.  
Constraints: Preserve canonical Form 10-K semantics, authoritative CIK and accession identity, exact primary-document retrieval, bounded network behavior, and existing repository authority; do not create a universal configurable SEC filing engine.  
Disposition: Retain as an unscheduled candidate; require a task ticket before implementation.  
Comments: Exact accession and latest visible are distinct operator intents and should not be silently combined.

### BLG-002 — Historical SEC submissions retrieval

Backlog ID: BLG-002  
Title: Historical SEC submissions retrieval  
Status: Candidate  
Area: Shared SEC provider mechanics  
Source: TASK-016 recent-submissions limitation  
Problem: TASK-016 reads only the SEC recent-submissions columns and does not traverse older submissions history files.  
Potential value: Make older eligible filings available while retaining authoritative metadata and deterministic selection.  
Trigger: Required Form 10-K evidence is no longer present in the issuer's recent submissions response.  
Constraints: Bound history requests and bytes, validate issuer identity, define deterministic page and candidate ordering, preserve retry and pacing limits, and keep form policy in the artifact adapter rather than the provider service.  
Disposition: Retain as an unscheduled candidate; evaluate together with exact-accession needs before roadmap placement.  
Comments: Historical traversal should be justified by a concrete evidence need rather than added speculatively.

### BLG-003 — Amended Form 10-K artifact semantics

Backlog ID: BLG-003  
Title: Amended Form 10-K artifact semantics  
Status: Candidate  
Area: Canonical artifacts and SEC retrieval policy  
Source: TASK-016 explicit Form 10-K/A exclusion  
Problem: The canonical TASK-016 artifact intentionally excludes Form 10-K/A and provides no separate amended-filing contract.  
Potential value: Support correction and amendment analysis without weakening the meaning of the unamended Form 10-K artifact.  
Trigger: A consulting or evidence workflow demonstrates a requirement for amended annual filing evidence.  
Constraints: Decide canonical artifact identity, amendment multiplicity, relationship to the original accession, primary-document meaning, provenance, and no-change semantics before adapter implementation.  
Disposition: Retain as an unscheduled semantic-design candidate; do not make amendment handling a runtime toggle on the existing adapter.  
Comments: Treating amendments as merely another form string would hide material artifact-policy decisions.

### BLG-004 — Additional artifact-specific SEC form adapters

Backlog ID: BLG-004  
Title: Additional artifact-specific SEC form adapters  
Status: Candidate  
Area: Retrieval-adapter extensions  
Source: TASK-016 extension analysis and registry hardening review  
Problem: TASK-022 implemented Form 10-Q, Form 8-K, Form 20-F, and Form 6-K. Proxy, ownership, exhibit, amended-form, and other artifact-specific semantics remain unimplemented.
Potential value: Extend authoritative deterministic acquisition to other high-value canonical artifacts.  
Trigger: A canonical artifact and concrete operator workflow establish form-specific eligibility, selection, multiplicity, and primary-artifact requirements.  
Constraints: Use unique adapter identity and non-overlapping artifact/mode claims; shared provider services or acquisition mechanisms are allowed, but a universal configurable SEC policy adapter is not.  
Disposition: Partially satisfied by TASK-022; retain only the unimplemented artifact families as unscheduled candidates and authorize each contract separately.
Comments: Shared transport does not imply shared artifact semantics.

### BLG-005 — Scheduled or concurrent pull operation

Backlog ID: BLG-005  
Title: Scheduled or concurrent pull operation  
Status: Candidate  
Area: Pull operations and repository coordination  
Source: TASK-016 single-process and single-writer limitation  
Problem: The current local pull workflow assumes operator initiation and single-process, single-writer repository use.  
Potential value: Support larger recurring acquisition workloads and clearer operational coordination.  
Trigger: Measured workload or operator practice demonstrates that manual single-process execution is insufficient.  
Constraints: Preserve immutable attempt evidence, source-scoped monotonic checkpoints, atomic publication, bounded network use, independent artifact outcomes, and recoverable interruption semantics.  
Disposition: Retain for operational evidence; no scheduler or concurrency mechanism is authorized.  
Comments: Operational scale should be measured before selecting a coordination design.

### BLG-006 — Governed semi-deterministic and discovery adapters

Backlog ID: BLG-006  
Title: Governed semi-deterministic and discovery adapters  
Status: Candidate  
Area: Retrieval-adapter governance  
Source: TASK-016 deferred extension boundary  
Problem: TASK-016 implements deterministic structured-source retrieval only; listing, portal, and discovery-based sources remain unsupported.  
Potential value: Acquire evidence from authoritative sources that lack a complete structured identifier-to-artifact path.  
Trigger: A prioritized canonical artifact cannot be retrieved through a deterministic authoritative interface and has a bounded, reviewable discovery surface.  
Constraints: Define bounded candidate generation, uncertainty, operator diagnostics, replayable provenance, failure semantics, and repository ingress before implementation; do not introduce probabilistic selection into the deterministic SEC path.  
Disposition: Retain as unscheduled architecture work; require separate governance and validation criteria.  
Comments: Discovery flexibility must not weaken deterministic adapters or repository evidence authority.

### BLG-007 — Hybrid SQLite structured-state migration

Backlog ID: BLG-007
Title: Hybrid SQLite structured-state migration
Status: Authorized as TASK
Area: Repository persistence and operations
Source: TASK-020 structured repository storage architecture review
Problem: Authoritative structured state remains fragmented across custom JSON records, catalog pointers, generation directories, and replay implementations without cross-record transactions.
Potential value: Make structured publication transactional and index-backed, reduce custom storage mechanics, and improve backup/restore consistency while preserving immutable artifact bytes and public contracts.
Trigger: Explicit authorization of a migration milestone, or the addition of another structured authority, material query latency, concurrent-writer need, cross-file integrity incident, or unmet backup/restore objective.
Constraints: SQLite structured authority plus content-addressed filesystem byte authority; no database BLOB migration; no permanent dual-write; offline shadow import and differential validation; verified backup/restore; one atomic authority cutover; preserve repository/query contracts and authority classes; PostgreSQL only on documented scale or operations triggers.
Disposition: TASK-021 implemented the hybrid authority as a fresh-state foundation rather than a legacy migration; any future import of material retained repositories requires a new ticket.

### BLG-008 — Compose downstream research POCs into the operating product

Backlog ID: BLG-008
Title: Compose downstream research POCs into the operating product
Status: Moved to ROADMAP
Area: Product composition
Source: TASK-068 repository architectural inventory
Problem: Source-object parsing, derived knowledge, governed retrieval, bounded intelligence, and consulting workspaces are implemented and tested but are composed only by task proof scripts and tests. Product-retained artifacts do not enter that chain through the stable CLI or admin application.
Potential value: Turn established architectural contracts into an inspectable end-to-end research workflow without recreating their authorities.
Trigger: A task defines lifecycle, rebuild/freshness, partial failure, retention, and operator-review behavior over actual product evidence.
Constraints: Preserve immutable evidence, independent derived authority, provenance-complete evidence packages, non-authoritative model output, operator inspectability, and one-way dependencies.
Disposition: Direction is recorded in ROADMAP; a task ticket is still required before implementation.

### BLG-009 — Evaluate semantic, retrieval, and model quality

Backlog ID: BLG-009
Title: Evaluate semantic, retrieval, and model quality
Status: Moved to ROADMAP
Area: Knowledge, retrieval, and intelligence quality
Source: TASK-005 through TASK-008 limitations confirmed by TASK-068 inventory
Problem: Current parsing and ontology are narrow, retrieval uses deterministic local vector substitutes, intelligence uses deterministic planner/reasoner substitutes, and structural grounding checks do not establish general semantic entailment or answer quality.
Potential value: Select semantic expansion and replaceable model/retrieval implementations using measurable operator value and governed evaluation.
Trigger: Product composition supplies representative evidence needs, queries, and quality criteria.
Constraints: Do not bypass evidence packages, provenance, disclosure/retention policy, explicit inference, budgets, or fail-closed output validation.
Disposition: Direction is recorded in ROADMAP; retain concrete implementation choice until evaluation requirements are authorized.

### BLG-010 — Resolve official press-release source and transport viability

Backlog ID: BLG-010
Title: Resolve official press-release source and transport viability
Status: Candidate
Area: Artifact-specific acquisition
Source: TASK-066 blocked operational review
Problem: The WDC Business Wire adapter is implemented and Pull-registered, but direct Business Wire transport is denied or times out and the tested feed cannot supply complete release text. The issuer archive is a candidate but was not reachable from the tested execution edge.
Potential value: Deliver genuinely operable official press-release acquisition or explicitly retire an unusable registered path.
Trigger: An authorized issuer archive, licensed source, or production network can be tested through the real acquisition path.
Constraints: Preserve complete official document bytes, issuer attribution, conservative interval coverage, bounded transport, normal repository ingress, and lawful access; browser capture is not an operational fallback.
Disposition: Require a source/transport decision and live acceptance ticket; do not enable or schedule the existing adapter meanwhile.

### BLG-011 — Unique registry for collided historical identifiers

Backlog ID: BLG-011
Title: Unique registry for collided historical identifiers
Status: Candidate
Area: Documentation governance
Source: TASK-068 documentation-authority inventory
Problem: Accepted history contains duplicate ADR-0024, ADR-0026, and TASK-058 identifiers. Filenames and titles disambiguate them, but numeric-only references remain ambiguous.
Potential value: Reduce citation and agent-orientation errors without renumbering or rewriting accepted records.
Trigger: Another collision occurs or tooling needs a unique decision/task key.
Constraints: Preserve historical filenames and provenance; add aliases or a registry rather than silently renumbering accepted records.
Disposition: Retain as documentation maintenance; current guidance requires filename/title-qualified citations.
