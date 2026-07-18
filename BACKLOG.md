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
Problem: Form 10-Q, Form 8-K, proxy, ownership, exhibit, and foreign-issuer semantics are not implemented.  
Potential value: Extend authoritative deterministic acquisition to other high-value canonical artifacts.  
Trigger: A canonical artifact and concrete operator workflow establish form-specific eligibility, selection, multiplicity, and primary-artifact requirements.  
Constraints: Use unique adapter identity and non-overlapping artifact/mode claims; shared provider services or acquisition mechanisms are allowed, but a universal configurable SEC policy adapter is not.  
Disposition: Retain as a family of unscheduled candidates; authorize each artifact contract separately.  
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
