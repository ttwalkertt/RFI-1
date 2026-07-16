# Bounded native SEC EDGAR acquisition

Native EDGAR is the TASK-004 live acceptance path. SEC-API.io remains an optional commercial
adapter documented separately. Both use the unchanged acquisition engine and repository facade.

## Fixed corpus

| Source | SEC identity | Inclusive filing interval | Per-form maximum |
|---|---|---|---|
| STX | CIK 1137789 | 2024-01-01 through 2025-12-31 | 1×10-K, 2×10-Q, 2×8-K |
| WDC | CIK 106040 | 2024-01-01 through 2025-12-31 | 1×10-K, 2×10-Q, 2×8-K |

Discovery uses official `data.sec.gov/submissions/CIK##########.json` data. Results are selected
per form by filing date, acceptance timestamp, and accession descending, then exposed one at a
time. The maximum corpus is ten filings and cannot widen with the wall clock.

Exact retrieval uses the official archive path:

```text
https://www.sec.gov/Archives/edgar/data/<CIK>/<accession digits>/<accession>.txt
```

The exact complete-submission bytes become immutable content-addressed repository artifacts.

## Runtime identity and fair access

`RFI_SEC_USER_AGENT` may be supplied in the invoking process environment or in the ignored local
file `.rfi/runtime.env`. Its value must contain a descriptive application identity followed by an
operator-controlled contact email. The repository intentionally supplies no real contact value.

The local file is a literal UTF-8 `KEY=value` file: it performs no shell expansion, interpolation,
or command execution. Only `RFI_SEC_USER_AGENT` and optional `SEC_API_IO_API_KEY` are accepted.
Create it with private permissions and edit in the operator's normal secret-safe editor:

```sh
umask 077
mkdir -p .rfi
chmod 700 .rfi
touch .rfi/runtime.env
chmod 600 .rfi/runtime.env
${EDITOR:?set EDITOR to a secret-safe editor} .rfi/runtime.env
```

Add `RFI_SEC_USER_AGENT=<operator supplied>` and, only if needed, the optional commercial key.
Do not paste values into commands, tickets, chat, test output, or review artifacts. Environment
variables override the corresponding local file values. Empty environment overrides fail closed
rather than falling back to the file.

Profiles contain only `env:RFI_SEC_USER_AGENT`. The local file is Git-ignored. The loader rejects
symlinks, non-regular files, permissions broader than `0600`, files over 16 KiB, malformed lines,
duplicate keys, and unknown keys. Values are never printed, copied into process environment,
persisted in runtime evidence, copied into fixtures, placed in URLs, or included in review
evidence. Missing or malformed configuration stops before network access.

The adapter spaces requests by at least 0.5 seconds, limiting it to two requests per second—well
below the current SEC maximum of ten. It also enforces two attempts, a 20-second timeout, a 5 MB
submissions response limit, a 50 MB filing limit, an 80-request acceptance ceiling, status and
content checks, and sanitized errors.

## Commands

Offline scope and tests:

```sh
.venv/bin/python scripts/edgar_operator.py scope
env -u RFI_SEC_USER_AGENT .venv/bin/python -m unittest tests.test_edgar -v
env -u RFI_SEC_USER_AGENT make validate
.venv/bin/python -m unittest tests.test_runtime_config -v
```

Explicitly live commands:

```sh
.venv/bin/python scripts/edgar_operator.py live-config
.venv/bin/python scripts/edgar_operator.py live-config --probe
.venv/bin/python scripts/run_task004_edgar_live.py
```

The first command validates configuration without network access. The `--probe` command makes one
live request. The acceptance runner refuses ambiguous reuse if its ignored state or evidence path
already exists. Use `--no-local-config` on either entry point to require environment-only input.

Provider-disabled inspection, integrity, replay, and rebuild:

```sh
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/edgar_operator.py inventory \
  --state .artifacts/runtime/TASK-004-edgar
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/acquisition_operator.py verify \
  --state .artifacts/runtime/TASK-004-edgar
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/acquisition_operator.py delete-derived \
  --state .artifacts/runtime/TASK-004-edgar
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/acquisition_operator.py rebuild \
  --state .artifacts/runtime/TASK-004-edgar
```

Review generation always disables local configuration and removes both supported environment
variables from child processes. A package generated without separately captured sanitized live
evidence marks native live acceptance blocked and cannot substitute fixture evidence for real
EDGAR data.
