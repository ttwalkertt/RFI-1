# Governing design provenance and authority

TASK-001 imported seven root design documents and added the repository-authored `BACKLOG.md`.
Their source/destination provenance and current integrity hashes are recorded in
[`design-baseline.json`](design-baseline.json). The hash manifest proves which files formed the
baseline and how their repository copies evolved. It is not a rule that imported planning prose
overrides later executable repository facts.

The eight tracked root records are:

- `RFI_MANIFESTO.md`
- `README.md`
- `DESIGN_PRINCIPLES.md`
- `ACQUISITION_POC_GUIDANCE.md`
- `BACKLOG.md`
- `TASKS.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`

## Current authority model

For claims about current behavior, use public contracts and committed implementation first, then
executable tests and validation evidence. Accepted ADRs and completed task evidence establish
architectural intent and bounded acceptance. Current orientation documents reconcile those facts.
Historical plans, reviews, and research inputs preserve provenance but cannot override executable
facts.

The complete ordering and maturity vocabulary are maintained in
[`current-state.md`](current-state.md#documentation-authority). In particular:

- `README.md` is the efficient entry point;
- `current-state.md` is the concise current implementation/composition orientation;
- `ARCHITECTURE.md` owns stable layers, authority boundaries, dependency direction, and invariants;
- `ROADMAP.md` owns intended direction but does not authorize work;
- `TASKS.md` and the active ticket own work authorization and current task status;
- `BACKLOG.md` records unscheduled candidates only; and
- ADRs, completed reviews, and ticket records preserve accepted decisions and history.

If these records conflict about implementation, expose the conflict and reconcile the current
orientation to repository evidence. Do not change production behavior merely to satisfy a stale
document.

## Historical identifier ambiguity

Accepted history contains two ADR-0024 filenames and two ADR-0026 filenames. It also contains two
unrelated TASK-058 tickets. The collisions are preserved to avoid rewriting provenance. Cite the
filename or title with the identifier. A future governance task may add a unique registry, but
must not silently renumber accepted records.

## Evolution record

Detailed subsystem history lives in the task reviews and accepted ADRs. The current architecture
now includes the following broad accepted additions beyond the imported acquisition baseline:

- independent source-object and derived-knowledge contracts;
- governed retrieval/evidence packages and bounded intelligence contracts;
- a consulting workspace/execution-journal POC;
- revisioned concepts, target firms, source profiles, Pull Workflow, and local operator surfaces;
- hybrid SQLite/content-addressed persistence and repository-owned artifact queries;
- deterministic SEC forms, transcripts, mailing-list evidence, streams, and feeds.

The capability matrix and precise composition status are intentionally centralized in
[`current-state.md`](current-state.md#capability-maturity-and-composition) rather than repeated in
this provenance note.
