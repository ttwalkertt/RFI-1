# TASK-026 — Usable Artifact Stream Configuration and Canonical YAML Import/Export

## Status

Ready

## Summary

Replace the current dense Artifact Streams configuration page with a clear operator workflow and add canonical YAML import/export for stream definitions.

TASK-025 established the revisioned artifact-stream DAG, governed external-source profiles, typed cross-schema filtering, schema-specific context expansion, durable memberships and lineage, explicit execution, and artifact-browser integration. That architecture is now merged.

The remaining problem is operator usability. The current Streams page exposes too much of the internal stream model at once, mixes draft configuration with execution controls, and provides no practical path for authoring or reviewing nontrivial stream definitions outside the browser.

This task must deliver:

- a substantially clearer, schema-aware Stream Configuration page;
- canonical YAML import and export using the same repository-owned stream revision contract as the UI;
- safe validation and preview before persistence;
- CLI support to print the canonical YAML schema/template;
- CLI support to validate, import, and export stream definitions; and
- complete verification that browser and CLI workflows produce the same normalized repository state.

Implementation details remain with Codex unless constrained below by an architectural invariant, required behavior, or verification obligation.

---

## Context

RFI-1 already supports:

- revisioned stream definitions;
- external governed sources and upstream-stream inputs;
- stream dependency DAG validation;
- bounded typed selection policies;
- schema capability declarations;
- schema-specific context-expansion handlers;
- bounded preview and execution;
- durable runs, memberships, publication plans, and lineage;
- Linux mailing-list and SEC artifact projections;
- atomic stream publication;
- immutable evidence retention independent of stream membership; and
- one authoritative operator-console navigation definition.

The current Streams page is functionally complete but operationally difficult to use. Identity, input topology, source selection, artifact schema, typed predicate construction, expansion policy, output bounds, validation, save, and execution controls are presented together with internal terminology and long repository identifiers.

RFI-1 already has a successful YAML-based operator workflow for catalog seeding. Existing catalog YAML uses a versioned top-level document, human-readable metadata, stable record identities, structured lists, and optional research/provenance metadata. The stream-definition format should follow the same broad operator principles without copying the firm schema or creating a second stream model.

The uploaded HDD supplier catalog is an example of the existing human-authored YAML style: a declared `schema_version`, descriptive catalog metadata, stable entity identifiers, structured nested fields, and optional research provenance. fileciteturn6file0

---

## Objective

Implement an operator-usable stream-definition workflow across browser, YAML, and CLI.

An operator must be able to:

1. create or revise a stream using a clear browser workflow;
2. author a stream definition in external YAML;
3. import YAML by file upload or pasted text;
4. validate and normalize YAML without saving;
5. preview bounded matches using the imported or browser-authored draft;
6. compare an imported definition with an existing saved revision;
7. explicitly save the definition as a new stream or new revision;
8. export any saved revision as deterministic canonical YAML;
9. print the supported YAML definition schema/template from the CLI;
10. validate, import, and export definitions from the CLI; and
11. obtain identical normalized stream revisions regardless of whether the definition originated in the browser or CLI.

---

## Architectural Requirements

### 1. One stream-definition contract

Browser editing, YAML import/export, CLI operations, validation, preview, persistence, and execution must all use the same repository-owned stream-definition contract.

Do not create:

- a browser-only configuration shape;
- a YAML-only configuration model;
- duplicate validation logic;
- a second persistence boundary;
- hidden browser defaults that are absent from canonical YAML; or
- CLI behavior that bypasses revisioning, capability validation, or DAG validation.

A definition must normalize through one authoritative application/service boundary before it may be previewed or saved.

### 2. Canonical, versioned YAML

Define a bounded, versioned YAML representation for artifact streams.

At minimum, canonical YAML must represent:

- format/schema version;
- stream stable identity;
- display name;
- description;
- enabled state where applicable;
- input kind;
- governed external-source reference or upstream-stream references;
- artifact schema expectations;
- typed selection policy;
- schema-supported expansion policy;
- hard execution/output bounds; and
- optional human-authored notes or descriptive metadata that do not affect execution.

The representation must preserve the semantic distinction between:

- external governed source input;
- upstream stream input;
- selection;
- context expansion; and
- output bounds.

The exact field names remain an implementation decision, but they must be stable, documented, human-readable, and deterministic.

### 3. Canonical serialization

Exported YAML must be deterministic for a given saved revision.

Canonicalization must define:

- stable top-level key ordering;
- stable ordering for unordered collections;
- normalized scalar types;
- explicit omission or inclusion rules for defaults;
- consistent formatting of dates and identifiers;
- deterministic Boolean policy representation; and
- a trailing newline.

A canonical export followed by validation and re-import must produce the same normalized definition and semantic fingerprint.

Comments and original YAML formatting need not round-trip.

### 4. Safe parsing and strict validation

YAML parsing must use a safe parser.

The system must reject explicitly:

- unknown format/schema versions;
- unknown top-level or nested fields unless the specification intentionally permits an extension location;
- duplicate stable identities within one import operation;
- unsupported artifact schemas;
- unsupported fields or operators for the selected schema;
- invalid Boolean policy structures;
- invalid bounds;
- unresolved governed-source references;
- unresolved upstream-stream references;
- self-reference;
- indirect dependency cycles;
- incompatible upstream schemas where the current stream contract prohibits them;
- unsupported expansion strategies;
- credentials, secrets, tokens, cookies, or transport-private configuration embedded in stream YAML; and
- executable content, arbitrary SQL, arbitrary Python, or arbitrary JSON-path predicates.

Unknown fields must never be silently discarded.

Validation errors must identify the relevant YAML path and provide an actionable operator message.

### 5. Governed source boundary

External stream YAML must reference a governed external-source profile by stable identity.

Stream YAML must not duplicate source-owned transport configuration such as:

- endpoint or archive URL;
- provider protocol details;
- credentials;
- User-Agent;
- pacing;
- concurrency;
- timeout;
- response bounds;
- retry/backoff;
- `Retry-After` policy; or
- future acquisition cursor state.

The normalized preview may show a read-only summary resolved from the governed source profile, but saving the stream must not modify that source profile.

### 6. Browser workflow redesign

Replace the current single dense form with a clear, progressive editor organized into these operator-facing sections:

1. **Identity**
2. **Input**
3. **Selection**
4. **Context and limits**
5. **Review and save**

The page must clearly distinguish:

- a new unsaved draft;
- an imported unsaved draft;
- an existing saved stream;
- a modified draft based on a saved revision; and
- the latest saved revision eligible for execution.

Internal implementation terminology should not dominate the default workflow.

### 7. Identity section

The identity section must support:

- display name;
- stable identity;
- description;
- enabled/disabled state where supported.

For new streams, stable identity may be derived from the display name but must remain visible and reviewable before save.

For existing streams, stable identity must not be silently changed.

Advanced or rarely edited identity details may be collapsed by default.

### 8. Input section

The operator must choose between:

- a governed external source; or
- one or more upstream streams.

External-source selection must present human-readable display names and concise source summaries. Raw internal IDs may be shown secondarily but must not be the primary label.

Upstream-stream selection must present useful operator context such as:

- stream display name;
- stable identity;
- artifact schema;
- latest saved revision;
- latest successful run where available;
- active membership count where available; and
- dependency/cycle validation status.

Selecting or changing input must update available schema capabilities and expansion options.

### 9. Selection section

Provide a usable common-path policy editor driven by schema capabilities.

The first slice must make common predicates straightforward for supported schemas, including where available:

- keywords or phrases;
- authors or participants;
- title or subject patterns;
- effective date bounds;
- artifact type/schema;
- source;
- registered structured attributes; and
- all/any match mode.

The existing bounded typed predicate model remains authoritative.

Nested Boolean groups, negation, and less common registered attributes must remain available through an **Advanced policy** mode rather than dominating the initial editor.

The UI must not imply that a field/operator is supported when the selected schema does not declare that capability.

### 10. Context and limits section

Show only schema-supported context-expansion controls.

For mailing-list messages, operator-facing controls may include:

- no expansion or connected-discussion expansion;
- required ancestor closure;
- descendant depth;
- direct-match maximum; and
- expanded-artifact maximum.

For artifact schemas without context expansion, do not show irrelevant mailing-list controls.

Use clear operator labels and concise explanations. Preserve the underlying TASK-025 expansion and bounds contracts.

### 11. Draft validation, preview, save, and execution hierarchy

Draft operations and execution operations must be visually and behaviorally separate.

Draft operations:

- Validate
- Preview bounded matches
- Import YAML
- Export or copy draft YAML where appropriate
- Save new stream or save new revision

Execution operations:

- Run saved stream
- Run dependency chain

Execution must be disabled unless a valid saved revision exists.

Validation and preview must never persist a revision or execute acquisition.

Saving must require an explicit operator action after validation.

### 12. YAML import in the browser

Support both:

- file upload; and
- pasted YAML text.

Import must follow a staged workflow:

1. parse;
2. validate format version and structure;
3. resolve governed-source and upstream references;
4. validate schema capabilities, predicates, expansion, bounds, and DAG topology;
5. normalize to the authoritative stream-definition contract;
6. present a readable normalized preview;
7. show warnings separately from errors;
8. show a semantic diff when importing over an existing stream/revision; and
9. require explicit confirmation before save.

Import must not implicitly run the stream.

Import must not implicitly modify a governed source profile.

### 13. YAML export in the browser

Allow export of:

- the currently selected saved revision; and
- the current valid draft, clearly labeled as unsaved, if supported by the chosen implementation.

Saved-revision export is mandatory.

The operator must be able to download canonical YAML and copy or inspect it.

The exported definition must reference stable source/stream identities rather than transient database row IDs.

### 14. CLI schema/template output

Add a CLI feature that prints the canonical stream-definition YAML schema/template.

The CLI must support a discoverable command consistent with existing RFI CLI conventions, equivalent in capability to:

```text
rfi streams --print-schema
```

or:

```text
rfi streams schema
```

Codex may select the exact command structure after inspecting the current CLI, but it must be obvious from `rfi --help` and relevant subcommand help.

The schema/template output must:

- be valid YAML;
- declare the supported format/schema version;
- document required and optional fields;
- include representative external-source and upstream-stream examples or clearly selectable variants;
- describe supported policy structures without becoming an unbounded language specification;
- identify that governed-source transport settings and secrets are excluded; and
- remain synchronized with the actual validator.

A machine-readable formal schema may accompany the human-readable YAML template, but the YAML output is required.

### 15. CLI validate, import, and export

Add CLI operations equivalent in capability to:

```text
rfi streams validate --file STREAM.yaml --state PATH
rfi streams import --file STREAM.yaml --state PATH
rfi streams export --stream STREAM_ID --state PATH
```

Exact syntax remains with Codex, subject to consistency with existing CLI patterns.

Required behavior:

- `validate` performs full structural, capability, reference, bounds, and DAG validation without saving;
- `import` validates and explicitly creates a new stream or new revision;
- `export` writes canonical YAML to stdout by default and optionally to a file;
- commands return nonzero exit status on validation, resolution, or persistence failure;
- errors are actionable and identify the failing YAML path where applicable;
- stdout remains suitable for redirection when exporting;
- diagnostics must go to stderr where necessary to preserve clean YAML stdout;
- CLI import must not execute the stream;
- CLI import must not alter governed-source profiles; and
- repeated import of semantically identical canonical YAML must behave deterministically and must not create accidental duplicate identities or meaningless revisions.

Codex must define and document whether semantically identical import is a no-op, an explicit already-current result, or an operator-confirmed new revision. Silent duplicate revision creation is not acceptable.

### 16. Import/export relationship to revisioning

Importing a definition whose stable identity does not exist may create a new stream after explicit validation.

Importing a definition whose stable identity already exists must not overwrite history.

It must either:

- create a new revision through the normal revision service; or
- reject and require an explicit mode indicating a new revision.

The browser and CLI must expose the distinction clearly.

Export must identify the stream and revision represented, either within canonical metadata or through a clearly documented export convention, without making revision-row IDs part of the reusable semantic definition unless necessary.

### 17. Semantic diff

When importing over an existing stream, provide a semantic diff based on normalized definitions rather than raw YAML text.

The diff should identify changes in categories such as:

- identity metadata;
- input source or upstream dependencies;
- artifact schema;
- selection policy;
- expansion;
- bounds; and
- enabled state.

Formatting-only YAML differences must not appear as semantic changes.

A textual CLI diff mode is optional, but the browser semantic diff is required.

### 18. Cross-surface equivalence

A definition created in the browser and exported to YAML must validate and import through the CLI to produce the same normalized semantic definition.

A valid YAML definition imported through the CLI must render correctly in the browser editor.

No surface may introduce hidden defaults that change execution semantics without appearing in canonical export.

### 19. Documentation

Update operator and architecture documentation to cover:

- the redesigned Streams page;
- common-path versus advanced policy editing;
- canonical stream YAML;
- browser import/export;
- CLI schema/template printing;
- CLI validation, import, and export;
- revision behavior;
- governed-source boundaries;
- examples for an external mailing-list stream and a derived stream;
- unsupported and deferred capabilities; and
- troubleshooting for validation and reference-resolution errors.

The documentation must state that a stream definition does not contain provider credentials or transport policy.

### 20. Existing behavior must remain intact

Preserve:

- SQLite as the only structured authority;
- schema version and migration discipline;
- TASK-025 revision history;
- DAG validation;
- finite schema capability registry;
- registered projection and expansion handlers;
- bounded preview and execution;
- atomic stream publication;
- artifact-retention independence;
- governed-source transport policy;
- acquisition failure semantics;
- shared operator navigation;
- artifact browser behavior; and
- existing REST identity and route conventions unless a change is required and justified.

---

## Required YAML Capabilities

The canonical format must support at least these two use cases.

### External governed-source stream

A definition equivalent in capability to:

```yaml
schema_version: 1
stream:
  stream_id: linux-block-storage
  display_name: Linux Block Storage
  description: Linux block-layer discussions relevant to storage architecture
  enabled: true

  input:
    kind: external_source
    source_profile_id: linux-block
    artifact_schema: mail.message

  selection:
    all:
      - any:
          - field: searchable_text
            operator: contains_any
            values:
              - blk-mq
              - zoned
              - zone append
              - smr
          - field: authors
            operator: contains_any
            values:
              - Jens Axboe
              - Damien Le Moal
      - field: effective_timestamp
        operator: on_or_after
        value: "2026-01-01"

  expansion:
    strategy: connected_discussion
    ancestor_closure: required
    descendant_depth: 3

  bounds:
    direct_matches: 25
    total_artifacts: 200
```

### Derived stream

A definition equivalent in capability to:

```yaml
schema_version: 1
stream:
  stream_id: smr-discussions
  display_name: SMR Discussions
  description: SMR-related discussions derived from the Linux block stream
  enabled: true

  input:
    kind: upstream_streams
    stream_ids:
      - linux-block-storage
    artifact_schema: mail.message

  selection:
    any:
      - field: searchable_text
        operator: contains_any
        values:
          - smr
          - host-managed
          - host-aware
          - zone append

  expansion:
    strategy: connected_discussion
    ancestor_closure: required
    descendant_depth: 3

  bounds:
    direct_matches: 50
    total_artifacts: 300
```

These examples are illustrative. Codex may refine field names and normalized structure while preserving the required semantics and human readability.

---

## Functional Requirements

### Browser

The Streams page must allow an operator to:

- create a stream through the common-path editor;
- switch to advanced policy editing;
- import YAML by file;
- import YAML by paste;
- validate without saving;
- preview bounded matches;
- inspect normalized configuration;
- compare against the existing saved revision;
- save a new stream;
- save a new revision;
- export canonical YAML;
- run only a valid saved revision; and
- navigate clearly between configured streams and the editor.

### CLI

The CLI must allow an operator to:

- discover stream commands from help;
- print the canonical YAML schema/template;
- validate a YAML file;
- import a new stream;
- import a new revision explicitly;
- export a selected stream revision;
- redirect canonical YAML cleanly to a file; and
- receive stable, actionable exit codes and errors.

### API/service

The application must provide reusable service operations for:

- parsing;
- validation;
- normalization;
- reference resolution;
- semantic comparison;
- canonical serialization;
- revision creation; and
- export retrieval.

Browser and CLI must call these shared operations rather than reimplementing them independently.

---

## Non-Goals

This task does not include:

- a general workflow engine;
- arbitrary executable filters;
- arbitrary SQL, Python, JavaScript, or JSON-path policies;
- dynamic third-party plugins;
- secrets or credentials in stream YAML;
- YAML-based governed-source creation or modification;
- automatic acquisition or execution on import;
- scheduled polling;
- durable Lore cursor implementation;
- multi-process distributed rate coordination;
- synthetic artifact generation;
- report generation;
- stream deletion or evidence pruning;
- bulk multi-document package import beyond the bounded canonical format selected for this task; or
- preserving YAML comments and original formatting.

---

## Acceptance Criteria

TASK-026 is complete only when all of the following are demonstrated.

### UI usability

- The page is organized into the required progressive sections.
- A new operator can identify the sequence: identity → input → selection → context/limits → review/save.
- Raw repository IDs are not the primary labels in selectors.
- Common mailing-list filtering does not require direct manipulation of low-level predicate rows.
- Advanced typed policy editing remains available.
- Unsupported expansion controls are hidden for schemas that do not support them.
- Unsaved draft state is visually explicit.
- Run actions are unavailable until a valid saved revision exists.

### YAML parsing and validation

- Valid external-source YAML parses and validates.
- Valid derived-stream YAML parses and validates.
- Unknown schema version fails.
- Unknown field fails.
- Invalid operator fails.
- Unsupported field for schema fails.
- Missing governed-source reference fails.
- Missing upstream-stream reference fails.
- Self-reference fails.
- Indirect cycle fails.
- Invalid bounds fail.
- Embedded secret-like transport fields fail.
- Errors identify actionable YAML paths.

### Canonicalization and round trip

- Saved revision exports deterministically.
- Exported YAML validates.
- Export → parse → normalize preserves semantic identity.
- Browser-created definition exported and imported through CLI preserves semantic identity.
- CLI-imported definition renders correctly in the browser.
- Formatting-only YAML changes do not produce semantic differences.
- Semantic changes do produce a readable diff.

### Revision behavior

- Import of a new stable identity creates a new stream only after explicit save/import.
- Import of an existing identity never overwrites prior revisions.
- Existing-identity import requires or clearly selects new-revision behavior.
- Semantically identical re-import has explicitly documented deterministic behavior.
- Validation and preview never create revisions.

### CLI schema/template

- Help exposes the schema/template command.
- The command prints valid YAML.
- The output includes or points clearly to both external-source and upstream-stream forms.
- The output is synchronized with the validator.
- Output explains required fields, optional fields, bounds, policy structure, and excluded transport/secrets.
- The output can be redirected to a file without log contamination.

### CLI operations

- Validate succeeds for valid YAML and fails nonzero for invalid YAML.
- Import creates the expected stream/revision and does not run it.
- Export emits canonical YAML.
- File-output mode works if implemented.
- Diagnostics preserve clean stdout for export.
- CLI and browser use the same normalization and validation services.

### Preservation of existing architecture

- Stream publication remains atomic.
- Artifact retention remains independent of memberships.
- No evidence bytes are duplicated by YAML import.
- Governed source profiles remain authoritative for transport configuration.
- No browser-only or YAML-only persistence representation is introduced.
- Existing TASK-025 tests continue to pass.

---

## Verification Requirements

Codex must produce a complete verification package.

### 1. Focused automated tests

Include focused tests for:

- browser editor section rendering and state transitions;
- schema-aware common controls;
- advanced policy behavior;
- YAML file import;
- pasted YAML import;
- canonical export;
- safe parsing;
- unknown-field rejection;
- unsupported predicate rejection;
- missing source rejection;
- missing upstream rejection;
- direct and indirect cycle rejection;
- semantic diff;
- external-source round trip;
- derived-stream round trip;
- browser-to-CLI equivalence;
- CLI-to-browser equivalence;
- CLI schema/template output;
- CLI validate/import/export;
- revision preservation;
- semantically identical re-import behavior;
- validation/preview non-persistence; and
- execution disabled for unsaved drafts.

### 2. Full repository validation

Run the repository-standard complete validation command and capture:

- focused tests;
- full test suite;
- lint;
- formatting;
- type checks;
- documentation checks;
- design-baseline checks;
- fixture/archive-integrity checks;
- sensitive-data scan;
- diff check; and
- isolated copied-tree validation.

### 3. Real-browser proof

Using a fresh or controlled state:

1. open Streams;
2. create a Linux mailing-list stream through the common-path form;
3. validate and preview;
4. save it;
5. export canonical YAML;
6. create or revise a stream by importing YAML;
7. inspect normalized preview and semantic diff;
8. confirm no save occurs before explicit confirmation;
9. confirm run controls are disabled for an unsaved draft;
10. save and then run or prove the saved run control is enabled;
11. confirm browser console has no unexpected warnings or errors.

Capture exact URLs, visible states, and relevant API calls.

### 4. CLI proof

Capture exact commands and outputs proving:

- help discoverability;
- schema/template printing;
- schema output redirected to a file;
- validation of valid YAML;
- rejection of invalid YAML;
- import of a new stream;
- explicit import as a new revision;
- export to stdout;
- export to a file if supported;
- canonical round trip; and
- no execution triggered by import.

### 5. Negative architectural proof

Demonstrate that the implementation does not:

- persist browser-only definitions;
- maintain a separate YAML authority;
- accept credentials or source transport policy in stream YAML;
- silently ignore unknown fields;
- execute on import;
- overwrite revision history;
- duplicate immutable artifact bytes;
- bypass DAG validation;
- introduce arbitrary executable filters; or
- alter governed-source profiles through stream import.

### 6. Review package contents

The package must include:

- task ticket;
- completion report;
- architectural summary;
- UI before/after summary;
- canonical YAML specification;
- CLI command reference;
- representative external and derived stream YAML fixtures;
- focused-test output;
- full-validation output;
- browser proof;
- CLI proof;
- round-trip proof;
- negative proofs;
- migration statement;
- changed-file inventory;
- cumulative patch;
- repository status;
- ZIP integrity proof; and
- SHA-256 checksum.

---

## Documentation Updates

Update at least:

- operator CLI documentation;
- stream architecture/design documentation;
- stream configuration documentation;
- YAML format documentation;
- relevant ADR or design decision record;
- task roadmap/status;
- design baseline; and
- any help text or examples needed for discoverability.

---

## Completion Report Requirements

The final Codex report must state:

1. the exact browser workflow delivered;
2. the exact canonical YAML format/version;
3. the exact CLI command structure;
4. the behavior of semantically identical re-import;
5. how existing stream revisions are protected;
6. how browser and CLI share one normalization/validation path;
7. how governed source boundaries are preserved;
8. all verification results;
9. the review-package location and checksum;
10. all known limitations and deferred capabilities;
11. repository branch and commit status; and
12. whether any files remain unstaged or uncommitted.

---

## Definition of Done

TASK-026 is done when RFI-1 provides a usable, understandable Stream Configuration experience and a canonical, revision-safe YAML workflow across browser and CLI, including a discoverable CLI command that prints the supported YAML definition schema/template.

The implementation must retain TASK-025’s architectural guarantees, avoid a second configuration authority, and include a complete verification package suitable for independent review.
