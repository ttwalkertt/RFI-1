# RFI-1 Repository-Wide Complexity and Robustness Review

Review date: 2026-08-05

Review basis commit: `45966d528cec1d49e42037c59f57eec5f3a61a29`

Branch: `main`

Evidence package: `docs/reviews/repo-wide-complexity-robustness/`

## Executive assessment

RFI-1 remains architecturally recognizable and unusually explicit about evidence authority,
provenance, fail-closed behavior, bounded acquisition, and repository inspection. The central
hybrid repository is backed by real transactional and restart tests, malformed data normally fails
closed, configuration reload is atomic, artifact bytes are immutable, cursors are revision-bound,
and acquisition policies expose partial and indeterminate outcomes rather than silently claiming
coverage.

The repository is not uniformly over-complex. Complexity is concentrated in four areas:

1. transcript discovery, resolution, provider dispatch, selection, and retrieval;
2. the generic acquisition engine;
3. mailing-list acquisition/query state;
4. the local HTTP composition and routing layer.

Two verified defects change the immediate posture. First, hybrid backup can report `PASS` while
producing an archive that cannot be restored when a write overlaps the interval between the SQLite
snapshot and content enumeration. Second, the production pull source identity includes the current
source-profile revision even though retained transcript discovery history is contractually required
to survive profile revisions. The existing TASK-056 test passes because it keeps a synthetic source
ID constant and therefore does not exercise production source identity derivation.

Recommendation: do not begin another transcript, persistence, or recovery feature milestone until
the backup consistency defect and stable logical-source identity defect are fixed in separate
bounded tasks. Other development can continue. This is a focused correction and consolidation
pause, not a repo-wide refactor.

Overall robustness: **Usable with material operational limitations**.

Overall complexity posture: **Concentrated architectural debt; manageable if extension pressure is
paused at the transcript/acquisition boundary**.

## Review method and limits

The review covered all tracked product Python modules, tests, scripts, governing architecture,
design principles, roadmap, task ledger, active TASK-065 ticket, operator documentation, ADRs,
task reviews, validation commands, and Git file-change history. Static AST metrics were combined
with targeted source inspection, repository search, focused tests, and deterministic offline
probes. Metrics support findings; they are not a composite quality score.

The repository contains 105 production Python files and 35,087 production Python lines, plus 64
test modules and 23,747 test Python lines. The largest production modules are
`discovery.py` (2,573 lines), `acquisition/engine.py` (1,869), `storage/sqlite.py` (1,512),
`mailing_lists/repository.py` (1,414), and `admin/server.py` (1,324). The largest functions include
`AcquisitionEngine._run_source` (1,030 lines; 118 AST branching nodes), `AdminHandler._api`
(582 lines; 137 branching nodes), `BoundedTranscriptDiscovery.discover` (468 lines; 98 branching
nodes), and `MailingListAcquisitionService._plan` (428 lines; 79 branching nodes).

The review did not perform live external-source acquisition, load/performance testing, process-kill
fault injection, disk-full testing, or multi-process write stress. Network-dependent correctness
was assessed through existing fixtures and contract tests. The local socket tests initially failed
under the filesystem/network sandbox and passed when rerun with loopback binding permitted; that
environmental restriction is not a repository failure.

## System map and authority boundaries

| Subsystem | Principal authority and responsibility | Important transitions | Highest-risk coupling |
| --- | --- | --- | --- |
| Governance/configuration | Version-controlled schemas, templates, discovery policy, external firm files; SQLite stores materialized immutable revisions | inspect -> validate -> atomic materialize -> current revision | External files, source-profile revisions, pull planning |
| Firms/concepts/source profiles | SQLite repositories own stable identity and immutable revision history | draft -> validate -> publish revision | Pull source identity and configuration reload |
| Acquisition engine | Adapter-neutral orchestration over repository ingress | discover -> deduplicate -> retrieve -> qualify/select -> retain -> checkpoint | Trial-oriented transcript extensions inside the generic engine |
| Immutable evidence | SQLite owns structured artifact/attempt/observation facts; content-addressed files own bytes | bytes first -> one structured transaction -> current document/checkpoint | Backup must snapshot both authorities consistently |
| Transcript acquisition | Orchestrator, generic IR discovery/resolver, provider registry/adapters, terminal selector | configured/learned/operator seed -> bounded resolution -> provider retrieval -> selection -> learning | `discovery.py`, engine state, source identity, repository anchor projection |
| SEC acquisition | Artifact-specific adapters over a shared bounded SEC provider | identity -> bounded listing -> exact document -> repository ingress | Runtime request identity and external format changes |
| Mailing lists | SQLite manifests/evidence plus derived discussions; process-local FIFO fetch queue | select -> fetch bounded context -> retain -> project -> publish | Raw SQL query projections and silently best-effort queue history |
| Streams | SQLite stream definitions/runs/memberships/lineage; finite schema registry | validate DAG -> save revision -> run dependency chain -> atomic publish | Mailing-list projections and repository-specific query seams |
| Pull workflow | Durable SQLite pull-run record and one process-local serialized executor | receive -> snapshot -> plan -> retrieve -> summarize | Daemon HTTP threads, restart reconciliation, shared execution lock |
| Operator console | Thin local HTTP/HTML surface over services | request -> normalized API result -> polling/inspection | One 582-line route dispatcher and heterogeneous error mapping |
| Knowledge/retrieval/intelligence/workspace | Deliberately independent portable or rebuildable stores/contracts | evidence -> source objects -> knowledge -> retrieval -> intelligence -> workspace journal | Older POC layers are less integrated with the current operator path |

The most important authority ambiguity is not duplicate persistence: it is identity. TASK-056 calls
`source_id` the stable logical configured-source identity, while the production pull workflow
derives it from a revision ID. The most important physical consistency boundary is the hybrid
SQLite/content snapshot used by backup.

## Findings

### RCR-001 — Hybrid backup can report success for an unrestorable archive

- Classification: **Confirmed defect**
- Severity / confidence: **High / High**
- Horizon / scope: **Immediate / subsystem**
- Governing property: a backup is a consistent, independently restorable snapshot of SQLite and
  all referenced immutable content (`docs/sqlite-structured-state-repository.md:106-123`).
- Evidence: `src/rfi/storage/backup.py:50-103` verifies live state, snapshots SQLite, then separately
  enumerates and copies the live content directory. There is no shared repository revision check,
  writer exclusion, or post-build restore-equivalence verification. The offline overlap probe
  injects one valid acquisition after the database snapshot and before content enumeration;
  `create_backup` returns `PASS`, while restore fails with `content inventory contains missing or
  orphaned objects`.
- Mechanism: the database snapshot and content member inventory can describe different authority
  revisions. A new content object copied after the database snapshot is an orphan relative to that
  snapshot; a referenced object not yet copied would be missing.
- Operational impact: the operator can believe data protection succeeded and discover only during
  recovery that the archive is unusable. This is credible recovery failure, so severity is High.
- Fact versus inference: the inconsistent archive is observed by the deterministic probe. The exact
  timing frequency in real operation is unknown.
- Existing detection: clean-state backup/restore tests pass; no concurrent-write or revision-change
  test exists, and backup does not verify its own completed archive.
- Smallest remediation: create a repository-owned hybrid snapshot protocol that binds a SQLite
  snapshot, a content inventory, and an authority revision; retry or fail if the revision changes,
  and independently verify the finished archive before reporting success. Do not combine this with
  orphan disposition policy.

### RCR-002 — Transcript learning is partitioned by source-profile revision

- Classification: **Confirmed defect**
- Severity / confidence: **Medium / High**
- Horizon / scope: **Near-term / subsystem**
- Governing property: TASK-056 requires discovery history to survive source-profile revisions and
  calls `(firm, logical configured source, adapter)` the stable key
  (`tasks/TASK-056-persistent-discovery-anchor-history.md:24-36,49-62`).
- Evidence: `src/rfi/pull/workflow.py:451-484,749-768` includes `revision_id` in the source-ID hash.
  `src/rfi/discovery.py:1413-1421` requests history using that source ID, and
  `src/rfi/acquisition/repository.py:326-339` requires an exact source-ID match. The probe records an
  anchor under profile r1, derives the otherwise-identical r2 source ID, and observes one r1 anchor
  and zero r2 anchors.
- Mechanism: changing any source-profile revision creates a new governed source identity. History
  remains durable but becomes undiscoverable to the next production pull.
- Operational impact: a routine configuration revision discards the effective learned-first
  behavior, increasing bounded discovery failure risk and external requests. Evidence is not lost.
- Fact versus inference: identity and lookup loss are observed. A missed real transcript is a
  plausible consequence, not demonstrated live.
- Existing detection: `tests/test_task056.py:225-251` publishes two profile revisions but queries a
  separately constructed constant `source-a`; it therefore proves repository key isolation, not
  production revision survival. Full validation currently accepts the defect.
- Smallest remediation: define one stable logical acquisition-source ID separately from immutable
  execution/configuration revision identity, preserve the revision on observations, and add an
  integrated pull-planning -> successful anchor -> profile revision -> next planning regression.

### RCR-003 — Pull execution has durable records but no truthful interruption/queue lifecycle

- Classification: **Robustness gap**
- Severity / confidence: **Medium / High**
- Horizon / scope: **Near-term / subsystem**
- Governing property: operator-visible run status should distinguish queued, running, partial,
  interrupted, and terminal work; restart should not leave an apparently active operation forever.
- Evidence: `src/rfi/admin/server.py:949-976` creates a durable `running` record and starts an
  untracked daemon thread. `src/rfi/pull/workflow.py:73,140-145` serializes all runs and injected
  transcript acquisitions behind one non-fair process lock. `src/rfi/pull/repository.py` provides no
  startup reconciliation. The probe confirms a `running` record remains `running` after reopen.
  `docs/pull-workflow.md:178-196` explicitly documents the limitation.
- Mechanism: overlapping REST requests are all labeled running while all but one wait invisibly;
  process exit leaves them permanently running; there is no cancel/retry/reconcile API. If an
  unexpected exception occurs after completed firms, `src/rfi/pull/workflow.py:203-225` retains the
  firms but resets the summary to empty and marks the whole run failed, concealing partial work in
  the headline status.
- Operational impact: indefinite browser polling, ambiguous rerun decisions, invisible queueing,
  and misleading zero summaries after partial retained work.
- Fact versus inference: persistent running state and code paths are observed; operator double-submit
  frequency and process-kill frequency are unknown.
- Existing detection: tests cover in-process progress and normal aggregation, but not process
  restart, overlapping run order, cancellation, or exception-after-one-firm truthfulness.
- Smallest remediation: introduce explicit `queued`, `running`, `interrupted`, and terminal
  reconciliation semantics within the existing pull-run repository; do not build a general job
  framework or merge this with mailing-list queue work.

### RCR-004 — Mailing-list queue silently loses its promised durable history

- Classification: **Robustness gap**
- Severity / confidence: **Medium / High**
- Horizon / scope: **Near-term / local**
- Governing property: terminal fetch history and non-progress events are durable operator evidence;
  persistence failures must be visible and normalized.
- Evidence: `src/rfi/mailing_lists/queue.py:453-491` catches every exception from
  `record_fetch_event` and `record_fetch_history` and does nothing. The in-memory job is still shown
  as terminal. `tests/test_task032.py` covers successful persistence extensively but has no negative
  history-store control.
- Mechanism: database busy, corruption, schema, or programming errors erase terminal telemetry
  without changing the operator-visible success/failure result or adding a diagnostic.
- Operational impact: after restart, investigation history can be absent even though the prior UI
  claimed a terminal operation; evidence artifacts may remain correct, but recovery context is lost.
- Fact versus inference: exception swallowing is observed. The probability of a real persistence
  failure is unknown.
- Existing detection: none for a failing history store.
- Smallest remediation: make terminal history publication part of terminalization semantics or
  retain an explicit `history_persistence_failed` diagnostic/status. Keep progress-event
  coalescing/best-effort behavior separate if desired.

### RCR-005 — Transcript behavior is concentrated in a stateful multi-generation orchestration module

- Classification: **Complexity hotspot**
- Severity / confidence: **Medium / High**
- Horizon / scope: **Near-term / subsystem**
- Governing property: provider selection, discovery, qualification, retained learning, terminal
  selection, and ingress each have one clear owner and remain replaceable behind stable contracts.
- Evidence: `src/rfi/discovery.py` is 2,573 lines and contains policy loading, HTTP search/parsing,
  graph discovery, bounded transport, resolution, trial planning, terminal selection, the pull
  adapter, provider dispatch, generic IR retrieval, diagnostics, and compatibility entry points.
  Its `BoundedTranscriptDiscovery.discover` is 468 lines; the adapter `_discover` is 293 lines.
  Transcript extension/repair tasks TASK-048 through TASK-065 account for 26 commits touching this
  file. `src/rfi/acquisition/engine.py:_run_source` has also grown to 1,030 lines to support both
  classic paginated adapters and trial/terminal-selection adapters.
- Mechanism: invocation state (`_budgets`, `_provider_adapters`, `_validated_expected`), policy,
  provider dispatch, generic discovery, and result translation are coordinated through ordering and
  shared mutable dictionaries. Correct changes require cross-reading engine, discovery, provider,
  repository, and pull workflow.
- Operational impact: regressions are likely to appear at seams such as the TASK-056 identity bug;
  tests increasingly patch private internals and reproduce production orchestration subclasses.
- Fact versus inference: sizes, responsibilities, mutable state, and history are observed. Increased
  future defect probability is an architectural inference.
- Existing detection: transcript task tests are broad and valuable, but mostly task-layered and
  implementation-coupled; no architectural test enforces owner boundaries.
- Smallest remediation: after RCR-002, freeze behavior with characterization tests, then separate
  trial planning, invocation-scoped budget/context, generic IR resolution, provider dispatch, and
  result translation behind existing public contracts. Do not redesign selection or persistence in
  the same task.

### RCR-006 — Mailing-list consumers depend on repository SQL rather than complete fact contracts

- Classification: **Architectural debt**
- Severity / confidence: **Medium / High**
- Horizon / scope: **Defer until after immediate fixes / subsystem**
- Governing property: repository/query contracts are the only supported storage-consumer boundary,
  and callers do not own persisted schema (`docs/sqlite-structured-state-repository.md:15-17,125-131`).
- Evidence: `MailingListRepository.rows` accepts arbitrary SQL and is described as private
  (`src/rfi/mailing_lists/repository.py:1217-1225`), but `MailingListQueryService` issues at least 14
  SQL statements through it (`src/rfi/mailing_lists/service.py:943-1127`). Stream projection refresh
  also relies on a generic `rows` seam (`src/rfi/streams/registry.py:38-61`).
- Mechanism: table/column shape, joins, JSON decoding, and query semantics are owned partly by the
  service layer. Schema migration or alternative persistence requires editing consumers and makes
  malformed historical rows surface outside repository normalization.
- Operational impact: migration and query regressions; this is not a confirmed current correctness
  failure.
- Existing detection: realistic query tests cover present SQLite state, but no storage-independent
  contract fixture protects the boundary.
- Smallest remediation: add typed repository query methods or one repository-owned query adapter
  returning complete domain facts, then remove arbitrary SQL from service consumers. Do not combine
  with acquisition or transcript consolidation.

### RCR-007 — HTTP routing and error normalization are one growing decision table

- Classification: **Complexity hotspot**
- Severity / confidence: **Low / High**
- Horizon / scope: **Defer / local**
- Governing property: HTTP remains a thin adapter with consistent method, validation, status, and
  error semantics.
- Evidence: `AdminHandler._api` is 582 lines with 137 branching nodes and 80 returns;
  `AdminHandler._dispatch` adds route/page/error branching. `AdminConsole.__init__` receives 13
  service dependencies plus address/state. Error classification partly uses typed error codes and
  partly message substring inspection (`src/rfi/admin/server.py:470-531,1191-1215`).
- Mechanism: every new endpoint extends one order-sensitive conditional and central exception map.
- Operational impact: wrong route precedence or inconsistent status/error vocabulary is easier to
  introduce, but no current collision was confirmed.
- Existing detection: endpoint tests are strong but scattered among task files.
- Smallest remediation: extract declarative route groups or small handler methods while preserving
  the single composition root and exact response contracts. Avoid a web-framework migration.

### RCR-008 — Validation is broad but does not detect architectural or cross-task contract drift

- Classification: **Documentation or test mismatch**
- Severity / confidence: **Medium / High**
- Horizon / scope: **Near-term / subsystem**
- Governing property: validation should detect invariant regressions rather than preserve only task
  implementations.
- Evidence: 56 of 64 test modules are task-named; 14 test modules exceed 500 lines. The largest are
  TASK-064 (1,337), TASK-057 (1,225), and TASK-060 (940). Tests reference private members heavily,
  including direct `_database` transactions and private engine/result helpers. The TASK-056
  completion review claims production revision survival, yet its test does not use production
  identity derivation. `scripts/quality.py` is a useful parse/style/annotation-policy checker, not a
  semantic type checker. `scripts/check_baseline.py` checks design hashes and a hard-coded file
  inventory, not dependency direction or authority access.
- Mechanism: each milestone adds vertical evidence without a smaller invariant suite spanning task
  boundaries. Private seams allow tests to pass while composition behavior differs.
- Operational impact: full `make validate` can be green despite RCR-001 and RCR-002.
- Fact versus inference: the two missed defects and tool behavior are observed; suite maintenance
  cost is inferred from concentration and private coupling.
- Existing detection: by definition absent for the two confirmed defects.
- Smallest remediation: add a compact invariant suite for stable identities, hybrid snapshot
  consistency, restart lifecycle, repository-only persistence access, and interface equivalence.
  Keep historical task tests, but stop using them as the only acceptance layer.

### RCR-009 — Governing documentation and task status have drifted from current implementation

- Classification: **Documentation or test mismatch**
- Severity / confidence: **Low / High**
- Horizon / scope: **Immediate / local**
- Governing property: repository documents refresh the architect and operator's current mental model.
- Evidence: `docs/operator-guide.md:1-5` says it covers through TASK-031 while it contains later
  transcript behavior; `docs/sqlite-structured-state-repository.md:32-52` says schema version 2 and
  lists an early table set while runtime schema is version 15; `TASKS.md` ends at TASK-064 even though
  TASK-065 is implemented, reviewed, tested, and is the latest commit history. `scripts/check_docs.py`
  validates links and help anchors, not factual/version coherence.
- Mechanism: milestone documentation is appended locally, but canonical summaries and task ledger
  are not consistently advanced.
- Operational impact: recovery planning and future task scoping start from stale facts; runtime
  behavior is unaffected.
- Existing detection: none.
- Smallest remediation: one documentation-only reconciliation with executable assertions for schema
  version and roadmap/task ledger completeness where practical.

## Hotspot inventory

| Hotspot | Evidence | Assessment |
| --- | --- | --- |
| Transcript discovery/provider path | 2,573-line module; repeated TASK-048–065 extension; multiple long stateful functions | Problematic accidental complexity around justified domain complexity; consolidate after defects |
| Acquisition engine | 1,030-line `_run_source`; classic and trial-oriented protocols; selection/checkpoint/diagnostics state | Problematic control-flow concentration; domain lifecycle is justified, implementation concentration is not |
| Mailing-list repository/service | 1,414 + 1,200 lines; complex source/canonical/occurrence/relationship scopes | Much complexity is justified by provenance and migration semantics; raw SQL consumer seam is debt |
| SQLite schema/migrations | 1,512 lines; schema version 15; explicit additive migrations and validation | Large but acceptable centralization; migration fixtures are uneven and need invariant coverage |
| Admin server | 582-line route method and 14-parameter constructor | Straightforward but fragile extension point; local extraction is warranted, framework replacement is not |
| Pull workflow | 862 lines; durable stages plus adapter/result translation | Understandable for normal execution; restart/queue/exception semantics are incomplete |
| Task tests and review generators | 56 task test modules; 50 task-specific review generators | Strong audit trail but high duplication and composition blind spots; preserve evidence, add invariant layer |
| Workspace/knowledge/retrieval stores | Separate file-backed authorities predating SQLite | Acceptable by explicit architecture; not hidden acquisition authority and not current operator hot path |

## Robustness matrix

Legend: **Strong** = explicit and well tested; **Partial** = bounded/documented limitation; **Gap** =
actionable weakness; **N/A** = not a meaningful workflow property.

| Workflow | Interruption | Retry | Duplicate | Stale state | Malformed input | Concurrency | Restart |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Startup/open | Strong fail-closed schema/integrity checks | N/A | Idempotent init | Strong incompatible/mixed detection | Strong | Partial single-host writer | Strong migrations, except stale docs |
| Firm configuration reload | Transactional rollback | Explicit operator retry | Repeated reload may append revisions by contract | Strong byte fingerprint notice | Strong complete-set validation | Strong process-local overlap rejection | Strong materialized state |
| Pull workflow | Gap: daemon exit leaves running | Manual new run; no resume | Repository ingress idempotent; request not deduped | Profile snapshot is strong | Strong request/profile checks | Gap: invisible serialized waiters | Gap: no reconciliation |
| SEC acquisition | Structured transaction; orphan detectable | Bounded provider retries | Strong candidate/artifact identity | Checkpoints | Strong fail-closed adapter validation | Process-local | Strong evidence/checkpoint state |
| Generic transcript acquisition | Structured transaction | Bounded trials and retrieval | Strong candidate/occurrence separation | Gap across profile revisions | Strong selection/provider validation | Serialized by pull lock | Evidence strong; learning lookup gap |
| StockAnalysis provider | Same ingress | Provider-local bounded retries | Strong stable candidate identity | Retained artifacts hydrated | Strong URL/content gates | Invocation context is stateful | Fixture replay strong |
| Mailing-list fetch | Cooperative safe checkpoints | Durable frontier | Duplicate jobs suppressed, evidence idempotent | Overlap windows explicit | Strong parsing/quarantine | Strong single FIFO queue | Queue resets; frontier/history durable, except silent history failure |
| Stream publication | Atomic all-or-none component publication | Rerun/rebuild | Membership identity/lineage | Current revision/upstream checks | Strong DAG/schema checks | Local writer serialization | Strong durable runs/memberships |
| Artifact inspection | Read-only | N/A | Observation navigation explicit | Strong revision-bound cursor rejection | Strong query/range validation | Concurrent readers supported | Strong if bytes verify |
| Backup/restore | Failed restore cleans destination | Operator rerun | Destination overwrite rejected | Gap: no shared hybrid snapshot revision | Strong archive/member validation | Defect under overlapping write | Clean archives restore strongly |
| Workspace journal | Partial files detected/quarantined | Explicit append/recovery | Hash-chain identity | Open executions visible | Strong fail-closed verification | Single writer only | Strong append-only replay |

## Test and validation assessment

### Strengths

- Tests exercise real temporary SQLite repositories, immutable content, migrations, restart reads,
  byte tampering, stale cursors, rollback, duplicate identity, and API/CLI equivalence.
- Negative controls are common for malformed adapters, unsafe URLs, provider mismatch, conflicting
  evidence, missing bytes, unsupported state, cancellation, retry bounds, and partial coverage.
- The transcript suite now covers provider-local parsing, explicit provider dispatch, durable
  provider learning, terminal selection, and retained-artifact replay.
- `make validate` is broad: unit discovery, offline end-to-end proofs, style/annotation policy,
  import, docs links, baseline inventory, and source archive build.
- Review-package verification has meaningful tamper and consistency tests.

### Blind spots

- No hybrid backup/write overlap or post-build restore-equivalence test.
- No integrated test of logical source identity across real source-profile revisions.
- No pull process-restart reconciliation, overlapping request lifecycle, cancellation, or
  exception-after-partial-success test.
- No negative-control history store for the mailing-list queue.
- Architectural checks do not enforce dependency direction, forbid arbitrary consumer SQL, or
  compare documented schema/task status with runtime facts.
- Task-specific tests often patch private methods or construct state below the composition boundary.
- Full validation is deterministic offline, but it is long and gives equal prominence to historical
  proofs and current invariant coverage; failures can be harder to localize.

### Recommended invariant-level additions

1. Hybrid snapshot remains restorable while a controlled writer commits before, during, and after
   snapshot boundaries.
2. Successful transcript learning remains first in planning after an actual profile revision and
   process reopen.
3. Pull startup marks orphaned running records interrupted and preserves completed-firm summary.
4. Queue terminalization visibly fails or degrades when durable history publication fails.
5. Repository consumer boundary test rejects direct SQL outside repository/query adapter modules.
6. Canonical docs assert current runtime schema and latest completed task.

## Remediation roadmap

### Task A — Make hybrid backups revision-consistent

- Objective: never report success unless the archive represents one self-consistent hybrid authority
  snapshot and independently verifies.
- Architectural boundary: storage backup/restore plus repository revision protocol only.
- Principal invariant: every archived content member is referenced by the archived database and
  every archived database reference has exactly one verified member.
- In scope: stable revision/inventory capture, bounded retry or explicit concurrent-change failure,
  post-build verification, deterministic overlap tests.
- Non-goals: orphan repair, retention policy, PostgreSQL, scheduling, incremental backup.
- Required tests: writes at each snapshot phase, missing/orphan injection, self-verification,
  restore equivalence, clean backup regressions.
- Regression surface: acquisition content publication, CLI backup/restore, SQLite WAL reads.

### Task B — Define stable logical acquisition-source identity

- Objective: preserve learning/checkpoint scope across configuration revisions without conflating
  immutable execution snapshots.
- Architectural boundary: pull source identity, governed-source registration, anchor/checkpoint key
  semantics, compatibility for existing rows.
- Principal invariant: profile revision changes preserve logical-source learning while every attempt
  retains the exact acquisition-time revision.
- In scope: explicit logical ID, compatibility rule, integrated profile-revision tests.
- Non-goals: transcript ranking, provider dispatch, discovery budgets, repository repair.
- Required tests: r1 success -> r2 planning/reopen, source/firm/adapter isolation, historical rows,
  checkpoint behavior.
- Regression surface: source IDs, governed sources, checkpoints, artifact observations, pull details.

### Task C — Reconcile interrupted and overlapping pull runs

- Objective: expose truthful queued/running/interrupted/partial terminal states and deterministic
  operator recovery.
- Architectural boundary: pull workflow and pull-run repository; HTTP remains thin.
- Principal invariant: no persisted run claims active execution when no executor owns it.
- In scope: startup reconciliation, queue state or explicit conflict, cancellation/retry semantics,
  partial-summary preservation.
- Non-goals: general scheduler, multi-host workers, mailing-list queue unification.
- Required tests: process-reopen simulation, two overlapping requests, cancellation checkpoints,
  exception after one completed firm, idempotent terminal read.
- Regression surface: REST polling, CLI synchronous runs, seed-injection lock behavior.

### Task D — Make mailing-list terminal telemetry honest

- Objective: prevent silent loss of durable terminal history/events.
- Architectural boundary: process-local fetch queue and history port.
- Principal invariant: terminal state explicitly records whether durable history publication
  succeeded.
- In scope: normalized persistence error, visible degraded state/diagnostic, negative control.
- Non-goals: durable queue restoration, general monitoring, pull workflow changes.
- Required tests: failing event store, failing history store, close/restart, successful regressions.
- Regression surface: queue snapshots, operator labels, history retention.

### Task E — Consolidate transcript invocation responsibilities

- Objective: reduce change amplification after Tasks B and C freeze behavior.
- Architectural boundary: `rfi.discovery`, transcript provider registry, and acquisition engine ports.
- Principal invariant: planning, provider dispatch, qualification/selection, persistence, and
  diagnostics retain exactly one owner each.
- In scope: characterization tests and extraction of invocation-scoped collaborators.
- Non-goals: new providers, new search, ranking changes, persistence migration, UI changes.
- Required tests: all TASK-057–065 invariants plus owner/dependency checks.
- Regression surface: every transcript acquisition mode; therefore this must not be combined with
  Tasks A–D.

### Task F — Close mailing-list query contracts and reconcile canonical docs

- Objective: remove arbitrary consumer SQL and restore accurate architectural/operator status.
- Architectural boundary: mailing-list repository/query adapter and documentation tooling.
- Principal invariant: consumers receive typed complete facts without persisted-schema knowledge.
- In scope: typed query methods, storage-independent fixtures, schema/task/operator doc updates.
- Non-goals: mailing acquisition changes, projection redesign, web framework changes.
- Required tests: query equivalence, malformed historical row normalization, documentation facts.
- Regression surface: mailing browser, stream projection refresh, operator help.

Suggested order: **A, B, C, D, E, F**. Tasks A and B should block related new feature work. Tasks A
and B must remain separate because they protect different authorities and have unrelated regression
surfaces. Task E must follow B and C so extraction does not hide behavioral changes.

## Deferred or rejected concerns

- **Large SQLite module:** accepted for now. Schema and migration ownership are centralized, and many
  migrations have realistic table-removal/backfill tests. Split only around a demonstrated ownership
  boundary, not line count.
- **Separate workspace/knowledge/retrieval stores:** accepted. They are explicitly independent,
  portable, non-competing authorities or rebuildable projections, not accidental legacy fallback.
- **Generic IR and StockAnalysis transcript implementations:** accepted as two source behaviors.
  The problem is their coordination in one stateful adapter, not the existence of provider-specific
  parsing.
- **Exact duplicate firm schema files:** accepted while byte equality is enforced by baseline/tests;
  packaged runtime and documentation copies serve different distribution roles.
- **No multi-host writer/database server:** accepted. Current evidence supports a local single-writer
  application; the trigger for PostgreSQL has not been reached.
- **Intentional content orphan after structured rollback:** the bytes-first protocol is defensible
  and fail-closed. However, operational orphan disposition remains unresolved. It should receive a
  separate policy task only after backup consistency is fixed; automatic deletion is rejected.
- **External-source format drift:** provider adapters have bounded parsing, content gates, explicit
  failure classes, and fixtures. Live variance remains unproven but no additional defect was
  confirmed in this offline review.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Governance and configuration | Versioned policy/templates and atomic materialization | Complete, with stale canonical docs |
| Firms, concepts, source profiles | Stable identity and immutable revisions | Complete |
| Immutable acquisition repository | Structured facts, byte authority, provenance, checkpoints | Usable with limitations |
| Hybrid backup/restore | Portable verified recovery | **Blocked by RCR-001 for overlapping writes** |
| SEC acquisition | Deterministic artifact-specific retrieval | Complete for supported forms |
| Transcript acquisition | Bounded discovery/provider resolution/selection/learning | Usable with limitations; RCR-002 and complexity debt |
| Mailing-list acquisition | Bounded context, resumability, canonical lineage | Usable with limitations |
| Streams | Revisioned DAG and atomic membership publication | Complete for current schemas |
| Pull workflow | Shared CLI/REST/GUI acquisition lifecycle | Usable with limitations; restart lifecycle incomplete |
| Operator console | Local inspection and administration | Usable with limitations |
| Knowledge/retrieval/intelligence | Governed downstream contracts | Provisional quality, not current review risk center |
| Workspace | Independent append-only consulting journal | Usable with limitations |
| Validation/review tooling | Reproducible historical evidence and broad offline checks | Usable with limitations; invariant layer needed |

Architectural change introduced by this review: none to production behavior. The review adds only
read-only metrics/probe tooling and evidence artifacts. The next architectural milestone should be
Task A, hybrid backup consistency, followed by Task B, stable logical acquisition-source identity.
