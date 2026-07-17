# TASK-013 — External Catalog Import for `rfi seed`

## Status

Complete

## Objective

Extend `rfi seed` to import one or more external catalog files in addition to the built-in starter catalog.

The design shall support curated catalogs created manually or generated with AI assistance while maintaining deterministic, validated, and idempotent imports.

The implementation shall treat imported catalogs as external data sources rather than application state.

## Motivation

The built-in starter catalog is intentionally small.

Operators should be able to construct larger curated catalogs outside RFI and import them repeatedly without duplicate records or unintended modification.

The canonical import format should be discoverable directly from the tool so AI assistants and external tools can generate compatible catalogs without reverse engineering the implementation.

## Functional Requirements

### External catalog import

Support:

```bash
rfi seed --state PATH --file FILE
```

and:

```bash
rfi seed --state PATH -f FILE
```

Multiple `--file` arguments may be supported now or reserved for a future enhancement, but the design shall not preclude importing multiple catalogs.

### Built-in seed behavior

Existing behavior shall remain unchanged.

```bash
rfi seed --state PATH
```

shall install only the built-in starter catalog.

No implicit import shall occur.

### Canonical template output

Provide a command that prints the canonical YAML import template.

Preferred interface:

```bash
rfi seed --print-schema
```

The command shall:

- write valid YAML to stdout;
- perform no state mutation;
- require no initialized state;
- exit successfully.

The printed template shall represent the canonical import format expected by the importer.

### Validation

Entire catalog files shall be validated before modifying state.

Validation failures shall produce actionable error messages.

No partial imports are permitted.

### Import semantics

Imports shall be idempotent.

Existing identical records shall be reported as already present.

New records shall be created.

Conflicting canonical identifiers shall be rejected.

No existing record shall be silently modified.

### Schema generation

The printed template shall be generated from the same canonical field definitions used by the importer.

The implementation shall avoid maintaining independent template and parser definitions.

## Catalog Format

The canonical import format shall be YAML.

JSON compatibility is acceptable provided the YAML format remains canonical.

## Sample Canonical YAML

The printed template should resemble:

```yaml
schema_version: 1

catalog:
  title: "Example catalog"
  description: "Describe the purpose of this catalog."
  prepared_on: "YYYY-MM-DD"

firms:
  - id: example-firm
    name: Example Firm, Inc.
    aliases:
      - Example Firm

    status: active

    relevance: 50

    sector: Information Technology
    industry: Example Industry

    roles:
      - example-role

    identifiers:
      ticker: EXMP

research:
  prepared_by: Your Name
  methodology: Describe selection methodology
  reviewed_on: YYYY-MM-DD

  sources:
    - title: Example Source
      url: https://example.com/
      accessed_on: YYYY-MM-DD
```

This sample is illustrative only.

The printed output shall always reflect the canonical implementation.

## Relevance

`relevance` is an ordinary numeric field.

It is intended for:

- sorting;
- filtering;
- searching;
- prioritization.

It is not a classification or taxonomy.

## Non-Goals

This task does not include:

- web research;
- automatic acquisition;
- automatic synchronization;
- downloading catalogs;
- modifying existing records;
- replacing acquisition workflows.

## Verification Requirements

The verification package shall include evidence demonstrating:

- built-in seed behavior remains unchanged;
- successful import from YAML;
- short and long file options;
- canonical template generation;
- generated template parses successfully;
- import succeeds after replacing template placeholders with valid values;
- idempotent repeated import;
- duplicate identifier rejection;
- conflicting record rejection;
- malformed YAML rejection;
- unsupported schema version rejection;
- unreadable file handling;
- empty file handling;
- no partial imports after validation failure;
- installed executable and `python -m rfi` behavioral parity;
- complete validation suite passing.

## Design Notes

The canonical template is intentionally exposed through the CLI so that humans, AI assistants, and external tooling can generate valid catalogs directly from the tool rather than relying on separate documentation.

The template should remain synchronized automatically with the importer's supported fields and validation rules.

## Solution Data

### Implementation

- `rfi seed -f/--file FILE` is repeatable and imports YAML target-firm catalogs while retaining
  built-in starter behavior when no file is supplied.
- `rfi seed --print-schema` emits canonical YAML before state lookup and cannot be combined with
  file import.
- `rfi.catalog_import` separates canonical fields, decoding, whole-batch validation, persistence
  orchestration, and template rendering. An importable-type registry supports future sections.
- PyYAML is the sole new runtime dependency and provides safe YAML loading and dumping.

### Import Semantics

All supplied files are decoded before persistence. New records are staged in stable identifier
order and published through one canonical catalog-pointer update. Any staging or publication
failure removes the batch's staged artifacts and preserves the prior catalog. Identical existing
records are reported as already present. Duplicate canonical IDs and conflicts with persisted,
batch, or built-in starter identities fail closed. Existing revisions are never updated. Catalog
and research metadata are validated but are not persisted as state.

Target-firm `relevance` is a finite numeric value from 0 through 100 inclusive, defaulting to 0.0
when omitted. It supports descending sort, minimum-value filtering, numeric search, and operator
prioritization. It is not a classification, enumeration, taxonomy, role, status, sector, or
industry, and no category labels are defined.

### Verification

`tests/test_task013.py` covers canonical template parsing without state, valid placeholder
replacement, long and short repeatable options, successful and idempotent import, duplicate and
conflicting canonical IDs, recognition-identifier conflicts, malformed YAML, unsupported schema,
unreadable and empty files, relevance template/persistence/read/sort/filter/search/default and
invalid-value behavior, complete-batch validation, injected persistence rollback after artifact
staging, and installed/module parity. `tests/test_task012.py` retains the built-in seed regression
proof.

The reproducible review package is generated by `make review-package` under
`.artifacts/review/TASK-013`, with a ZIP and SHA-256 checksum beside it. It contains representative
command output, focused and complete validation logs, the cumulative patch, changed-file inventory,
repository status, design notes, limitations, and a digest manifest.

### Limitations

Only target-firm records are importable in schema version 1. Metadata is validation-only, and
imports are local files only. Download, synchronization, mutation, and schema migration remain out
of scope. The batch transaction applies to new firms in one import invocation; it does not combine
starter concept seeding and target-firm import into a cross-repository transaction.

## Architectural Status Summary

- External catalog CLI: **Complete** for local repeatable YAML files and schema discovery.
- Canonical import model and validation: **Complete** for schema version 1 target firms.
- Deterministic persistence orchestration: **Complete** for create-or-identical semantics and
  all-or-nothing multi-firm publication.
- Additional catalog types: **Provisional extension point** through the importable-type registry.
- Remote acquisition and synchronization: **Not Started** and explicitly out of scope.
- Next architectural milestone: add another importable catalog type only when its authority and
  persistence contract are defined, reusing the registry and whole-batch validation boundary.
