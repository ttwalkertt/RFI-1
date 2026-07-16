# ADR-0001: Repository bootstrap

- Status: accepted
- Scope: TASK-001

## Context

RFI-1 needs an accelerated proof-of-concept foundation that can evolve toward an MVP without
implementing acquisition or later knowledge capabilities prematurely. The repository must remain
understandable to one technical owner and preserve explicit boundaries for future immutable
evidence, mutable indexes, generated outputs, and source code.

## Decision

Use a `src`-layout Python project with a single, metadata-only `rfi` package and standard-library
bootstrap tooling. Keep governing design documents at the repository root so their existing names
and README navigation remain stable. Put development guidance and decisions under `docs/`, tests
under `tests/`, deterministic automation under `scripts/`, future checked-in test data under
`fixtures/`, and future local/runtime state under ignored `data/` boundaries.

Python 3.11 is the minimum supported version. There are no runtime or third-party development
dependencies in TASK-001. A local virtual environment and reproducible `make` targets provide the
dependency and workflow boundary. Standard-library checks validate syntax, annotations, formatting
policy, documentation links, imported-document integrity, tests, imports, and source packaging.

Generated build and review evidence lives under ignored `.artifacts/`. TASK-001 review packages use
`.artifacts/review/TASK-001/` plus a sibling ZIP and checksum. Runtime data and credentials are also
ignored; tracked README files document the future boundaries without defining their schemas.

## Alternatives considered

- A flat package layout was simpler initially, but a `src` layout catches accidental imports from
  the working directory and gives later packaging work a clean boundary.
- Poetry, Hatch, and uv could provide richer locking and publishing workflows, but TASK-001 has no
  dependencies and requiring a network bootstrap would weaken fresh-checkout validation.
- pytest, Ruff, and mypy offer broader checks. They are deferred until product code creates enough
  surface area to justify third-party tooling; the current explicit policy covers the bootstrap.
- Moving design inputs under `docs/design/` would group them neatly, but it would require broad link
  edits and make the governing baseline less visible from the repository root.
- Creating acquisition interfaces or placeholder domain packages now could anticipate later work,
  but would violate the task boundary and bias designs before source behavior is observed.

## Consequences

The repository is offline-bootstrapable and reviewable with very little machinery. The quality
policy is intentionally narrower than a mature Python project's eventual toolchain. Later tickets
may replace it while retaining the documented commands. No object layout, repository identity,
source model, acquisition behavior, or downstream intelligence semantics are established here.
