# RFI-1 current architectural state

This document is the concise orientation artifact for the implemented repository. It describes
the state visible in the current branch; it is not a promise that every implemented subsystem is
part of the operating product. Start here before reading historical task tickets or broad design
studies.

## Documentation authority

Different repository records answer different questions. Use the narrowest applicable authority:

1. **Current behavior:** public contracts and committed implementation under `src/rfi/`, then
   executable tests and validation evidence.
2. **Accepted architectural intent:** accepted decisions under `docs/decisions/`, task invariants,
   and repository conventions. Code alone may be incidental or provisional.
3. **Current orientation and direction:** this document, `ARCHITECTURE.md`, `README.md`, and
   `ROADMAP.md`, reconciled against the first two levels.
4. **Work authorization and status:** `TASKS.md` plus the applicable ticket under `tasks/`.
   `BACKLOG.md` records possibilities and cannot authorize work.
5. **Historical provenance:** completed task reviews, older design guidance, task-ticket planning
   language, and the design study. These explain why a decision was made but do not override
   current executable facts.

When evidence conflicts, report the conflict. Do not make implementation conform to an older plan
without a newly authorized task. The imported-file hashes in `docs/design-baseline.json` prove
document provenance; they do not elevate old prose above repository behavior.

Two historical identifier collisions are preserved: there are two ADR-0024 files, two ADR-0026
files, and two unrelated TASK-058 tickets. Always cite the filename or milestone title as well as
the number. Renumbering accepted historical records would damage provenance.

## Classification vocabulary

Architecture, maturity, and composition are separate properties:

- **Product-integrated:** composed by the stable `rfi` CLI, local admin/API server, or shared Pull
  Workflow.
- **Implemented POC:** public contracts, implementation, and executable proof exist, but the
  stable application does not compose the capability into its normal workflow.
- **Provisional:** useful implementation exists, but scope, quality, transport, or operating
  evidence is deliberately narrow.
- **Blocked:** implementation exists but a known acceptance condition prevents supported
  operation.
- **Missing/deferred:** no implemented capability satisfies the described need.

“Complete” in a historical task record means its bounded milestone met its acceptance criteria. It
does not by itself mean production-ready, product-integrated, broad, or high quality.

## Operating product

RFI-1 currently ships as a local, single-operator Python application. The stable composition roots
are `rfi.cli`, `rfi.admin.server.create_admin_server()`, and
`rfi.pull.create_pull_workflow()`. They provide:

- initialization, explicit seed/import, configuration backup/restore, integrity verification,
  and a local foreground admin server;
- revisioned business concepts, canonical target-firm identity, effective source profiles, and
  externally managed firm configuration;
- a durable Pull Workflow shared by CLI, REST, and browser surfaces;
- immutable acquisition evidence, append-only observations and attempts, content deduplication,
  and repository-owned artifact inspection;
- deterministic SEC Form 10-K, 10-Q, 8-K, 20-F, and 6-K retrieval;
- bounded earnings-call transcript acquisition with explicit StockAnalysis provider dispatch,
  retained discovery learning, seed injection, and conservative coverage;
- repository-owned RSS/Atom sources, polling, unavailable-entry tombstones, fulfillment, firm-pull
  association, and aggregate RSS projection;
- bounded Linux/Lore mailing-list acquisition, resumable relationship closure, canonical
  cross-list lineage, process-local fetch progress/history, and operator inspection; and
- revisioned materialized artifact streams with canonical YAML, typed selection, DAG validation,
  atomic publication, lineage, rebuild, and CLI/browser operation.

SQLite is authoritative for current structured application state. Exact acquired bytes live in the
content-addressed filesystem. Version-controlled configuration and governance remain files.
Rebuildable indexes and UI projections are not independent authorities.

## Capability maturity and composition

| Capability | Implementation maturity | Product composition | Principal evidence / limitation |
|---|---|---|---|
| Repository foundation and validation | Complete for the repository workflow | Integrated | `Makefile`, `scripts/quality.py`, `scripts/review_package.py`, repository tests |
| SQLite structured state and immutable bytes | Usable with local/single-writer limits | Integrated | `rfi.storage`, `rfi.acquisition`, TASK-021 tests and ADR-0017 |
| Concepts and target firms | Complete for revisioned local catalogs | Integrated | `rfi.concepts`, `rfi.firms`, admin/CLI tests; calculated observations are not product-composed |
| Source profiles and external firm configuration | Complete with startup/manual reload semantics | Integrated | `rfi.source_profiles`, `rfi.firm_configuration`, TASK-041/048B/054/055 evidence |
| Pull Workflow | Complete for bounded local invocations | Integrated | `rfi.pull`; CLI, REST, and browser use the same workflow |
| Artifact query and isolated preview | Complete for retained evidence | Integrated | `rfi.artifacts`, admin artifact browser, TASK-018/019 tests |
| SEC numbered forms | Usable with recent-submissions and form-policy limits | Integrated | artifact-specific adapters; exact accession and older-history traversal remain deferred |
| SEC authoritative 10-K workflow | Complete as a bounded vertical slice | Integrated in CLI | `rfi.sec`; no continuous scheduler |
| Earnings transcripts | Usable with limitations | Integrated | StockAnalysis is the only provider; selection and discovery are bounded and coverage may be indeterminate |
| WDC Business Wire press releases | Implemented but operationally blocked | Registered in Pull Workflow, unsupported for live operation | fixture/browser-capture parsing passes; direct production transport is denied or times out |
| RSS/Atom feeds | Complete for public credential-free feeds | Integrated | `rfi.feeds`; external recurrence only, no authenticated feeds or redirect DNS pinning |
| Mailing-list evidence and workflow | Usable with bounded Lore/local-operation limits | Integrated | `rfi.mailing_lists`; no durable scheduler or global rate coordination |
| Revisioned artifact streams | Complete for bounded materialized projections | Integrated | `rfi.streams`; not a general workflow engine |
| Source objects | Complete contracts, narrow parser | Implemented POC | `rfi.source_objects`; SEC SGML/header structure only; task proof scripts compose it |
| Derived knowledge | Complete contracts, narrow ontology | Implemented POC | `rfi.knowledge`; deterministic issuer/filing ontology, independent generation storage |
| Governed retrieval/evidence packages | Complete contracts, provisional quality | Implemented POC | `rfi.retrieval`; deterministic local vectors, narrow corpus, no product composition |
| Model-guided intelligence | Complete bounded contracts, provisional reasoning quality | Implemented POC | `rfi.intelligence`; deterministic planner/reasoner substitutes, no live model adapter |
| Consulting workspace | Complete for the bounded local POC | Implemented POC | `rfi.workspace`; proof-script JSON workflow only, no application UI or upstream product composition |

## Public architectural contracts

The package exports in each subsystem `__init__.py` are the practical public Python boundary. The
most important slow-moving contracts are:

- acquisition inputs, results, interval coverage, trials, and repository receipts in
  `src/rfi/acquisition/`;
- canonical firms, source profiles, Pull Workflow results, feed definitions/runs, mailing-list
  manifests, stream revisions/runs, and artifact query objects in their corresponding packages;
- source-object and derived-knowledge reader/provenance contracts in `src/rfi/source_objects/` and
  `src/rfi/knowledge/`;
- retrieval queries, traces, evidence packages, and budgets in `src/rfi/retrieval/`;
- intelligence plans, claim authority, execution traces, and executor ports in
  `src/rfi/intelligence/`; and
- workspace journal and executor ports in `src/rfi/workspace/`.

The stable operator surface is documented in `docs/application-cli.md` and
`docs/operator-guide.md`. Task scripts are acceptance and diagnostic tools unless the stable CLI
guide explicitly identifies them as routine application commands.

## Established invariants

- Exact source evidence and its acquisition history remain distinct from derived knowledge,
  intelligence output, and operator annotations.
- Acquired bytes are immutable and content-addressed; repeated observations do not copy or mutate
  canonical content.
- Provider adapters do not own canonical persistence identity or write physical storage directly.
- Structured runtime state has one SQLite authority; browser pages, streams, feeds, and mailing-list
  projections do not create competing stores.
- Derived layers depend on public upstream contracts and retain provenance; upstream packages do
  not depend on intelligence or workspace code.
- Coverage is explicit and conservative. Successful candidates do not imply interval completeness.
- Stored external content is untrusted and inspected through repository-owned bounded reads and an
  isolated browser preview.
- Model output is non-authoritative. Every accepted claim must expose its authority class,
  evidence mapping, and uncertainty where applicable.
- Whatever downstream reasoning can consume must remain inspectable by an operator through the
  same governed evidence contracts.

## Genuine frontier

The principal missing product capability is composition, not the absence of POC classes. The
operating product does not yet transform acquired artifacts into source objects and knowledge,
build governed retrieval state, execute model-guided analysis, or save that work in a consulting
workspace. The next composition task must define lifecycle, rebuild, freshness, error, and operator
review behavior rather than merely call the existing proof scripts.

Other genuine gaps are broader semantic extraction, evaluated retrieval quality, a real governed
model adapter, polished investigation workflows, viable official press-release transport,
deployment/authentication, durable scheduling, multi-user/multi-writer coordination, monitoring,
and scale evidence. These are roadmap or backlog concerns until a task ticket authorizes work.

## Known ambiguities

- The concept catalog is product-integrated, while its in-memory observation/calculation service is
  only proven in tests/scripts. “Concepts are integrated” must not be read as a derived-knowledge
  pipeline claim.
- The WDC press-release adapter is registered in the Pull Workflow, but the TASK-066 evidence
  explicitly blocks supported live operation. Registration is not operational acceptance.
- Historical TASK-005 through TASK-008 records use “complete” for bounded architectural POCs.
  Their public contracts are real; their absence from the stable application is also real.
- The design study under `docs/design/` is research input, not proof that its proposed product
  composition exists.
