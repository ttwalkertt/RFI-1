# TASK-068 architectural review — repository reality reconciliation

## Executive summary

TASK-068 reconciles RFI-1's governing and orientation documentation with committed contracts,
composition roots, tests, accepted decisions, and completed task evidence. No product capability or
architectural refactor was introduced.

The central correction is that RFI-1 is neither acquisition-only nor an end-to-end research
product. It has a product-integrated local acquisition/evidence application and a separately
implemented chain of downstream POCs for source objects, derived knowledge, retrieval,
intelligence, and consulting workspaces. The updated documents state both facts and identify
product composition as the principal engineering frontier.

[`current-state.md`](current-state.md) is the new concise orientation artifact. It defines the
documentation authority order, maturity vocabulary, operating product, capability matrix, public
contract families, established invariants, genuine frontier, and known ambiguities.

## Inventory method

The reconciliation inspected the complete product package, all subsystem exports and contract
files, stable CLI and admin/Pull composition roots, all test modules, root guidance, downstream
subsystem guidance, accepted ADR filenames, task-ticket status/index drift, recent completed-task
reviews, build/validation tooling, and Git history/state.

The machine-readable `scripts/task068_architecture_inventory.py` independently records:

- public contract classes across 15 subsystem contract packages;
- the stable top-level CLI commands and integrated admin pages;
- imports at the CLI, admin, and Pull Workflow composition roots;
- absence of source-object, knowledge, retrieval, intelligence, and workspace imports from those
  stable composition roots;
- presence of TASK-005 through TASK-008 proof scripts and focused tests;
- TASK-005/006/007/008/067 test counts; and
- historical ADR/task identifier collisions.

This evidence demonstrates that classifications were derived from repository behavior and
composition, not by comparing documents with one another.

## Documentation drift findings

| Drift | Repository evidence | Reconciliation |
|---|---|---|
| README described acquisition as the exclusive current effort | `rfi.knowledge`, `rfi.retrieval`, `rfi.intelligence`, and `rfi.workspace` exist with public exports/tests | README now distinguishes integrated acquisition/evidence from downstream implemented POCs |
| README marked existing root files as planned | `ARCHITECTURE.md` and `ROADMAP.md` are committed governing files | Removed planned labels and replaced the index with an authority-oriented path |
| ROADMAP called Phase 0 acquisition the current phase | Implemented/tested layers exist through TASK-008, while product composition stops earlier | Roadmap now begins from the actual baseline and identifies composition/quality/product/operations frontiers |
| ARCHITECTURE mixed durable boundaries, task chronology, and maturity | Stable composition roots omit the downstream POCs even though their packages exist | Architecture now separates layers, authorities, invariants, composition, and current limitations |
| TASKS omitted multiple implemented/authorized tickets | Ticket files, tests, reviews, and Git history exist for omitted milestones | TASKS now indexes every extant ticket and distinguishes POC, ready, blocked, and complete states |
| Early ticket `Ready` headers contradicted later implementation evidence | Current tests/reviews and mainline code demonstrate completed bounded milestones | TASKS is explicitly the current status authority; historical ticket scope remains unchanged |
| TASK-006 said intelligence/workspace were not started | TASK-007/008 packages, tests, and proof scripts exist | Downstream status summary now says implemented POC, not product-integrated |
| TASK-007 said workspace was not started | `rfi.workspace`, TASK-008 tests, and workspace proof script exist | TASK-007 guidance now records implemented POC and remaining composition/UI gap |
| Root package docstring said intelligence/workspace were absent | Both packages are public and tested | Docstring now states implemented but not product-composed |
| Backlog said 10-Q/8-K/foreign-issuer forms were absent | TASK-022 adapters cover 10-Q, 8-K, 20-F, and 6-K | BLG-004 now retains only genuinely missing form families |
| Business Wire registration could be mistaken for acceptance | Pull factory registers the adapter; TASK-066 review explicitly blocks live operation | Current state, README, architecture, roadmap, TASKS, and backlog preserve the blocked classification |

## Repository capability inventory

### Product-integrated

- local CLI/admin/API lifecycle, concepts, firms, source profiles, and external firm configuration;
- SQLite structured authority, content-addressed immutable evidence, backup/restore, and integrity;
- shared Pull Workflow, artifact query/preview, SEC numbered forms and 10-K workflow;
- bounded StockAnalysis transcripts, learning inspection, and seed injection;
- feeds, mailing-list workflows, canonical lineage, fetch history, and revisioned streams; and
- shared browser/operator help and repository projections.

### Implemented POCs

- SEC structural source objects and exact-span provenance;
- versioned issuer/filing knowledge and correction/supersession;
- governed retrieval, evidence packages, replaceable local vectorizers, and inspection;
- bounded intelligence planning/reasoning contracts with deterministic substitutes; and
- consulting investigation journal, comparison, notes, export, backup, and restore.

### Provisional, blocked, missing, or deferred

- transcript support is one-provider and bounded; coverage can remain indeterminate;
- WDC Business Wire acquisition is implemented but operationally blocked;
- source-object/knowledge semantics are narrow and retrieval/model quality is not validated;
- the downstream POC chain is not composed into the stable application;
- frontier-model integration, semantic answer evaluation, polished consulting UI, authentication,
  scheduling, multi-user/multi-writer operation, monitoring, and production deployment are absent.

The full capability maturity matrix is in [`current-state.md`](current-state.md).

## Documentation authority model

Current behavior is determined first by public contracts/committed implementation and then by
executable tests/validation evidence. Accepted ADRs, task invariants, and completed evidence supply
architectural intent. Current orientation documents reconcile those facts. Roadmaps, historical
plans, reviews, and the design study cannot override them.

Work authorization remains separate: `TASKS.md` plus the applicable ticket authorize work;
`BACKLOG.md` does not. Imported design hashes prove provenance rather than immutable authority.

Historical collisions are preserved rather than renumbered: cite both ADR-0024/0026 files and both
TASK-058 tickets by filename or title.

## Capability maturity matrix

| Architectural layer | Maturity | Product composition | Review conclusion |
|---|---|---|---|
| Configuration/application shell | Complete for local operation | Integrated | Stable CLI/admin roots and shared services exist |
| Acquisition and immutable evidence | Complete contracts; source-specific limits | Integrated | Current product center of gravity |
| Artifact/feed/mail/stream projections | Complete for bounded local workflows | Integrated | SQLite/evidence authorities preserved |
| Source objects | Narrow but complete POC contract | Isolated | SEC structure only; proof scripts/tests compose it |
| Derived knowledge | Narrow but complete POC contract | Isolated | Issuer/filing ontology only |
| Retrieval/evidence packages | Complete contract; quality provisional | Isolated | Local deterministic vector candidates |
| Intelligence | Complete bounded contract; quality provisional | Isolated | Deterministic planner/reasoner; no live model adapter |
| Consulting workspace | Complete bounded local POC | Isolated | No stable application UI/composition |
| WDC press releases | Implemented, blocked | Registered but unsupported live | Transport viability prevents operational acceptance |

## Before/after contradiction summary

Before TASK-068, a new agent could reasonably infer either that only acquisition existed or that
TASK-005 through TASK-008 were complete product layers, depending on which document it opened.
After TASK-068, all entry points use the same three-axis statement:

1. the architectural layer exists;
2. its maturity may be complete only within a bounded POC; and
3. product composition is independently integrated or isolated.

The roadmap no longer repeats obsolete historical phases, and task completion no longer implies
product or production readiness.

## Changed-file inventory

- Root orientation/governance: `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `TASKS.md`,
  `BACKLOG.md`.
- Current authority/orientation: `docs/current-state.md`, `docs/design-baseline.md`, and updated
  `docs/design-baseline.json` integrity metadata.
- Material downstream reconciliation: `docs/governed-retrieval-and-source-browser.md`,
  `docs/model-guided-source-grounded-intelligence.md`, `docs/development.md`, and the root package
  documentation string.
- Task completion/review: TASK-068 ticket and this review.
- Reproducible evidence/package tooling: `scripts/task068_architecture_inventory.py`,
  `scripts/generate_task068_review.py`, and the `Makefile` review target.

No implementation module, persistence schema, UI asset, runtime configuration, public contract, or
test behavior changed. The only file under `src/rfi/` changed is the package documentation string.

## Roadmap reconciliation

The roadmap now starts from actual repository capability and orders the frontier by dependency:

1. compose evidence into governed research workflows;
2. evaluate and broaden semantic, retrieval, and model quality;
3. establish usable consulting product composition;
4. resolve source-specific acquisition gaps, especially press-release transport; and
5. harden operations when usage supplies deployment/scale requirements.

These directions do not authorize implementation. Concrete gaps were added as BLG-008 through
BLG-011.

## Task guidance reconciliation

`TASKS.md` now includes all extant tickets, the duplicate TASK-058 warning, TASK-048A/B follow-ons,
the unimplemented TASK-033/TASK-049 ready work, the TASK-005 through TASK-008 POC classification,
and TASK-066's operational block. Historical ticket bodies remain preserved.

## Evidence supporting capability claims

| Claim | Primary evidence |
|---|---|
| Stable local product composition | `src/rfi/cli.py`, `src/rfi/admin/server.py`, `src/rfi/pull/__init__.py` |
| Public architectural contracts | subsystem `contracts.py` and package exports under `src/rfi/` |
| Downstream layers exist | `rfi.source_objects`, `rfi.knowledge`, `rfi.retrieval`, `rfi.intelligence`, `rfi.workspace` |
| Downstream layers are isolated from stable product | composition-root import inventory plus TASK-005–008 proof scripts |
| Integrated feeds | `rfi.feeds`, CLI/admin/Pull composition, `tests/test_task067.py` |
| Integrated acquisition/evidence contracts | `rfi.acquisition`, `rfi.artifacts`, Pull/SEC/mail/stream/feed tests |
| Business Wire is blocked | Pull registration plus `docs/TASK-066-review.md` direct-transport evidence |
| Historical authority ambiguity | duplicate ADR-0024/0026 and TASK-058 filenames in inventory JSON |

## Validation and results

The final commit-aware package runs and captures:

- architecture inventory and contract/composition assertions;
- local Markdown link/reference validation;
- design-baseline hash, structure, and repository-boundary validation;
- focused TASK-005/006/007/008/015/018/021/064/066/067 tests supporting documented claims;
- committed-range `git diff --check`;
- an explicit documentation-only scope audit; and
- full repository-standard `make validate`.

The generated `validation/results.json` records each exact command and exit code. Complete raw
outputs are packaged. The focused claim suite passes 126 tests. The full gate passes 680 tests,
lint, formatting, lightweight typing, imports, documentation/link checks, baseline integrity,
deterministic demos/proofs, source-archive build, and repository integrity validation.

## Patch, branch, and package evidence

The review package is generated only from a clean committed branch by the shared commit-aware
builder. It contains the reviewed base/head/range, complete binary-capable patch, changed-file
inventory, diff statistics, Git status, copied orientation/evidence files, validation transcripts,
manifest, per-member sizes and SHA-256 hashes, ZIP, and ZIP SHA-256 sidecar.

Expected branch: `codex/task-068-documentation-reconciliation`. The package is generated after the
task commit, then independently verified before push. Generated review artifacts remain ignored
and are not a second documentation authority.

## Architectural Status Summary

| Subsystem | Responsibility | Status after TASK-068 | Important limitation / next milestone |
|---|---|---|---|
| Documentation authority | Resolve behavior, intent, orientation, authorization, and history | Complete | Historical identifier collisions remain filename-qualified |
| Current-state orientation | Efficient capability, maturity, composition, and evidence map | Complete | Must be updated when composition/maturity changes |
| Root architecture guidance | Stable layers, authorities, dependencies, and invariants | Complete | Detailed task chronology intentionally removed |
| Roadmap | Actual remaining engineering frontier | Complete | Direction only; no work authorized |
| Task index | Complete extant-ticket inventory and current status semantics | Complete | Historical ticket headers remain provenance |
| Operating product | Acquisition/evidence application and operational projections | Unchanged | Local/single-operator limits remain |
| Downstream research chain | Source objects through consulting workspace | Implemented POC, unchanged | Product composition and quality evaluation are next |
| Official press releases | Artifact-specific WDC implementation | Blocked, unchanged | Requires authorized viable source/transport |
| Review evidence | Factual inventory, validation, patch, manifest, ZIP, SHA-256 | Complete after final package generation | Package describes one immutable committed range |

TASK-068 changes the repository's architectural self-description, not its architecture. The next
architectural milestone should be selected from the reconciled roadmap and authorized by a new or
refined ticket.
