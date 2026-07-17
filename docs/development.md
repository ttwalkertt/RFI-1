# Development

RFI-1 has no runtime or third-party development dependencies. Python 3.11 or newer,
`make`, Git, and a ZIP-capable Python standard library are sufficient. This intentionally keeps
the bootstrap usable offline and avoids choosing product dependencies before later task tickets.

## Setup

From the repository root:

```sh
make setup
```

This creates an ignored `.venv` using `python3` (override with `make PYTHON=/path/to/python`).

## Quality gates

```sh
make test
make focused-test
make acquisition-demo
make lint
make format-check
make typecheck
make import-check
make docs-check
make baseline-check
make build
```

Run all gates with `make validate`. It includes the deterministic, local-only acquisition
substrate demonstration. The lint, formatting, and lightweight static type-policy
checks are implemented with the standard library in `scripts/quality.py`; their deliberately
small policy is documented in that script's output. A later task may adopt external tooling when
the codebase has enough behavior to justify the dependency.

`make build` creates and verifies a source snapshot at `.artifacts/build/rfi-1-source.zip`.
It is a reviewable bootstrap build artifact, not a published application distribution.

## Stable application workflow

Install the repository into the active virtual environment with `python -m pip install -e .` when
the `rfi` executable is not already present. The module form works through the same implementation.

First run:

```sh
.venv/bin/rfi init
.venv/bin/rfi seed  # optional, explicit starter data
.venv/bin/rfi admin
```

Later runs need only `.venv/bin/rfi admin`. Use `--state PATH` consistently to select another
state location, and use `rfi --help` or `rfi <command> --help` for host, port, defaults, examples,
and lifecycle behavior. See the [application CLI guide](application-cli.md) for the full operator
workflow and failure semantics. Routine application use no longer requires task-specific scripts.

## TASK-011 target-firm workflow

Run `make task011-proof` for the seeded HDD firm catalog, conflict, revision, restart, and stable
reference proof. The existing local admin server exposes Target Firms at `/firms`; its public API
is documented in the [target-firm catalog guide](target-firm-catalog-and-admin-editor.md).

## Acquisition operator workflow

The substrate accepts repository state through a caller-selected directory. It never contacts a
source itself. Use the local fixture lifecycle with:

```sh
make acquisition-demo
```

For an existing state directory, inspect and maintain it with:

```sh
.venv/bin/python scripts/acquisition_operator.py sources --state STATE
.venv/bin/python scripts/acquisition_operator.py artifacts --state STATE
.venv/bin/python scripts/acquisition_operator.py history --state STATE
.venv/bin/python scripts/acquisition_operator.py checkpoints --state STATE
.venv/bin/python scripts/acquisition_operator.py index --state STATE
.venv/bin/python scripts/acquisition_operator.py verify --state STATE
.venv/bin/python scripts/acquisition_operator.py delete-derived --state STATE
.venv/bin/python scripts/acquisition_operator.py rebuild --state STATE
```

See [the acquisition substrate guide](acquisition-substrate.md) for contracts, durability,
checkpoint ordering, failure behavior, and replay semantics.

## Acquisition engine operator workflow

The TASK-003 fixtures use only checked-in JSON and exact byte files. Create a local state directory,
inspect explicit adapter registration, and run one or all enabled governed fixture sources:

```sh
.venv/bin/python scripts/acquisition_operator.py adapters --state STATE
.venv/bin/python scripts/acquisition_operator.py run-source --state STATE \
  --source source-fixture-feed --run-key first
.venv/bin/python scripts/acquisition_operator.py run-all --state STATE --run-key complete
```

Inject a transient failure and resume by rerunning without the injection:

```sh
.venv/bin/python scripts/acquisition_operator.py run-source --state STATE \
  --source source-fixture-feed --run-key partial \
  --fail-candidate candidate-feed-b-v1
.venv/bin/python scripts/acquisition_operator.py run-source --state STATE \
  --source source-fixture-feed --run-key resumed
```

Use the existing `sources`, `history`, `checkpoints`, `index`, `verify`, `delete-derived`, and
`rebuild` commands to inspect and replay repository state. `rebuild` never loads adapters. Run the
raw multi-source demonstration with `make engine-demo`, complete validation with `make validate`,
and generate the independently auditable TASK-003 package with `make review-package`. See the
[engine design](acquisition-engine.md) for contracts and failure semantics.

## Review package

```sh
make review-package
```

This reruns and captures every gate, performs an equivalent isolated-tree validation, records
Git state and the full task patch, and creates:

- `.artifacts/review/TASK-003/`
- `.artifacts/review/TASK-003-review.zip`
- `.artifacts/review/TASK-003-review.zip.sha256`

Generated artifacts are intentionally ignored by Git. Review evidence must be regenerated from
the final state rather than committed as durable project source.

## TASK-004 SEC workflow

Native EDGAR is the required live acceptance path; SEC-API.io remains an optional commercial
acceleration path. Native profiles, fair-access pacing, runtime identity, live commands, and replay
are documented in [the native EDGAR guide](edgar-acquisition.md). The commercial boundary remains
documented in [the SEC-API.io guide](sec-api-acquisition.md). Inspect both scopes without operator
identity, credentials, or network requests using:

```sh
.venv/bin/python scripts/edgar_operator.py scope
.venv/bin/python scripts/sec_api_operator.py scope
```

Run `make edgar-offline` and `make sec-api-offline` for the distinct sanitized fixture lifecycles.
Explicit live commands may read the two governed values from private, Git-ignored
`.rfi/runtime.env`; environment values override it. `make validate` never loads that file and
remains identity-free, credential-free, and offline. `make review-package` creates
the TASK-004 package and honestly marks native live acceptance blocked when `RFI_SEC_USER_AGENT` is
absent. Live commands are never part of normal validation and must be explicitly invoked.

## TASK-005 source and knowledge workflow

Run `make task005-proof` for the deterministic offline construction and independent rebuild proof.
The source-object catalog and derived-knowledge store are separate and can be inspected with the
commands in the [TASK-005 subsystem guide](source-objects-and-derived-knowledge.md). The optional
real proof consumes the existing TASK-004 runtime corpus locally and performs no network access.

## TASK-006 retrieval workflow

Run `make task006-proof` for deterministic governed retrieval, provenance-complete evidence
assembly, replaceability, and browser inspection. See the
[TASK-006 subsystem guide](governed-retrieval-and-source-browser.md) for query and navigation
commands.

## TASK-007 intelligence workflow

Run `make task007-proof` for the deterministic multi-step, insufficiency, ambiguity,
replaceability, refusal, and fail-closed model-output proofs. Run the accepted local corpus proof:

```sh
.venv/bin/python scripts/task007_operator.py real-proof \
  --acquisition-state .artifacts/runtime/TASK-004-edgar \
  --state .artifacts/runtime/TASK-007
```

The JSON record exposes the structured plan, every TASK-006 request and consumed package,
model-facing projection, raw draft, claim mappings, iteration decisions, and stopping reason. See
the [TASK-007 subsystem guide](model-guided-source-grounded-intelligence.md) for contracts,
retention, runtime policy, failure semantics, and limitations. `make review-package` creates the
TASK-007 review package.
