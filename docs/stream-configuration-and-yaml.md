# Stream configuration and canonical YAML

TASK-026 refines the TASK-025 artifact-stream subsystem for operators. It does not introduce a
second stream model. `StreamDraft` is still the revisioned repository definition consumed by
validation, preview, persistence, and execution. A strict YAML adapter decodes into that contract,
and canonical export encodes from it.

## Browser workflow

Open `/streams` and work from top to bottom:

1. **Identity** — enter the display name, description, enabled state, visible stable identity, and
   optional non-executable notes. A new stable identity is suggested from the name; a saved
   identity is locked.
2. **Input** — choose one governed external source or compatible upstream streams. Selectors lead
   with display names and show stable identities as secondary context. Upstreams also show schema,
   current revision, active membership count, and latest run status.
3. **Selection** — the common editor offers match-all/match-any, keywords or phrases, authors or
   participants, title/subject, source, and effective-date bounds only when the schema declares
   them. **Advanced policy** exposes the same bounded typed policy for nested groups, negation, and
   registered attributes.
4. **Context and limits** — choose only expansion strategies registered for the schema and set
   hard direct/total bounds. Connected-discussion ancestor/depth controls appear only when that
   strategy is supported and selected.
5. **Review and save** — validate, preview, inspect draft YAML, or stage YAML import. None persists
   a revision. Save or import is a separate explicit action. Execution is in a separate area and
   remains disabled for every new, imported, or modified draft.

File upload and pasted YAML use the same staged path: safe parse, strict structure/version checks,
stable-reference resolution, capability/bounds/DAG validation, normalization, warnings, semantic
diff, and explicit save. The normalized YAML preview is copyable. Saved current or historical
revisions can be downloaded as canonical YAML.

## Canonical format version 1

The complete document has exactly `schema_version`, `stream`, and optional export-only `revision`
keys. Unknown fields fail; they are never discarded. Defaults are explicit in canonical export:
`enabled` is present, description is present (possibly empty), and expansion/bounds are present.
Optional `metadata.notes` is omitted when empty. Every export ends with one newline.

```yaml
schema_version: 1
stream:
  stream_id: linux-block-storage
  display_name: Linux Block Storage
  description: Linux block-layer discussions relevant to storage architecture
  enabled: true
  input:
    kind: external_source
    source_profile_id: linux-block-lore
    artifact_schema: mail.message
  selection:
    all:
    - field: text
      operator: contains
      value: zoned
    - field: effective_at
      operator: after_or_on
      value: '2026-01-01'
  expansion:
    strategy: connected_discussion
    ancestor_closure: required
    descendant_depth: 3
  bounds:
    direct_matches: 25
    total_artifacts: 200
  metadata:
    notes: Optional operator notes.
```

Derived input replaces the `input` object only:

```yaml
input:
  kind: upstream_streams
  stream_ids:
  - linux-block-storage
  artifact_schema: mail.message
```

Representative complete files are
[`task026-external.yaml`](../fixtures/streams/task026-external.yaml) and
[`task026-derived.yaml`](../fixtures/streams/task026-derived.yaml).

## Selection policy

A policy node has exactly one form:

- `all: [POLICY, ...]`
- `any: [POLICY, ...]`
- `not: POLICY`
- `field`, `operator`, and exactly one of `value` or `values`

The schema registry remains authoritative. Current common fields are `schema`, `source`, `title`,
`text`, `authors`, and `effective_at`; mail and SEC registered attributes remain as documented in
[Revisioned artifact streams](revisioned-artifact-streams.md). The human aliases
`searchable_text`, `effective_timestamp`, `contains_any`, `on_or_after`, and `on_or_before` decode
to bounded registered nodes and export in canonical registry form. Boolean children and upstream
identities are sorted canonically because their order has no execution meaning; `in` values are
deduplicated and sorted. Policy depth remains five and node count remains fifty.

## Revision and equivalence behavior

Import of a missing stable identity requires `new` mode and creates revision 1. Import of a
changed existing identity requires `revision` mode and normal optimistic revision creation; prior
history remains immutable. A normalized fingerprint covers identity metadata, enabled state,
input identities, schema, selection, expansion, bounds, and notes. Semantically identical import
returns `already_current` without writing a meaningless revision. Formatting, comments, mapping
order, unordered Boolean-child order, and unordered upstream order do not create differences.

Browser JSON drafts, YAML drafts, CLI input, preview, save, and execution all normalize at
`StreamService`. The YAML document and browser are adapters, not persistence authorities. SQLite
continues to be the only structured authority.

## Governed-source and safety boundary

A stream definition contains only `source_profile_id`. It does **not** contain provider
credentials, tokens, cookies, endpoints/archive URLs, User-Agent, protocol, pacing, concurrency,
timeouts, response bounds, retry/backoff, `Retry-After`, acquisition cursors, or provider-private
configuration. Those fields fail closed and the import cannot create or modify a source profile.

The safe parser also rejects duplicate mapping keys, unsupported versions, unknown nested fields,
invalid scalar types, executable/SQL/Python/JavaScript/JSON-path configuration, unsupported
schemas, fields, operators or expansion, bad bounds, missing references, self-reference,
incompatible upstream schemas, and direct or indirect cycles. Errors include a `$`-rooted YAML
path such as `$.stream.input.source_profile_id`.

## CLI reference

```text
rfi stream schema
rfi stream --state PATH validate --file YAML
rfi stream --state PATH import --file YAML --new
rfi stream --state PATH import --file YAML --revision [--expected-revision ID]
rfi stream --state PATH export --stream ID [--revision-id ID] [--output YAML]
```

`schema` prints a valid commented template and documents both input variants. `validate` performs
structure, capabilities, reference, bounds, and DAG checks without saving. `import` never runs a
stream. `export` emits YAML only on stdout; diagnostics go to stderr.

## Troubleshooting

- `unknown_source` — configure the governed source separately, then reference its stable identity.
- `unknown_upstream` — save the upstream stream first and use its stable stream identity.
- `incompatible_schema` — choose upstreams whose artifact schema matches this definition.
- `dependency_cycle` / `self_reference` — remove the reported edge at
  `$.stream.input.stream_ids`.
- `unsupported_predicate` / `unsupported_operator` — inspect `rfi stream capabilities` and use a
  field/operator pair registered for `artifact_schema`.
- `invalid_limit` / `invalid_bounds` — direct matches must be 1–500 and total artifacts 1–2000.
- `revision_conflict` — export or reload the current saved revision, reapply the intended change,
  and import with the current expected revision.
- `forbidden_configuration` — remove source transport, credential, cursor, or executable fields;
  configure provider behavior in the governed source profile instead.

## Deferred capabilities

YAML comments and original formatting do not round-trip. There is one document per import, not a
bulk package. Arbitrary scripts, regex engines, SQL, JSON path, source creation, automatic
acquisition/execution, scheduling, durable Lore cursors, transformed artifacts, and plugins remain
out of scope. Legacy TASK-025 JSON preview/save CLI commands remain temporarily available, but
YAML version 1 is the canonical operator interchange format.
