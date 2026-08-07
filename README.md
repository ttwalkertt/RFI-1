# Repository-First Intelligence (RFI-1)

RFI-1 is a local, evidence-first research repository and architectural proof of concept. Its
operating product acquires and preserves governed public evidence, maintains revisioned source
configuration and materialized views, and exposes shared CLI, browser, and REST workflows. The
repository also contains implemented downstream POCs for source parsing, derived knowledge,
retrieval, grounded intelligence, and consulting workspaces; those downstream POCs are not yet
composed into the operating product.

The distinction matters: RFI-1 is no longer acquisition-only, but it is not yet an end-to-end
research product.

## Start here

Read these in order before changing the repository:

1. [`AGENTS.md`](AGENTS.md) — mandatory working instructions.
2. [`docs/current-state.md`](docs/current-state.md) — current capabilities, maturity, product
   composition, evidence locations, and documentation authority.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — stable layers, authorities, dependencies, and invariants.
4. [`TASKS.md`](TASKS.md) and the active ticket under [`tasks/`](tasks/) — authorized scope and
   acceptance evidence.
5. [`docs/framework-task-operating-model.md`](docs/framework-task-operating-model.md) — completion,
   review-package, and Architectural Status Summary requirements.

Use [`ROADMAP.md`](ROADMAP.md) for intended direction and [`BACKLOG.md`](BACKLOG.md) for
unscheduled candidates. Neither authorizes implementation. Completed task reviews and the design
study preserve useful provenance, but repository contracts, implementation, and tests determine
current behavior.

## What is integrated today

The stable `rfi` application provides:

- local SQLite initialization, explicit seed/import, configuration backup/restore, and integrity
  verification;
- revisioned concepts, target firms, firm source profiles, and externally managed firm
  configuration;
- a Pull Workflow shared by the CLI, local admin/API server, and browser;
- immutable, content-addressed acquisition evidence with append-only observations and attempts;
- deterministic SEC Form 10-K, 10-Q, 8-K, 20-F, and 6-K retrieval;
- bounded StockAnalysis earnings-transcript acquisition and inspection;
- repository-owned RSS/Atom sources, polling, unavailable-entry handling, and aggregate RSS;
- bounded Linux/Lore mailing-list acquisition and canonical lineage; and
- revisioned artifact streams plus a repository-owned artifact browser.

The registered WDC Business Wire adapter is fixture-backed but operationally blocked by live
transport viability. It must not be described or operated as accepted production retrieval.

The source-object, derived-knowledge, retrieval, intelligence, and consulting-workspace packages
have public contracts and executable proofs. They are currently invoked by task scripts and tests,
not by the stable CLI/admin composition. See the capability matrix in
[`docs/current-state.md`](docs/current-state.md#capability-maturity-and-composition).

## Architecture at a glance

```text
Operating product
  governed configuration
          |
          v
  acquisition services ---> immutable bytes + SQLite evidence/operations
          |                                  |
          +--> artifact browser              +--> streams/feed/mail projections

Implemented downstream POCs (not product-composed)
  immutable evidence -> source objects -> derived knowledge -> governed retrieval
                    -> grounded intelligence -> consulting workspace
```

The repository keeps these authority classes distinct. Model output, workspace history, stream
membership, and browser projections never replace exact source evidence.

## Run the local application

RFI-1 requires Python 3.11 or newer, `make`, and Git.

```sh
make setup
.venv/bin/rfi init
.venv/bin/rfi seed       # optional starter data
.venv/bin/rfi admin
```

Later runs normally need only `.venv/bin/rfi admin`. Use a consistent `--state PATH` to select a
different repository. Discover the supported operator surface with:

```sh
.venv/bin/rfi --help
.venv/bin/rfi pull --help
.venv/bin/rfi feeds --help
.venv/bin/rfi mailing-list --help
.venv/bin/rfi stream --help
```

The full stable workflow and failure semantics are in
[`docs/application-cli.md`](docs/application-cli.md). The integrated browser guide is
[`docs/operator-guide.md`](docs/operator-guide.md). Task-specific scripts are evidence and
diagnostic tools unless those guides explicitly say otherwise.

Live SEC access requires a governed SEC user agent. Other live paths have their own explicit
gates and bounded policies. Normal repository validation is local and must not require credentials
or network access.

## Validate changes

```sh
make docs-check
make baseline-check
git diff --check
make validate
```

`make validate` runs the repository-standard tests, static policy checks, documentation/link
checks, design-baseline verification, source archive build, and integrity checks. Each task ticket
may require additional focused or live evidence. A task is not complete merely because the full
test suite passes; the ticket's review package and documented limitations remain required.

## Documentation map

| Document | Role |
|---|---|
| [`docs/current-state.md`](docs/current-state.md) | Current implementation, maturity, composition, authority, and evidence orientation |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architectural layers, authorities, dependencies, and invariants |
| [`ROADMAP.md`](ROADMAP.md) | Intended engineering frontier; not authorization |
| [`TASKS.md`](TASKS.md) | Current task index and authorization/status guidance |
| [`BACKLOG.md`](BACKLOG.md) | Unscheduled candidates and deferred observations |
| [`docs/decisions/`](docs/decisions/) | Accepted architectural decisions; cite filename because historical numbers collide |
| [`docs/development.md`](docs/development.md) | Development and validation workflow |
| [`docs/operator-guide.md`](docs/operator-guide.md) | Integrated local browser workflow and help topics |
| [`docs/design-baseline.md`](docs/design-baseline.md) | Provenance and interpretation of the imported root guidance |
| [`docs/design/`](docs/design/) | Research/design inputs, not current implementation evidence |

## Enduring principles

- The repository, not a chat or generated report, is the durable record.
- Evidence is preserved before interpretation and remains inspectable.
- Provenance and conservative coverage are explicit contracts.
- Acquisition, knowledge, retrieval, intelligence, and projection/workspace state are separate
  layers with one-way dependencies.
- Replaceable providers, retrieval techniques, models, and interfaces do not become architectural
  authorities.
- Architecture, implementation maturity, product composition, and roadmap status must be stated
  separately.
