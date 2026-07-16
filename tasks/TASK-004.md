# TASK-004 — First Live SEC Acquisition and Real Consulting Corpus

## Status

Ready

## Authorized Native EDGAR Amendment — 2026-07-15

The operator accepts the credential-free SEC-API.io implementation as valuable partial work but
amends the live-completion strategy for this task:

- native SEC EDGAR is the required live acceptance path;
- SEC-API.io remains an optional commercial acceleration adapter whose live behavior is untested;
- official `data.sec.gov/submissions/CIK##########.json` data governs discovery;
- official `www.sec.gov/Archives/edgar/data/` complete-submission paths govern exact retrieval;
- the existing STX/WDC, date, form, and count boundary is unchanged;
- native requests require an operator-supplied runtime User-Agent with application identity and
  contact address, referenced only as `env:RFI_SEC_USER_AGENT`;
- no personal contact value may be invented, committed, persisted in repository state, printed in
  diagnostics, copied into fixtures, or included unsanitized in review evidence;
- requests must be paced conservatively below the SEC-published maximum and remain bounded;
- normal tests remain offline through sanitized deterministic EDGAR transport fixtures;
- the SEC-API.io implementation and tests must not be removed or weakened.

This amendment supersedes the native-EDGAR production-path exclusion elsewhere in this ticket only
to the extent required for the bounded native live acceptance. It does not authorize crawling,
bulk ingestion, XBRL parsing, full-text search, extraction, downstream knowledge, AI, or reporting.
If the required runtime User-Agent identity is absent, implementation and offline verification may
proceed, but native network access must stop and TASK-004 must remain incomplete.

## Objective

Implement the first live SEC acquisition path for RFI-1 using a configured commercial SEC data provider, and use it to acquire a deliberately bounded real corpus relevant to the operator’s HDD consulting work.

This is a vertical milestone, not merely an adapter-construction task.

TASK-004 is complete only when the existing acquisition kernel has successfully:

- authenticated to the configured provider through a non-persisted credential boundary;
- discovered and retrieved real SEC filing evidence;
- stored exact source artifacts and provenance through the existing repository contracts;
- completed a bounded live acquisition for the selected issuer corpus;
- repeated the same acquisition idempotently;
- replayed and rebuilt repository-derived state with the provider unavailable;
- produced a complete, sanitized verification package.

The implementation must preserve provider independence. The provider accelerates acquisition; it must not own repository identity, evidence semantics, replay, or consulting knowledge.

## Context

TASK-001 established the repository foundation and governing design baseline.

TASK-002 implemented the repository-owned acquisition substrate:

- governed sources;
- stable internal identities;
- immutable content-addressed artifacts;
- append-only retrieval history;
- rebuildable document and checkpoint indexes;
- checkpoint ordering;
- replay and integrity validation.

TASK-003 implemented and verified the acquisition engine and adapter boundary through deterministic fixture adapters:

- explicit adapter registration;
- paginated discovery;
- exact-byte retrieval;
- deterministic ordering and duplicate handling;
- partial-failure and resumption behavior;
- run summaries;
- checkpoint finalization;
- offline replay and rebuild.

TASK-004 must now expose those assumptions to real provider and SEC behavior. Real evidence may justify narrowly scoped contract corrections, but the live adapter must fit behind the existing engine rather than absorb or replace it.

The governing design documents, prior ADRs, current acquisition code, and current operator workflow remain authoritative.

## Working Milestone

At completion, RFI-1 should contain a small, real, auditable SEC corpus that is useful as the evidence foundation for later consulting-oriented knowledge development.

The minimum governed issuer corpus is:

- Seagate Technology Holdings plc — ticker `STX`;
- Western Digital Corporation — ticker `WDC`.

The minimum filing scope is a bounded recent set of:

- annual reports (`10-K`);
- quarterly reports (`10-Q`);
- material current reports (`8-K`).

Codex must select and document a deterministic date or count boundary that:

- is small enough for inexpensive repeatable POC execution;
- includes meaningful real filing variety;
- is not dependent on “latest” at test time;
- can be rerun without silently widening the corpus;
- produces enough evidence to validate pagination, metadata, exact bytes, provenance, and idempotency.

Additional issuers or form types must not be added merely to make the demonstration look larger.

## Governing Principles

The implementation must preserve these principles:

1. The repository is the durable system of record.
2. Provider data is input evidence, not repository identity.
3. Repository-owned document identity must survive provider replacement.
4. Exact retrieved bytes must be preserved immutably.
5. Provenance must identify the real issuer, filing, provider mechanism, retrieval time, and source reference.
6. Retrieval history remains append-only and inspectable.
7. Checkpoints advance only after required durable effects.
8. Live acquisition and offline replay are separate operations.
9. Unit and integration tests must not require a commercial account or network.
10. A live acceptance run is required for task completion.
11. Secrets must never enter source profiles, repository evidence, logs, patches, tests, fixtures, or review artifacts.
12. Provider-specific pagination, authentication, rate limits, and response mapping belong in the adapter boundary.
13. Provider-specific identifiers must remain provenance attributes, not repository-owned identity.
14. Real integration evidence should drive corrections; speculative provider abstraction should be avoided.
15. Acquisition remains separate from parsing, interpretation, claims, and projection.
16. The result must remain understandable and operable by a single technical owner.

## Required Preconditions

TASK-004 live completion requires:

- an active account with the selected commercial SEC data provider;
- a valid API credential available to the execution environment;
- authorization to perform bounded live requests;
- sufficient provider quota for implementation validation and the bounded live corpus.

The credential must be supplied through a runtime-only mechanism chosen and documented by Codex, such as an environment variable or local ignored configuration file.

The task ticket does not authorize reading arbitrary credential stores.

If no credential is available, Codex may implement and validate the adapter offline, but it must report the task as blocked or incomplete. It must not fabricate live evidence or claim completion without a successful live acceptance run.

## Required Outcomes

### 1. Commercial SEC provider adapter

Implement one real SEC acquisition adapter behind the TASK-003 adapter contract.

The adapter must:

- authenticate through the approved runtime credential boundary;
- validate required runtime configuration before network access;
- discover bounded filings for governed issuer profiles;
- support the provider’s real pagination or continuation behavior;
- retrieve exact filing bytes or the most authoritative exact artifact exposed by the provider;
- preserve relevant provider response metadata as provenance without allowing it to define repository identity;
- map provider failures into the engine’s existing failure model;
- expose actionable sanitized diagnostics;
- avoid direct access to repository persistence;
- avoid logging secrets, authorization headers, complete credential-bearing URLs, or sensitive raw error bodies.

The selected provider may initially be SEC-API.io or another approved commercial SEC filing service. The durable adapter and documentation must name the actual provider used.

### 2. Stable SEC filing identity

Define and verify the repository-owned identity rule for SEC filings.

The identity model must remain stable across:

- repeated discovery;
- provider pagination changes;
- provider URL changes;
- provider replacement;
- retrieval on different dates;
- amendments and filing revisions;
- multiple artifacts associated with one filing where applicable.

Codex must base identity on durable SEC filing semantics rather than ticker alone, filename alone, provider object ID alone, or mutable URL alone.

The design record must explain:

- issuer identity;
- filing identity;
- accession or equivalent filing key treatment;
- form type;
- filing date;
- amendment behavior;
- artifact identity;
- provider provenance.

### 3. Governed live source profiles

Add minimum governed source definitions for the real corpus.

Profiles must:

- use stable internal source IDs;
- identify issuer scope;
- identify form scope;
- specify the deterministic date or count boundary;
- select the commercial adapter explicitly;
- reference credentials indirectly;
- expose bounded request or quota controls where practical;
- validate before any live request;
- remain free of secret values.

The profiles must not silently expand from a bounded POC corpus into an open-ended filing mirror.

### 4. Network client boundary

Implement a proportionate network boundary for the live adapter.

It must address:

- connection and read timeouts;
- provider authentication;
- bounded retries;
- rate-limit or quota responses;
- transient server failures;
- permanent request failures;
- response status validation;
- content-type and response-shape validation;
- maximum response or artifact size where appropriate;
- sanitized diagnostics;
- deterministic injection or replacement for offline tests.

Do not build a generalized HTTP framework. Implement what the real provider and current adapter require.

### 5. Provider response mapping

Map real provider discovery and retrieval responses into existing RFI contracts.

The mapping must preserve and distinguish:

- repository source identity;
- repository document identity;
- candidate identity;
- filing accession or equivalent SEC identity;
- issuer identifiers such as CIK and ticker where available;
- form type;
- filing and acceptance timestamps where available;
- amendment status;
- provider identifier;
- provider discovery URL or source reference;
- retrieved artifact URL or reference;
- media type;
- exact artifact checksum;
- retrieval mechanism and timestamp.

Unknown, absent, or inconsistent provider fields must be handled explicitly rather than guessed.

### 6. Bounded real corpus acquisition

Execute a real acquisition for the governed STX and WDC corpus.

The live run must:

- begin from a documented empty runtime repository state;
- use the production acquisition engine and live adapter;
- stay within the configured bounded scope;
- preserve exact acquired evidence;
- produce inspectable provenance and retrieval history;
- record skips, duplicates, and failures accurately;
- advance checkpoints only after durable success;
- produce a structured run summary.

The live corpus itself is local runtime data and must not be committed unless the governing repository policy explicitly requires a small sanitized sample. Full real filing artifacts should remain outside Git.

### 7. Live idempotency and incremental behavior

Run the same bounded live acquisition again.

The second run must demonstrate:

- no duplicate immutable artifacts;
- stable repository document identity;
- safe checkpoint behavior;
- accurate duplicate or unchanged outcomes;
- append-only evidence where a repeated attempt is materially recorded;
- no widening of the corpus caused by relative-time behavior;
- stable final derived state.

Where provider output changes between runs, the verification package must distinguish normal provider metadata drift from real filing-content or corpus changes.

### 8. Offline tests and recorded provider fixtures

Create sanitized, deterministic provider fixtures derived from the real integration sufficiently to exercise the adapter without network access.

Fixtures must:

- contain no credential, authorization header, account identifier, private quota information, or sensitive request URL;
- preserve the response shapes needed to test mapping, pagination, errors, and retrieval;
- be small and reviewable;
- identify how they were sanitized;
- avoid embedding the complete real corpus when a smaller representative response is sufficient.

The normal project test suite and isolated-tree validation must pass without an API key and without network access.

### 9. Real failure behavior

Verify representative provider-facing failures through deterministic offline tests and, where safely available, bounded live behavior.

At minimum cover:

- missing credential;
- invalid configuration;
- authentication rejection;
- quota or rate-limit response;
- transient server failure;
- timeout;
- malformed discovery response;
- missing required filing identity fields;
- retrieval response with unexpected content type;
- empty or truncated artifact response;
- pagination or continuation anomaly.

Tests must prove that failures do not overstate progress or leak secrets.

Do not deliberately consume excessive quota or provoke abusive provider traffic merely to create evidence.

### 10. Replay, rebuild, and provider independence

After the live corpus is acquired:

- disable or remove access to the provider credential;
- block network access;
- replay authoritative repository state;
- delete and rebuild derived indexes;
- verify all stored artifact checksums;
- inspect the reconstructed corpus;
- prove that provider access is not required for replay, rebuild, or routine repository inspection.

This is a mandatory completion condition.

### 11. Operator workflow

Provide documented operator commands for:

- checking live-provider configuration without exposing the secret;
- validating governed issuer profiles;
- estimating or displaying the bounded run scope;
- running one issuer;
- running the complete bounded corpus;
- displaying run summaries;
- inspecting provider failures;
- repeating an idempotency run;
- inspecting acquired filing metadata;
- verifying artifact integrity;
- disabling provider access and replaying;
- deleting and rebuilding indexes;
- running offline validation;
- running the gated live acceptance validation;
- generating the TASK-004 review package.

Commands must clearly distinguish offline checks from live, quota-consuming operations.

### 12. Usage and quota evidence

Capture proportionate provider-usage evidence.

Where the provider exposes relevant information, record sanitized:

- number of live requests;
- issuers queried;
- pages retrieved;
- filing artifacts retrieved;
- rate-limit or quota headers without account secrets;
- approximate task-run usage.

Do not implement a general billing subsystem. The purpose is to establish whether this acquisition approach is operationally and economically plausible for the POC.

### 13. Real-integration design record

Record the material lessons from the live integration.

The design record must address:

- actual provider selected;
- provider API surfaces used;
- authentication boundary;
- network-client behavior;
- real pagination behavior;
- SEC identity mapping;
- filing artifact choice;
- error and quota behavior;
- deviations between fixture assumptions and real behavior;
- changes made to TASK-002 or TASK-003 contracts;
- observed corpus characteristics;
- unresolved risks;
- recommendations for TASK-005 hardening;
- alternatives considered, including direct SEC retrieval where relevant.

## Required Live Demonstration

The final demonstration must prove:

1. runtime credential validation succeeds without exposing the secret;
2. STX and WDC governed profiles validate;
3. the bounded corpus can be described before execution;
4. the real provider adapter is selected explicitly;
5. real filing candidates are discovered through actual provider pagination;
6. real filing artifacts are retrieved and stored immutably;
7. SEC filing identity remains repository-owned and inspectable;
8. provenance contains issuer, filing, provider, and retrieval evidence;
9. the first run completes or reports bounded, well-explained partial results;
10. a second equivalent live run is idempotent;
11. any duplicates, unchanged filings, skips, or failures are correctly classified;
12. checkpoints do not advance beyond durable completion;
13. provider access can then be disabled;
14. replay succeeds with network access blocked;
15. derived indexes can be deleted and rebuilt;
16. all acquired artifact checksums verify;
17. the final corpus inventory is inspectable;
18. provider request and quota usage are summarized without secrets.

If the live provider is unavailable for reasons outside the implementation, preserve the evidence and report the task incomplete rather than substituting mocked success.

## Non-Goals

TASK-004 must not implement:

- native SEC EDGAR acquisition as a second production path;
- Investor Relations site retrieval;
- broad web crawling or scraping;
- open-ended historical backfill;
- every SEC form type;
- every issuer;
- XBRL parsing;
- filing-section extraction;
- exhibit interpretation;
- OCR;
- document chunking;
- embeddings or vector search;
- observations, derivations, enrichments, claims, positions, or projections;
- LLM integration;
- RAG;
- consulting briefs, reports, dashboards, or question answering;
- production schedulers or distributed workers;
- generalized credential management;
- generalized HTTP client frameworks;
- provider abstraction unsupported by current evidence;
- production deployment infrastructure.

Do not broaden the task merely because live data makes later product ideas visible.

## Architectural Boundaries

Codex has implementation discretion subject to these boundaries:

- fit the provider adapter behind the existing TASK-003 adapter contract;
- preserve repository-owned identity and persistence semantics;
- keep provider-specific code out of the acquisition engine and repository substrate;
- do not pass repository objects into the adapter;
- do not persist secrets or authorization material;
- do not make tests depend on live network access;
- do not commit full runtime corpus data;
- preserve deterministic bounded source profiles;
- preserve checkpoint ordering and append-only history;
- preserve offline replay and rebuild;
- use real integration evidence to justify any contract changes;
- document compatibility impact of any prior-contract change;
- avoid adding provider-specific branches to central engine logic;
- keep retries bounded and respectful of provider policy;
- keep the solution suitable for a single technical operator;
- preserve all existing quality gates and fixture behavior.

## Acceptance Criteria

TASK-004 is complete only when all of the following are true:

1. One real commercial SEC provider adapter is implemented behind the existing adapter boundary.
2. The actual provider and API surfaces used are documented.
3. Runtime authentication works through a non-persisted credential reference.
4. No secret value appears in tracked files, logs, patches, fixtures, manifests, or review artifacts.
5. STX and WDC governed source profiles are deterministic, bounded, and validated.
6. Repository-owned SEC filing identity is stable and documented.
7. Provider identifiers and URLs remain provenance rather than repository identity.
8. Real provider pagination and retrieval map correctly into existing engine contracts.
9. Network behavior includes timeouts, bounded retries, response validation, and sanitized diagnostics.
10. Offline tests cover provider mapping, pagination, authentication, quota, timeout, malformed response, and retrieval failures.
11. Normal project validation passes without credentials and without network access.
12. A real bounded STX/WDC corpus is acquired through the production engine.
13. Exact artifact bytes and checksums are preserved.
14. Real provenance and append-only history are inspectable.
15. Checkpoints do not advance beyond durable completion.
16. A second equivalent live run demonstrates idempotency.
17. The live corpus scope does not silently widen between runs.
18. Provider usage and quota evidence are captured proportionately and sanitized.
19. Provider access can be disabled after acquisition.
20. Replay succeeds with network blocked and credentials unavailable.
21. Derived indexes can be deleted and rebuilt from authoritative state.
22. All live corpus artifact integrity checks pass.
23. Any TASK-002 or TASK-003 contract change is narrow, justified, documented, and regression-tested.
24. Material live-integration lessons and alternatives are recorded.
25. Existing fixture adapters and all prior tests continue to pass.
26. No downstream extraction, knowledge, AI, or projection capability is implemented.
27. A complete independently auditable TASK-004 verification package is generated.
28. Final Git and branch state are explicitly reported.
29. No live-success claim is made without actual provider-backed evidence.

## Verification Requirements

Verification must include:

- focused adapter unit tests using sanitized recorded fixtures;
- provider-response mapping tests;
- SEC filing identity tests;
- pagination and continuation tests;
- deterministic source-bound tests;
- missing-credential tests;
- authentication-failure tests;
- rate-limit and quota tests;
- timeout and transient-failure tests;
- malformed-response tests;
- unexpected-content tests;
- secret-redaction tests;
- engine integration tests with the real adapter replaced by deterministic transport fixtures;
- all existing TASK-001 through TASK-003 tests;
- offline `make validate` with network blocked;
- isolated-tree validation without credentials;
- one gated live provider configuration check;
- one gated bounded live corpus run;
- one gated equivalent live rerun;
- corpus inventory comparison between runs;
- provider-disabled replay;
- index deletion and rebuild;
- artifact checksum verification;
- review-package secret scan;
- complete patch and scope validation.

Live checks must be clearly identified and must not run automatically as part of ordinary offline validation.

## Required Verification Package

Produce the complete TASK-004 review directory and ZIP under `.artifacts/review`.

The package must include, at minimum:

- `executive-summary.md`
- `implementation-summary.md`
- `architecture-decisions.md`
- `alternatives-considered.md`
- `provider-and-api-surface.md`
- `credential-and-secret-boundary.md`
- `sec-identity-model.md`
- `network-and-retry-model.md`
- `provider-response-mapping.md`
- `bounded-corpus-definition.md`
- `live-run-summary.md`
- `live-rerun-idempotency.md`
- `provider-usage-summary.md`
- `offline-replay-and-rebuild.md`
- `real-integration-lessons.md`
- `known-limitations.md`
- `deferred-work.md`
- `repository-tree.txt`
- `changed-files.txt`
- `git-status.txt`
- complete task-scoped `git-diff.patch`
- exact `validation-commands.md`
- raw focused-test output
- raw full offline-suite output
- raw isolated-tree validation output
- sanitized live configuration-check output
- sanitized live first-run output
- sanitized live second-run output
- corpus inventory and checksum reports
- raw provider-disabled replay output
- raw index-rebuild output
- review-package secret-scan output
- acceptance-criteria checklist
- machine-readable review manifest
- ZIP member listing
- ZIP SHA-256
- manifest checksum validation
- ZIP integrity result

### Verification-package quality rules

The package must:

- preserve raw evidence while sanitizing only secrets and credential-bearing request material;
- describe every redaction rule used;
- never contain an API key, token, authorization header, credential file content, or secret-bearing URL;
- include the exact bounded corpus definition;
- distinguish offline deterministic validations from live quota-consuming validations;
- include provider request counts and status outcomes where available;
- include all tracked and untracked TASK-004 changes in the patch;
- exclude full local corpus artifacts unless a narrowly selected non-sensitive sample is intentionally approved;
- distinguish authoritative evidence, derived indexes, runtime corpus data, and review artifacts;
- identify skipped or failed live checks honestly;
- avoid recursive package inclusion;
- validate its own checksums and ZIP integrity;
- be reproducible through documented commands.

A green offline test suite without successful live evidence is insufficient for completion.

## Codex Execution and Git Constraints

Codex is explicitly authorized to prepare the TASK-004 branch.

Starting from the repository supplied by the operator, Codex must:

1. verify it is in the RFI-1 repository;
2. verify the only authorized pre-existing untracked task input is `tasks/TASK-004.md`;
3. verify tracked files and the staged index are otherwise clean;
4. fetch current `origin/main` without rewriting local work;
5. ensure local `main` can be fast-forwarded to `origin/main`;
6. create and switch to:
   `agent/TASK-004-first-live-sec-acquisition`
7. preserve `tasks/TASK-004.md` across the branch transition;
8. confirm the branch starts from current `origin/main`;
9. implement TASK-004 only on that branch.

If the branch already exists, Codex must stop unless it can prove it is the intended clean TASK-004 branch based on current `origin/main`.

If branch creation or switching is blocked, stop and report the exact blocker. Do not implement on `main`.

Codex must not:

- commit;
- push;
- merge;
- rebase;
- reset;
- delete branches;
- clean the repository;
- stash unrelated work;
- modify Git configuration;
- create a pull request.

## Additional Execution Constraints

- Read the governing documents and prior acquisition ADRs before implementation.
- Treat `tasks/TASK-004.md` as an authorized task input.
- Stop on any other unexpected pre-existing change.
- Work only inside the RFI-1 repository.
- Use live network access only for explicitly identified TASK-004 provider operations.
- Keep ordinary validation offline.
- Never print or persist the credential.
- Do not read arbitrary user files to search for credentials.
- If the credential is absent, document the required runtime mechanism and stop before claiming completion.
- Respect provider rate limits, terms, and bounded scope.
- Do not silently weaken prior invariants.
- Do not broaden into hardening, IR retrieval, parsing, or knowledge development.
- Produce the complete verification package even when a live check fails.

## Expected Handoff

At completion, report:

- branch and HEAD;
- confirmation that the branch was created from current `origin/main`;
- actual provider used;
- runtime credential mechanism without the secret value;
- bounded STX/WDC corpus definition;
- live first-run result;
- live second-run idempotency result;
- request and quota summary;
- corpus document and artifact counts;
- SEC identity and provenance decisions;
- any prior-contract corrections;
- offline and live validation results;
- replay, rebuild, and integrity results with provider disabled;
- changed-file count;
- review directory and ZIP path;
- ZIP size, SHA-256, and integrity result;
- staged and unstaged state;
- known limitations and TASK-005 hardening recommendations;
- explicit confirmation that no secret was persisted;
- explicit confirmation that no downstream knowledge, AI, or projection capability was implemented;
- explicit confirmation that no commit, push, merge, rebase, reset, branch deletion, cleanup, Git-configuration change, or pull request was performed.
