# Stable RFI-1 application CLI

TASK-012 provides one supported operator entry point for local application state and the integrated
concept, target-firm, and source-profile admin console. The installed `rfi` command and
`python -m rfi` call the same
implementation. Run `rfi --help` and `rfi <command> --help` to discover options and examples.

## Command structure

```text
rfi init [--state PATH]
rfi seed [--state PATH] [-f FILE | --file FILE ...]
rfi seed --print-schema
rfi admin [--state PATH] [--host HOST] [--port PORT]
rfi pull (--firm FIRM_ID ... | --all-configured) [--state PATH]
rfi verify [--state PATH]
rfi backup [--state PATH] --output ZIP
rfi restore --input ZIP [--state FRESH_PATH]
rfi mailing-list --state PATH configure-linux-block
rfi mailing-list --state PATH configure-lore-source --source ID --list-id ID \
  --display-name NAME --archive-base-url HTTPS_URL [transport policy options]
rfi mailing-list --state PATH preview|acquire --live --message-id MESSAGE_ID [limits]
rfi mailing-list --state PATH sources|discussions|search|incomplete|rebuild
```

`configure-lore-source` persists provider/list/endpoint identity and User-Agent, pacing,
concurrency, timeout, response-size, retry, and backoff policy in the governed external-source
profile. Stream JSON references that source ID and does not repeat transport configuration.

The default state is `.artifacts/runtime/rfi-1`, the default host is `127.0.0.1`, and the default
port is `8765`. Every command prints or documents its state location. `admin` prints the bound URL,
state path, and Ctrl-C stop instruction before serving.

## First run

Initialize empty state once:

```sh
.venv/bin/rfi init
```

Optionally add the checked-in starter concepts and target firms. Seeding is explicit and is never
performed by `init` or `admin`:

```sh
.venv/bin/rfi seed
```

Launch the integrated console:

```sh
.venv/bin/rfi admin
```

Open the displayed URL. The concept catalog is at `/` or `/concepts`, Target Firms is at `/firms`,
and firm acquisition configuration is at `/source-profiles`. Press Ctrl-C to stop cleanly.
The shared Pull Workflow is available at `/pull-sources`.

## Pull Workflow

Run enabled source-profile artifacts through the same durable workflow used by REST and GUI:

```sh
rfi pull --firm seagate
rfi pull --firm seagate --firm ibm
rfi pull --all-configured
```

The complete structured result is printed as JSON. Unsupported retrieval modes are retained as
explicit skipped results with an operator diagnostic; they do not trigger hidden fallback logic.
An enabled `sec_10k` artifact with an identifier candidate containing a valid SEC CIK is selected
through the `sec-form-10k` capability and uses the governed runtime request identity described in
[deterministic SEC Form 10-K retrieval](deterministic-sec-form-10k-retrieval.md).
See [Pull Workflow](pull-workflow.md) for planning, outcomes, ingress, and limitations.

## Normal repeat use

Existing valid state needs only:

```sh
.venv/bin/rfi admin
```

Use the same `--state PATH` on every command when selecting a non-default location. Repeating
`init` verifies existing catalogs and reports that they already exist. Repeating `seed` creates
only missing starter identities and reports created and already-present counts.

## External catalog import

Print the canonical YAML authoring template without initialized state or any state changes:

```sh
.venv/bin/rfi seed --print-schema > firms.yaml
```

Replace the placeholders with real values, initialize the selected state, and import one or more
files. Both option spellings are equivalent and repeatable:

```sh
.venv/bin/rfi seed --state /path/to/state --file firms.yaml -f additional-firms.yaml
```

File import remains explicit. With no file, `seed` retains its starter-only behavior. With files,
the command validates the entire batch and conflicts with existing and starter firms before
creating any record. Identical existing records are reported as already present; duplicate or
conflicting canonical IDs, recognition identifiers, and domains fail closed without revisions.
Unknown fields and unsupported schema versions are rejected so authoring errors remain visible.

The emitted template and decoder share a canonical recursive field registry. YAML catalog and
research metadata are validated but remain external metadata rather than application state. Only
target-firm records are currently importable; the registry is the extension point for future
catalog types.

`relevance` is a finite numeric score from `0` through `100`, inclusive. Omission defaults to
`0.0`. Higher values sort first, the firm API accepts `minimum_relevance`, and numeric text is
searchable. Relevance is ordinary prioritization data—not a classification, taxonomy, role,
status, sector, or industry—and has no category labels.

New firms from every supplied file publish through one SQLite transaction. A persistence failure
rolls back every row in that batch and leaves the prior catalog and repository revision unchanged.

## Integrity, backup, and restore

`rfi verify` checks the SQLite schema version, database integrity, foreign keys, structured
relationships, content references, sizes, checksums, and orphan inventory. It reports problems but
does not repair or discard evidence.

`rfi backup` creates a new ZIP using SQLite's online backup API and includes every immutable
content object plus a checksummed member manifest. `rfi restore` accepts only a fresh destination,
verifies the complete archive, and re-runs schema and hybrid integrity checks before success.

## Failure behavior and boundaries

All normal commands require compatible initialized SQLite state. Missing core state explains how
to run `init`; incompatible, corrupt, legacy-only, or mixed legacy/SQLite state fails closed;
invalid ports, inaccessible paths, and bind failures produce an operator-facing error and nonzero
exit. Startup never repairs, migrates, or seeds state.

The CLI composes existing concept and firm repositories, sample providers, services, and admin
server. Persistence and public-service responsibilities remain in their established packages.
The local console remains unauthenticated, single-operator oriented, and is not a deployment or
daemon. No automatic browser launch, background scheduling, legacy migration, or production
packaging is introduced. Schema version 4 includes the supported version-1 mailing-list and
version-2 stream-schema migrations; it does not import legacy structured-file repositories.

Mailing-list preview is read-only and displays seeds, context, limits, state, and warnings before
an explicit acquire. There is no unbounded or archive-wide form. Offline query and rebuild actions
use retained repository evidence and never instantiate the live adapter.

## Architectural Status Summary

- Application lifecycle CLI: **Complete** for explicit local initialization, seeding, and startup.
- Integrated admin console: **Complete** for concept and target-firm local operation.
- Application structured persistence: **Complete for schema version 4**; SQLite is authoritative
  and incompatible or legacy state fails closed.
- Operational deployment: **Not started**; the server is a foreground local development service.
- Architectural change: TASK-021 replaced disposable structured-file persistence with one fresh
  SQLite authority while preserving explicit seed and public service behavior.
- Next milestone: gather operating evidence before considering schema evolution, PostgreSQL, or
  legacy import tooling.
