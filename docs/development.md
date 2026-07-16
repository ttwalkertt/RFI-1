# Development

RFI-1 currently has no runtime or third-party development dependencies. Python 3.11 or newer,
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
make lint
make format-check
make typecheck
make import-check
make docs-check
make baseline-check
make build
```

Run all gates with `make validate`. The lint, formatting, and lightweight static type-policy
checks are implemented with the standard library in `scripts/quality.py`; their deliberately
small policy is documented in that script's output. A later task may adopt external tooling when
the codebase has enough behavior to justify the dependency.

`make build` creates and verifies a source snapshot at `.artifacts/build/rfi-1-source.zip`.
It is a reviewable bootstrap build artifact, not a published application distribution.

## Review package

```sh
make review-package
```

This reruns and captures every gate, performs an equivalent isolated-tree validation, records
Git state and the full task patch, and creates:

- `.artifacts/review/TASK-001/`
- `.artifacts/review/TASK-001-review.zip`
- `.artifacts/review/TASK-001-review.zip.sha256`

Generated artifacts are intentionally ignored by Git. Review evidence must be regenerated from
the final state rather than committed as durable project source.
