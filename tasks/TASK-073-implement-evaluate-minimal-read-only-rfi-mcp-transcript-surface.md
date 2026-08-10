# TASK-073 — Implement and Evaluate Minimal Read-Only RFI MCP Transcript Surface

**Status:** Implemented and evaluated; independent external comparator unavailable
**Type:** Bounded implementation and architecture experiment
**Depends on:** TASK-071, TASK-072 / ADR-0028
**Scope:** Minimal local read-only MCP transcript surface plus Codex Work comparison experiment

## Objective

Implement the minimum read-only RFI MCP surface necessary to test whether a capable general-purpose investigative runtime such as Codex Work can investigate retained Seagate earnings-call transcripts proficiently while RFI remains responsible for retained truth, canonical identity, provenance, exact evidence, repository semantics, data dictionary, indices/query semantics, and governed access.

This task is an architectural experiment, not an MCP productization task.

The primary objective is not to implement the full MCP surface designed by TASK-072. It is to implement the smallest semantically sound surface necessary to run the experiment, preserve complete diagnostic attribution, and compare the result with TASK-071 and the existing independent analysis.

If the general-purpose runtime struggles, stop and attribute the failure before adding convenience capabilities or broadening the MCP surface.

## Architectural Hypothesis

Test:

> A capable general-purpose investigative runtime can own question interpretation, planning, iterative investigation, query reformulation, counterevidence search, context management, tool orchestration, stopping behavior, sufficiency judgment, synthesis, and report construction when RFI exposes a sufficiently rich and trustworthy epistemic substrate.

RFI continues to own immutable retained evidence, canonical identity, observations and provenance, authoritative retained metadata, deterministic derived metadata and its basis, repository relationships, data semantics, governed query semantics, disposable access/index generation semantics, exact evidence retrieval and integrity verification, and access bounds, health, coverage facts, and diagnostics.

The investigative runtime owns question interpretation and decomposition, hypotheses, search-term and query strategy, counterevidence strategy, investigation-wide budgets, context allocation, stopping, answer sufficiency, evidence selection for claims, synthesis, and report construction.

Do not move investigative behavior into RFI merely to improve experimental results.

## Required Starting Point

Treat TASK-072 and ADR-0028 as the design authority for this experiment, but implement only the bounded first slice needed for the Seagate comparison.

Inspect and reuse current repository contracts where appropriate, especially `ArtifactQueryService`, acquisition repository immutable artifact authority, observation/provenance contracts, TASK-071 transcript segmentation and lexical/temporal access mechanics, retained Seagate corpus and proving traces, and existing repository revision/snapshot semantics.

Do not mechanically expose TASK-071's four model tools through MCP.

## Required Data-Access Improvements

All three TASK-072 access improvements below are required within this task. They are prerequisites for a diagnostically trustworthy MCP experiment, not optional cleanup.

### 1. Immutable artifact-addressed exact reads

Promote normalized exact evidence access by immutable `artifact_id`.

Required behavior:

- exact evidence resolves through immutable artifact identity rather than mutable current `document_id`;
- whole-artifact integrity is verified against retained authority;
- bounded byte-range reads report the requested range and range digest;
- transcript exact-segment reads verify artifact identity, byte span, and segment digest;
- a later logical-document revision cannot silently change evidence represented by an existing segment locator;
- integrity failure and exact-evidence unavailability are typed failures, not empty results;
- content-store paths are not exposed.

### 2. Transcript access generation, health, staleness, bounds, and typed outcomes

Give the disposable transcript access/index layer explicit externally visible semantics.

At minimum expose:

- generation identity;
- repository/authority snapshot used to build the generation;
- health state;
- stale-generation behavior;
- indexed versus eligible document counts;
- build omissions/diagnostics;
- all material build, search, diversity, result, and response bounds;
- typed outcomes distinguishing success, successful empty, partial access, invalid request, stale/unavailable/corrupt access, repository failure, and integrity failure.

A repository authority change after generation build must be detected. The implementation must either reject the stale generation or rebuild explicitly; it must not silently combine old index identity with new retained content.

Do not treat an index outage, omitted document, stale generation, or repository failure as zero matches.

### 3. Standalone machine-legible data dictionary

Separate stable interface semantics from one corpus-instance response.

Provide a discoverable, versioned data dictionary explaining at least retained object types; logical document versus immutable artifact identity; observation and provenance semantics; authoritative versus deterministic-derived fields; source-effective time and its basis; transcript canonical classification and event-kind limitations; query/index semantics; candidate snippets versus exact verified evidence; successful empty versus failure; query completeness, index coverage, retained-corpus coverage, and answer sufficiency as distinct concepts; filters/orderings; pagination and bounds; and access generation/health semantics.

The dictionary must be useful to an unfamiliar capable agent without requiring a large RFI-specific procedural prompt. It must not prescribe investigation strategy, stopping, evidence preference, or report construction.

## Unknown-Scope and Empty-Result Semantics

Normalize these semantics before the experiment:

- known firm/scope with no matching artifacts → successful `empty`;
- unknown `firm_id` or other governed scope identifier → typed `unknown_object` or equivalent invalid-scope outcome;
- known corpus with a valid lexical query and no matches → successful `empty`;
- unknown artifact/document/observation/segment identifier → typed `unknown_object`;
- unavailable/stale/corrupt access generation → typed access failure;
- repository read failure → typed repository failure.

Invalid identifiers must never count as evidence of absence.

## Minimal MCP Surface

Implement only the surface needed for the experiment.

### Descriptive resources

Provide:

- `rfi://about`;
- `rfi://dictionary`;
- `rfi://capabilities`.

Expose server/repository identity, schema version, read-only status, repository snapshot, available/deferred capabilities, access-generation health, and relevant limits without investigative procedure.

### Repository resources

Provide only those required for the proving slice:

- logical document resource;
- immutable artifact resource;
- selected acquisition observation resource sufficient to inspect provenance;
- transcript corpus view;
- exact transcript-segment resource;
- bounded ordered transcript document/segment window.

### Tools

Implement:

#### `query_artifacts`

Expose governed retained-artifact selection using existing repository semantics, preserving canonical filtering, firm/scope semantics, source-effective ordering and basis, repository snapshot, bounded pagination, diagnostics, and total/returned counts where available.

#### `search_transcript_segments`

Expose bounded lexical/temporal candidate search over the declared retained transcript scope.

Results must identify themselves as candidate projections, not citable exact evidence. Expose normalized query semantics, scope, ordering, document/artifact/segment identity, source-effective date and basis, rank/score/snippet as derived access data, generation/snapshot, all applied bounds, total/returned/truncation information, and typed empty/failure outcomes.

Search-term choice and query reformulation remain runtime decisions.

#### `read_artifact_bytes`

Expose bounded exact bytes by immutable `artifact_id`, including artifact identity/checksum, requested half-open byte range, exact bytes or explicitly labeled rendering, range digest, applicable bounds, and verification result. Never silently clip a requested range.

### Explicitly Deferred Surface

`query_artifact_history` is not required unless implementation reveals that selected observation and document/artifact links are insufficient for provenance inspection. If deferred, declare it through capability discovery. Do not replace it with raw acquisition rows.

## MCP Transport and Deployment

Use local MCP `stdio`.

The server shall run locally, receive explicit RFI state/configuration, operate read-only over retained repository authority, perform no acquisition/correction mutation, expose no general filesystem capability, and require no HTTP service or remote authentication.

Remote transport, distributed operation, authentication, and multi-user authorization are out of scope.

## TASK-071 Separation

The MCP implementation may reuse or refactor stable transcript access mechanics from TASK-071 where they represent legitimate access semantics.

It must not import or reproduce TASK-071 investigative behavior, including mandatory tool ordering, investigation-wide budgets, hypothesis tracking, failed-search accounting as investigative policy, citation admission policy, temporal-boundary investigative rules, final-turn stopping, recovery work orders, adjudication, report generation, or OpenAI/model adapter behavior.

TASK-071 remains a comparison implementation, not the MCP runtime.

## Seagate Experimental Corpus

Use the same retained Seagate transcript corpus used by TASK-071.

Before running the comparison, verify and record corpus parity with the retained proving baseline, including document and segment inventory, or explicitly explain any repository change since that baseline.

Do not silently substitute external transcript files or internet evidence. The experiment concerns RFI retained truth.

## Experimental Questions

Run Codex Work against the same five substantive TASK-071 cases:

1. management sentiment/confidence over time;
2. cloud/nearline demand and constraints;
3. HAMR/Mozaic progress;
4. first/latest discussion of 40-TB-class capacity;
5. named-executive employee attrition by geography / retained-corpus insufficiency.

Use the same substantive question wording where practical.

The fifth case is an important negative/insufficiency control.

Do not create question-specific MCP tools or resources to improve performance on these cases.

## Codex Work Experimental Conditions

Exercise the MCP surface as an unfamiliar capable agent would.

Provide only the minimum orientation necessary to identify RFI as the retained-evidence source and state the research question.

Do not supply TASK-071's investigation protocol, tool order, stopping rules, citation rules, search hints, valid-document inventory, or recovery strategy.

The data dictionary, capability descriptions, MCP schemas, resources, and returned links are expected to make the repository legible.

Record exactly what RFI-specific prompt material was required. If substantial procedural prompting becomes necessary, record that as experimental evidence rather than silently adding it.

## Instrumentation

For every MCP request/resource read, record at least:

- correlation/request ID;
- capability and schema version;
- normalized input and deterministic input digest;
- repository snapshot;
- access generation and health;
- start/end time;
- typed outcome/error;
- returned and total counts where applicable;
- cursor/pagination state;
- every applied bound and truncation;
- referenced document/artifact/observation/segment IDs;
- exact artifact/range digests for evidence reads;
- response digest and byte count.

Preserve the Codex Work-side investigation trace separately, including original question, MCP discovery, tool/resource sequence, queries/reformulations, exact evidence reads, final answer/report, cited evidence, and runtime-visible failures.

Correlate traces by request ID where possible.

RFI must not record or manufacture hidden planner state, hypotheses, or sufficiency judgments.

## Diagnostic Attribution

Evaluate poor results before modifying the MCP surface.

Classify observed failures as at least:

### Repository/MCP/access failure

Relevant retained evidence exists but catalog/query semantics fail to expose it, the access generation omits it, bounds hide it without disclosure, MCP semantics make it materially inaccessible, exact evidence resolves incorrectly, or failure is misrepresented as absence.

### Retrieval-quality failure

The access surface operates correctly but lexical/index semantics fail to retrieve evidence that a reasonable query should locate. Keep this distinct from runtime search-strategy failure.

### Investigative-runtime failure

Appropriate capabilities/evidence are available, but Codex Work fails to discover them, chooses poor queries without adequate reformulation, ignores relevant returned evidence, fails to search qualifications/counterevidence, stops prematurely, or misjudges insufficiency.

### Repository-authority failure

The runtime uses the interface correctly, but RFI supplies incorrect or materially ambiguous canonical identity, retained metadata, event date/basis, provenance, artifact association, or exact bytes/checksum.

### Synthesis failure

Discovery and exact evidence are adequate, but the final conclusion overstates evidence, ignores qualifications, makes unsupported claims, misrepresents chronology, or cites evidence that does not support the claim.

Do not add MCP convenience operations until the observed failure has been assigned to one of these classes or explicitly remains unresolved.

## Comparison

Compare Codex Work + MCP against:

- TASK-071's retained proving results; and
- the existing independent analysis used as the external quality reference.

Do not require identical tool counts, search terms, investigation paths, selected evidence, conclusions where multiple conclusions are defensible, or prose.

Compare at least evidence discovery, exact evidence/citation integrity, chronology, qualification/counterevidence quality, insufficiency calibration, unsupported claims, error handling, stopping behavior, amount of RFI-specific procedural prompting required, access efficiency as a secondary metric, and diagnostic explainability of failures.

The central question is whether the general runtime can investigate proficiently without RFI owning the investigative loop.

## Required Tests

Add focused automated coverage for at least:

- MCP capability/resource/tool discovery;
- schema/version contracts;
- `query_artifacts` equivalence with repository semantics;
- known-empty versus unknown-scope behavior;
- invalid identifiers;
- stale cursors;
- repository failures;
- immutable artifact-ID exact reads;
- byte-range and digest verification;
- logical document revision after transcript generation build;
- stale-generation detection;
- prevention of artifact drift during segment expansion;
- segment-ID stability;
- exact segment byte/digest verification;
- access health distinctions;
- malformed/omitted transcript document producing visible partial access;
- all material internal/result bounds and truncation indicators;
- Seagate corpus parity with the recorded proving baseline;
- read-only behavior with no retained repository mutation.

Where practical, test that the MCP adapter does not depend on TASK-071 harness, adjudication, reporting, model adapter, SQLite schema details, or content-store paths.

## Required Deliverables

Produce:

1. minimal local read-only RFI MCP implementation;
2. normalized immutable artifact-ID exact-read capability;
3. transcript access generation/health/staleness and typed outcome capability;
4. standalone versioned machine-legible data dictionary;
5. focused automated tests;
6. complete correlated MCP access traces for the Seagate experiment;
7. preserved Codex Work investigation outputs/traces for all five questions;
8. comparative evaluation against TASK-071 and the independent analysis;
9. explicit diagnostic attribution for every material failure or quality gap;
10. experiment summary with architectural disposition;
11. normal commit-aware review package.

## Experimental Stopping Rule

The implementation phase stops when the minimum surface is sufficient to run the five-question experiment correctly.

During evaluation:

> If Codex Work struggles, stop and attribute the failure before adding capabilities.

Do not respond to a weak result by immediately adding question-specific tools, investigation prompts, support/counterevidence helpers, report-generation helpers, TASK-071 control logic, semantic retrieval, or additional evidence types.

Any proposed expansion must follow the attribution report and become a separately justified task or explicit repair.

## Out of Scope

Do not:

- implement the full TASK-072 conceptual MCP catalog;
- expose arbitrary SQL or repository filesystem paths;
- implement general filesystem access;
- add semantic embeddings or reranking;
- add universal cross-evidence search;
- expose mailing-list, feed, stream, source-object, or knowledge MCP extensions;
- add persistent investigation, hypothesis, claim, or report state;
- add RFI-owned investigative planning, stopping, or sufficiency logic;
- add MCP prompts prescribing research workflow;
- add acquisition or correction mutation;
- add a second evidence type;
- implement remote MCP transport or multi-user policy;
- build a general consulting workspace;
- treat success on Seagate transcripts as proof of a universal MCP architecture.

## Acceptance Criteria

TASK-073 is complete when:

1. all three required TASK-072 data-access improvements are implemented and tested;
2. a local read-only MCP server exposes the minimum required transcript/repository surface;
3. exact evidence is artifact-addressed and verified, with no mutable-document drift;
4. transcript access exposes generation, snapshot, health, staleness, diagnostics, and material bounds;
5. an unfamiliar agent can discover stable RFI semantics through the standalone dictionary and capability surface;
6. valid empty results, unknown identifiers/scopes, partial access, stale/unavailable access, repository failures, and integrity failures are distinguishable;
7. the server does not encode TASK-071 investigative procedure;
8. the retained Seagate corpus is verified against or reconciled with the proving baseline;
9. Codex Work is run against all five proving questions using only the bounded MCP surface and minimal orientation;
10. complete MCP and runtime traces are preserved sufficiently for diagnostic attribution;
11. results are compared with TASK-071 and the independent analysis;
12. every material weakness is attributed before any surface expansion is recommended;
13. no second evidence type or broader MCP productization is introduced;
14. tests and repository validation pass;
15. completed work is committed and pushed and a commit-aware review package is generated.

## Final Architectural Disposition

End the task with one of:

**Accept MCP + general-runtime investigative boundary**

**Repair named RFI/MCP access or retrieval gap and repeat experiment**

**General runtime is not yet a proficient replacement for TASK-071 investigative behavior**

**Reject the architectural hypothesis**

State the evidence supporting the disposition, quality comparison against TASK-071 and independent analysis, repository/access failures, retrieval-quality failures, investigative-runtime failures, repository-authority failures, synthesis failures, amount of RFI-specific procedural prompting required, and next bounded action if any.

Do not broaden the MCP surface merely to obtain an `Accept` disposition.
