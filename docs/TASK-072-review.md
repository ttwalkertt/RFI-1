# TASK-072 architectural review

## Outcome

TASK-072 completes a repository-grounded design for a read-only, agent-legible RFI MCP surface. It
recommends proceeding with a bounded Codex Work experiment after implementing a deliberately small
surface and correcting three access-layer gaps: immutable artifact-ID reads, transcript access
generation/health/typed outcomes, and a standalone data dictionary.

The primary deliverable is
[`rfi_mcp_surface_design.md`](design/rfi_mcp_surface_design.md). The accepted
experimental boundary is recorded in
[`ADR-0028`](decisions/0028-agent-legible-rfi-mcp-boundary.md).

No MCP server, dependency, transport, tool registration, acquisition change, research-harness
change, retained-state change, or production behavior is introduced.

## Repository-grounded findings

The design inspected current artifact/acquisition, research, retrieval, source-object, knowledge,
mailing-list, feed, stream, classification, coverage, test, and retained Seagate trace contracts.
That inspection established:

- `ArtifactQueryService.query()` is a reusable semantic catalog boundary with typed filters,
  source-effective order, snapshots, cursors, totals, and diagnostics.
- Current content reads resolve a mutable logical `document_id`; the normalized service lacks an
  immutable `artifact_id` read even though exact artifact reads exist in acquisition authority.
- Current detail/observation navigation does not expose normalized full document-revision history.
- TASK-071's transcript segmentation, lexical/temporal search, and stable byte locators are useful
  access mechanisms, but its generic failures, hard 100-document build, hidden internal bounds,
  dropped artifact diagnostics, and unenforced access snapshot are unsuitable as-is for MCP.
- TASK-071's tool order, budgets, stopping, citation admission, adjudication, recovery, and report
  construction are harness behavior and stay outside the proposed surface.
- The current Seagate corpus's missing speaker/event-kind metadata, conference-title/canonical-type
  conflict, and indeterminate coverage must remain visible limitations.

## Proposed boundary

The design uses:

- descriptive resources for server identity, the versioned data dictionary, and live capability
  health;
- addressable resources for logical documents, immutable artifacts, observations, exact transcript
  segments, corpus views, and ordered segment windows;
- tools for bounded artifact query, artifact history, transcript candidate search, and exact byte
  ranges; and
- no MCP prompts.

Every result separates authoritative and derived fields, successful empty results and failures,
coverage and answer insufficiency, candidate snippets and exact evidence, repository snapshots and
access generations, and each applied bound.

## Seagate validation design

The walkthrough covers the same five substantive cases as TASK-071: sentiment over time,
cloud/nearline demand and constraints, HAMR/Mozaic progress, first/latest 40-TB discussion, and
named-executive attrition by geography. It shows how a capable runtime can orient, search,
reformulate, expand exact evidence, inspect identity/provenance, look for qualifications, recognize
retained-corpus insufficiency, and synthesize independently.

No question-specific MCP operation is introduced to shorten the walkthrough.

## Diagnostic attribution

The design separately identifies:

- repository/MCP failures through generation inventory, snapshots, bounds, response traces, and
  exact digests;
- investigative-runtime failures through adequate returned evidence that the runtime ignores or
  fails to pursue;
- repository-authority failures through incorrect/ambiguous canonical metadata, provenance, or
  bytes; and
- synthesis failures through correct discovery/expansion followed by unsupported claims.

The recommended implementation records correlated per-request capability, schema, input, snapshot,
generation, outcome, counts, bounds, object IDs, evidence digests, and response digest. Runtime
planning state remains outside RFI.

## Design disposition and next task

**Proceed with MCP experiment.** Authorize a bounded TASK-073 to implement the local read-only
transcript slice and compare Codex Work against the five retained TASK-071 cases. The experiment
must stop and attribute poor results before adding convenience tools or broader evidence types.

The hypothesis is weakened if the runtime needs a large RFI-specific procedural prompt, cannot
discover/cite exact evidence, conflates failures with no matches, or performs materially worse than
TASK-071 despite correct complete access responses.

## Verification and review evidence

The task's review package is generated after commit by
`scripts/generate_task072_review.py`. It captures the complete committed patch, primary design,
decision, ticket, relevant implementation contracts, Seagate corpus/trace summaries, documentation
checks, design baseline, focused current-contract tests, documentation-only scope proof, and full
project validation.

## Known limitations

- This is a design, not an implemented or validated MCP interface.
- MCP resource/template usability with Codex Work remains empirical.
- The first slice is transcript-specific and does not prove a cross-domain universal surface.
- Transcript lexical recall and historical metadata fidelity remain provisional.
- Corpus coverage cannot currently be aggregated authoritatively from historical acquisition
  outcomes.
- Artifact history and common capability/dictionary contracts require implementation work.
- Local `stdio` does not address remote transport, authentication, multi-user authorization, or
  distributed operation.

## Architectural Status Summary

- **Immutable evidence and acquisition history — Complete, unchanged.** RFI remains the exact-byte,
  canonical identity, observation, and provenance authority.
- **Artifact query/read contracts — Complete with identified gaps.** Catalog/detail/current content
  are usable; immutable artifact-ID and normalized history access need cleanup.
- **Transcript acquisition/classification — Usable with limitations.** Provider, coverage,
  historical classification, event-kind, and speaker limits remain visible.
- **Transcript access/IQA — Implemented POC; provisional.** Search/locator mechanics are useful;
  health, staleness, typed outcomes, bound reporting, and artifact-addressed exact reads need work.
- **Agent-legible MCP design — Complete.** Resource/tool/prompt disposition, schemas, authority,
  failure taxonomy, gaps, walkthrough, instrumentation, minimal slice, and falsification criteria
  are specified.
- **MCP implementation — Not Started.** No server, dependency, or production behavior exists.
- **General-runtime experiment — Not Started.** Recommended next bounded milestone is TASK-073.

Architectural change: RFI now has an accepted experimental MCP boundary that preserves repository
epistemic authority while assigning all investigative behavior to a capable general-purpose
runtime. The surface remains provisional until the Codex Work experiment.
