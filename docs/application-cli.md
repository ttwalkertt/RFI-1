# Stable RFI-1 application CLI

TASK-012 provides one supported operator entry point for local application state and the integrated
concept and target-firm admin console. The installed `rfi` command and `python -m rfi` call the same
implementation. Run `rfi --help` and `rfi <command> --help` to discover options and examples.

## Command structure

```text
rfi init [--state PATH]
rfi seed [--state PATH]
rfi admin [--state PATH] [--host HOST] [--port PORT]
```

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

Open the displayed URL. The concept catalog is at `/` or `/concepts`; Target Firms is at `/firms`.
Press Ctrl-C to stop cleanly.

## Normal repeat use

Existing valid state needs only:

```sh
.venv/bin/rfi admin
```

Use the same `--state PATH` on every command when selecting a non-default location. Repeating
`init` verifies existing catalogs and reports that they already exist. Repeating `seed` creates
only missing starter identities and reports created and already-present counts.

## Failure behavior and boundaries

`seed` and `admin` require both catalogs to have been initialized. Missing state explains how to
run `init`; incompatible or corrupt state fails closed through existing repository verification;
invalid ports, inaccessible paths, and bind failures produce an operator-facing error and nonzero
exit. Startup never repairs, migrates, or seeds state.

The CLI composes existing concept and firm repositories, sample providers, services, and admin
server. Persistence and public-service responsibilities remain in their established packages.
The local console remains unauthenticated, single-operator oriented, and is not a deployment or
daemon. No automatic browser launch, background scheduling, schema migration, or production
packaging is introduced.

## Architectural Status Summary

- Application lifecycle CLI: **Complete** for explicit local initialization, seeding, and startup.
- Integrated admin console: **Complete** for concept and target-firm local operation.
- Concept and firm persistence: **Complete for current schemas**; incompatible state fails closed.
- Operational deployment: **Not started**; the server is a foreground local development service.
- Architectural change: lifecycle composition moved to a stable package entry point, and server
  creation now opens verified state without hidden mutation.
- Next milestone: use the stable operator surface for focused workflow feedback before expanding
  application operations or deployment concerns.
