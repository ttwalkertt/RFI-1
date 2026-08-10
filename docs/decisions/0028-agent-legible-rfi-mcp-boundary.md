# ADR-0028: Agent-legible RFI MCP boundary

## Status

Accepted for a bounded read-only experiment. No MCP implementation or product commitment is made
by this decision.

## Context

RFI owns immutable retained evidence, canonical identity, observations, provenance, normalized
repository metadata, and several governed access POCs. TASK-071 demonstrated that a bounded model
harness could investigate retained Seagate transcripts through public artifact reads and a
transcript-specific disposable index. That harness also owned tool order, investigation budgets,
stopping, evidence admission, adjudication, recovery, and report output.

The next architectural question is whether a capable general-purpose runtime can own that
investigative behavior while RFI exposes only a rich epistemic substrate through MCP. A direct MCP
translation of TASK-071 would make an experimental harness the external repository interface and
would prevent meaningful attribution of access failures versus planning or synthesis failures.

Implementation inspection also found that current transcript access records an artifact snapshot
without enforcing it on later expansion, reads exact expansion through a mutable document
projection, uses generic errors, mixes schema discovery with one corpus response, and does not
expose all applied bounds or access-generation health.

## Decision

1. RFI MCP is read-only and semantic. It exposes repository concepts, never SQLite, storage paths,
   raw event tables, provider adapters, or arbitrary method dispatch.
2. The common surface consists of versioned descriptive resources, a live capability/health
   registry, addressable document/artifact/observation resources, governed bounded query/history/
   exact-byte tools, and evidence-type-specific extensions.
3. Transcript access is one extension. It exposes a parameterized corpus view, lexical/temporal
   segment selection, exact verified segment resources, and bounded ordered document windows.
4. Search hits and snippets are derived candidates. Exact evidence must be re-read and verified
   against immutable `artifact_id`, byte span, and digest.
5. Every result distinguishes authority class, repository snapshot, access generation, applied
   bounds, coverage, diagnostics, successful empty state, and typed failure.
6. The general-purpose runtime owns question interpretation, planning, query reformulation,
   hypothesis/counterevidence strategy, context and tool orchestration, stopping, sufficiency,
   synthesis, and report construction.
7. RFI exposes no MCP prompts in the first experiment and no investigation, adjudication,
   recovery, claim-selection, or report-generation tool.
8. Evidence types may add justified domain-specific access extensions. RFI does not create one
   universal search or relationship grammar that erases mail, feed, stream, source-object,
   knowledge, or transcript semantics.
9. The first implementation experiment is local `stdio`, single-user, explicitly configured,
   read-only, transcript-scoped, and fully instrumented. Remote deployment, authentication,
   mutation, and broader evidence types remain deferred.
10. Before or within that first slice, the access boundary must add immutable artifact-ID reads,
    transcript generation/health/staleness, typed outcomes, separate dictionary discovery, and
    complete bound/diagnostic reporting. These are access semantics, not investigative behavior.

The detailed provisional resource/tool catalog and validation method are defined in
[`docs/rfi_mcp_surface_design.md`](../rfi_mcp_surface_design.md).

## Consequences

- An unfamiliar runtime can discover identity, authority, time, provenance, exact evidence,
  filters, bounds, and failures without a large RFI-specific procedural prompt.
- Known repository objects become resources; selection and bounded computation remain tools.
- TASK-071 stays an evidence/comparison case rather than the target interface.
- A model that misses available evidence can be distinguished from an MCP/index omission; a bad
  repository fact can be distinguished from an unsupported synthesis.
- The first implementation is slightly larger than a mechanical wrapper because current exact
  artifact addressability and transcript health/error semantics need correction.
- MCP resource/template client behavior becomes an empirical risk. The experiment measures it
  before duplicating all resources as tools.
- Success over Seagate transcripts does not establish a universal RFI MCP or justify product
  integration. Each additional evidence type requires a bounded semantic extension decision.
- Generated conclusions remain outside retained repository truth.

## Rejected alternatives

- generic SQL or filesystem access;
- translating TASK-071's model tool schemas and harness rules directly;
- one question/investigation/evidence-package/report tool;
- question-specific sentiment, supporting-quote, counterevidence, sufficiency, or chronology tools;
- one universal search across source evidence, derived knowledge, tombstones, and projections;
- exposing every Python service method;
- treating snippets as exact evidence or returning repository failures as empty results; and
- MCP prompts that prescribe investigation or report behavior.

## Experiment falsification

The boundary hypothesis is weakened if a capable runtime with correct MCP responses cannot
discover and cite exact evidence, recognize coverage and metadata limitations, distinguish errors
from no matches, or achieve support quality comparable to TASK-071 without a large RFI-specific
procedural prompt. Such a result should be attributed before broadening the surface: repository
semantic gap, MCP/resource usability gap, retrieval-quality gap, runtime investigation failure, or
synthesis failure.
