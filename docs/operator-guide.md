# RFI-1 Operator Guide

This is the canonical, repository-owned operating guide for the RFI-1 local administration
application. It describes the implemented product through TASK-031, including the first-class
Linux mailing-list workflow. The administration server renders this same file at
`/help`; no network connection or second documentation server is required.

Help opens through an ordinary named browser target. A browser normally reuses the existing
`rfi-operator-help` tab or window when Help is invoked again. Browser settings ultimately decide
whether the target appears as a tab or window, whether it may be placed on another monitor, and
whether a new browsing context is permitted. RFI-1 does not claim control over those choices.

Use the topic list or browser Find to search the complete guide. Topic identifiers in links are
explicit application contracts and do not depend on heading wording.

<!-- help-topic: getting-started -->
## Getting started

### Purpose

Initialize a local repository, optionally seed example catalog records, and start the integrated
administration server against the same state directory used by later commands.

### Prerequisites

- Run commands from the repository with the project environment installed.
- Choose one state path and use it consistently. The default is `.artifacts/runtime/rfi-1`.
- Bind the unauthenticated server only where appropriate. The default is `127.0.0.1:8765`.

### Normal operating sequence

```sh
.venv/bin/rfi init --state .artifacts/runtime/rfi-1
.venv/bin/rfi seed --state .artifacts/runtime/rfi-1
.venv/bin/rfi admin --state .artifacts/runtime/rfi-1
```

`init` creates empty compatible SQLite state and an immutable content store. It does not seed.
`seed` explicitly adds missing starter concepts and firms; repeating it is idempotent. `admin`
opens existing state, prints the local URL and state path, and does not seed, migrate, repair, or
open a browser. Stop the foreground server with Ctrl-C.

Open the printed URL. Use the persistent top navigation for Concept Catalog, Target Firms, Firm
Profiles, External Sources, Pull Sources, Linux Mailing Lists, Streams, and Artifacts. Every page
has a Help action.
Help is a separate browsing context, so invoking it does not submit, reset, close, or navigate the
current form.

### Common problems and recovery

- Missing state: run `rfi init` against the exact intended path.
- Legacy-only, mixed, corrupt, or incompatible state: startup fails closed. Do not move files into
  a new state directory piecemeal; restore a verified backup or choose a fresh path.
- Port already in use: choose another `--port` and use the printed URL.
- Unexpected repository: stop the server and compare the printed State path with the path passed
  to other commands.

Related topics: [repository model](#repository), [repository protection](#repository-protection),
and [CLI equivalents](#cli-reference).

<!-- help-topic: repository -->
## Repository and state model

### Purpose

Understand what is authoritative before editing, running acquisition, exporting, or restoring.

The selected state directory contains `repository.sqlite3`, the authoritative structured state,
and `content/sha256/...`, the authoritative immutable artifact bytes. SQLite records repository
identity and schema, firms and concepts with immutable revisions, firm source-profile revisions,
governed external sources, acquisition attempts and observations, pull runs, mailing-list state,
and stream definitions, runs, memberships, and lineage. Artifact bytes are not stored in SQLite.

Browser preferences are disposable local browser state. Help content, the source-profile template,
and application documentation are version-controlled repository sources. Help reads no runtime
repository records and changes no state.

### State semantics

- List, detail, history, artifact inspection, Help, export, and verification read state.
- Validate checks proposed state and never persists it.
- Preview evaluates normalized or derived behavior and never persists or executes it.
- Save or import is explicit and may create an immutable revision.
- Pull, stream Run, stream Run dependency chain, and mailing-list acquire execute work and retain
  durable results according to their workflow contracts.
- Export emits a representation and does not change the repository.
- Backup creates a verified archive; restore writes only to a fresh destination.

The local console is an unauthenticated, single-operator administration surface, not a production
daemon. Local readers can operate during one local writer, but multi-host writers are unsupported.

Related topics: [revisions and lineage](#revisions-lineage), [Artifacts](#artifacts), and
[repository protection](#repository-protection).

<!-- help-topic: concepts -->
## Concept Catalog

### Purpose

Browse governed business definitions and create immutable concept revisions. Concept records are
definitions and derivation instructions, not acquired evidence.

### When to use this page

Use Concept Catalog to search by identity, name, alias, hint, keyword, status, tag, or validity;
inspect a definition and history; or author a new definition/revision.

### Prerequisites

The repository must be [initialized](#getting-started). Starter concepts are optional and are
created only by `seed`. Related concept IDs and deterministic method inputs should already exist
when referenced.

### Typical workflow

1. Search or select a concept, or choose `New concept`.
2. Complete the typed editor. Use field-level `i` controls for schema help.
3. Choose `Validate draft`. This checks the proposal without persistence.
4. Choose `Preview new revision` and inspect the proposed status, changes, validity, and warnings.
5. Choose `Save new revision`. Creation makes revision 1; editing appends a revision.
6. Inspect the detail page and Revision history.

### Controls, actions, and state changes

Search, filters, detail, history, field help, validation, and preview are read-only or operate only
on browser draft state. `Save new revision` and `Retire` append immutable repository revisions.
They never rewrite older revisions. Samples illustrate expected shapes and do not become evidence.
Cancel or close leaves repository state unchanged; dirty editors warn before destructive page
navigation.

### Common problems and recovery

Validation links point to fields requiring correction. A revision conflict means another current
revision was published after this editor loaded; close or copy needed draft values, reload the
latest revision, and reapply the intended changes. Invalid deterministic inputs, units, method
shapes, validity intervals, and duplicate repeated values must be corrected before preview/save.
A failed validation or save leaves the entered form available.

### CLI equivalent

There is no general concept-edit CLI. `rfi seed` adds only missing repository-owned starter
concepts. Use the browser for normal concept authoring.

Related topics: [Target Firms](#firms), [repository model](#repository), and
[troubleshooting](#troubleshooting).

<!-- help-topic: firms -->
## Target Firms

### Purpose

Maintain the durable authority for who a research target is and how the operator recognizes it.
Firm identity is separate from source configuration, acquired evidence, streams, concepts, and
intelligence.

### When to use this page

Use Target Firms before configuring firm-owned acquisition. Search and filter existing firms,
inspect recognition metadata and history, or create/revise a target identity.

### Prerequisites

The repository must be [initialized](#getting-started). Choose a stable `firm_id`; it remains the
downstream reference. Do not encode mutable legal or market facts into that ID.

### Typical workflow

1. Choose `New target firm`, or select a firm and choose `Edit / create revision`.
2. Enter canonical and legal names, aliases, identifiers, domains, location, classifications,
   technology focus, source-discovery hints, notes, relevance, status, and validity.
3. Choose `Validate draft`; nothing is saved.
4. Choose `Preview new revision` and review the change summary and recognition metadata.
5. Choose `Save new revision`.
6. Inspect the firm detail and Revision history, then continue to
   [Firm Profiles](#source-profiles).

### What changes repository state

`Save new revision` creates a complete immutable revision and advances the current selector.
`Retire` also appends a revision; it does not delete the firm. Validation, preview, list/detail,
search, filter, and historical inspection do not persist. Source-discovery hints are operator
guidance and never become evidence.

### Common problems and recovery

Current firms cannot share a normalized domain or the same identifier kind, market, and value.
Resolve the real identity rather than deleting evidence. A stale revision must be reloaded before
retrying. A failed validation or save keeps the form values. Historical revisions are inspect-only.

### CLI equivalent

`rfi seed --file firms.yaml` validates a complete external firm batch before creating any firm and
publishes new firms transactionally. It does not revise existing firms. `rfi seed --print-schema`
prints the canonical external catalog template.

Related topics: [Firm Source Profiles](#source-profiles), [acquisition](#acquisition), and
[Artifacts](#artifacts).

<!-- help-topic: source-profiles -->
## Firm Source Profiles

### Purpose

Configure firm-owned acquisition intent using the repository-owned canonical artifact template.
This page is for SEC filings and other firm artifacts. Lore/public-inbox transport belongs under
[External Sources](#external-sources), not in a firm profile.

### Prerequisites

A [target firm](#firms) must exist. A profile may begin as displayed canonical defaults; defaults
are not a saved revision. Retrieval candidates must use modes and fields permitted by each
artifact item.

### Typical workflow

1. Choose `Target firm` or follow a configuration-problem link from
   [Pull Sources](#acquisition).
2. Expand an artifact category and artifact item.
3. Enable intended artifacts and add prioritized retrieval candidates.
4. Fill the mode-specific fields and optional operator notes.
5. Choose `Validate`. This checks the draft and saves nothing.
6. Choose `Save source-profile revision`.
7. Confirm the profile revision in the page history, then inspect
   [readiness](#source-readiness) under [Pull Sources](#acquisition).

### Controls and state changes

`Reload profile`, firm selection, expansion, and history inspection read state. Field changes live
only in the page draft. `Validate` is non-persistent. `Save source-profile revision` publishes one
immutable profile revision with optimistic current-revision checking. It does not create a target
firm revision and does not retrieve anything. Historical profiles are read-only.

The application snapshots the selected profile revision when a Pull Workflow starts. Later profile
edits do not rewrite that run's configuration history.

### Common problems and recovery

If Save is disabled, select a firm and make a valid change. An enabled artifact with no compatible,
complete candidate is incomplete and will not be runnable. Follow the linked configuration problem
from Pull Sources back to the exact firm and artifact. On revision conflict, reload the current
profile and reapply the intended edit. Preserve candidate priority because adapters attempt
supported candidates deterministically.

### CLI equivalent

There is no general firm source-profile editing CLI. `rfi pull` consumes saved profiles; it does
not create them.

Related topics: [source readiness](#source-readiness), [Pull Sources](#acquisition), and
[External Sources](#external-sources).

<!-- help-topic: source-readiness -->
## Source readiness and run eligibility

### Purpose

Decide whether configuration can be executed and distinguish enabled intent from actual adapter
support.

For firm acquisition, Pull Sources lists firms only after a source-profile revision exists. Each
row shows enabled, runnable, and incomplete artifact counts. Enabled means operator intent.
Runnable means at least one configured candidate matches a registered adapter capability.
Incomplete means correction is required. Unsupported modes remain explicit skipped or
configuration-problem outcomes; no hidden fallback is selected.

For streams, a definition must be valid, saved, current, and enabled before Run is available.
External-input streams also require a governed External Source whose stable ID matches the saved
definition. Derived streams require compatible saved upstream streams and an acyclic topology.

Readiness evaluation reads current configuration. It does not retrieve, publish a revision, or
create a run. Execution is always a separate operator action.

Recovery sequence: inspect counts, open the relevant [Firm Profile](#source-profiles) or
[External Source](#external-sources), validate and save the correction, then return to
[Pull Sources](#acquisition) or [Streams](#streams), refresh, and re-evaluate. Never change a saved
source identity to repair history; create a new source identity where its immutable policy must
change.

Related topics: [Firm Source Profiles](#source-profiles), [External Sources](#external-sources),
[acquisition](#acquisition), and [streams](#streams).

<!-- help-topic: external-sources -->
## External Sources

### Purpose

Create and inspect repository-global governed Lore/public-inbox source profiles shared by streams.
These are not target-firm profiles. They own provider/list/endpoint identity and bounded transport
policy; streams reference only the stable source ID.

### Prerequisites

Know the stable source ID, display name, Lore list identity, HTTPS archive endpoint, honest request
User-Agent, pacing, concurrency, timeout, response-size, retry, and backoff limits. The current UI
supports the `Lore / public-inbox` provider.

### Typical workflow

1. Choose `New Lore source`.
2. Complete Identity and provider and Bounded transport policy.
3. Choose `Validate profile`. The complete proposal is checked and nothing is saved.
4. Choose `Save governed source`.
5. Select the saved source to inspect its immutable profile.
6. Choose `Use in Stream Configuration` to continue to [Streams](#streams) with the stable source
   selected.

### State changes and immutability

`Save governed source` creates the repository-global source identity. An exact existing profile is
idempotent. Saved source identity and transport policy are immutable because acquisition and stream
history may refer to them. `Clone as new source` copies fields into an unsaved draft; choose a new
stable ID before saving. Validation, refresh, inspect, and clone preparation do not persist or
contact the archive. Stream definitions cannot override endpoint, credentials, request identity,
pacing, retry, timeout, response bounds, or cursors.

### Common problems and recovery

Use an HTTPS endpoint and values within the displayed bounds. If policy must change, inspect the
old source, choose `Clone as new source`, assign a new stable ID, validate, save, and
[revise the stream](#streams) to refer to the new source. Do not expect this page to acquire
messages; bounded live preview/acquire is currently [CLI-only](#cli-reference).

### CLI equivalent

```sh
rfi mailing-list --state STATE configure-lore-source \
  --source SOURCE_ID --list-id LIST_ID --display-name NAME \
  --archive-base-url HTTPS_URL
rfi mailing-list --state STATE sources
```

Related topics: [streams](#streams), [source readiness](#source-readiness), and
[Artifacts](#artifacts).

<!-- help-topic: acquisition -->
## Pull Sources and acquisition workflow

### Purpose

Execute the shared durable Pull Workflow for selected firms and interpret per-firm, per-artifact,
and per-attempt outcomes.

### Prerequisites

A [target firm](#firms) and a saved [Firm Source Profile](#source-profiles) revision must exist. At
least one artifact should be enabled and [runnable](#source-readiness). Live SEC retrieval requires
the governed runtime request identity where the selected adapter requires it. This page is not the
Lore/public-inbox acquire interface.

### Acquisition procedure

1. [Create or select a firm](#firms) under Target Firms.
2. [Configure, validate, and save its Firm Source Profile](#source-profiles).
3. Open Pull Sources and inspect [enabled, runnable, and incomplete counts](#source-readiness).
4. Select one or more firms and choose `Pull selected firms`.
5. Follow Workflow progress. Starting the pull persists a run and executes configured retrieval.
6. Read Completed results and expand attempt details for adapter, priority, status, diagnostic,
   and details.
7. Follow any linked `configuration_problem` to the exact
   [Firm Profile](#source-profiles) artifact and correct it.
8. Open [Artifacts](#artifacts) and locate the retained firm artifact and its acquisition
   observation.

The run snapshots each firm's current source-profile revision, expands enabled artifacts,
determines attemptability, executes supported candidates independently, ingests successful bytes,
records results, and summarizes execution. One artifact failure does not erase another artifact's
success. Outcomes include success, duplicate, no change, skipped, configuration problem, and
retrieval failure. A completed-results URL retains `run_id` for browser Back/reload inspection.

### What changes state

Selecting firms, refreshing, reading readiness, and viewing results do not mutate configuration.
`Pull selected firms` creates a durable run and may create attempts, observations, logical-document
projections, immutable content objects, and checkpoints. Exact duplicate bytes remain content
idempotent while each materially distinct successful acquisition creates its own observation.

### Common problems and recovery

- No firms listed: save a [Firm Source Profile](#source-profiles) first.
- Incomplete artifact: follow its configuration link, correct and save a
  [profile revision](#source-profiles), then start a new pull. Existing run history remains
  unchanged.
- Retrieval failure: inspect attempt diagnostics, verify runtime request identity/network access,
  and retry as a new run when corrected.
- Partial run: inspect every artifact outcome; successful evidence remains retained.

### CLI equivalent

```sh
rfi pull --state STATE --firm FIRM_ID
rfi pull --state STATE --firm FIRM_A --firm FIRM_B
rfi pull --state STATE --all-configured
```

Related topics: [Firm Source Profiles](#source-profiles), [source readiness](#source-readiness),
[Artifacts](#artifacts), and [troubleshooting](#troubleshooting).

<!-- help-topic: linux-mailing-lists -->
## Linux Mailing Lists

### Purpose

Use **Linux Mailing Lists** to operate bounded Lore-backed evidence streams without first
configuring External Sources or the generic Streams editor. The page coordinates those existing
repository objects behind an operations-first summary and remains the normal starting point when
the intended outcome is collecting Linux kernel mailing-list discussions.

### Prerequisites

The repository must be initialized and Lore must be reachable over HTTPS. No governed source or
stream needs to exist beforehand. The initial live test requires a start date, through date, and
hard direct/total message limits. Relevance controls are optional.

### Typical workflow

1. Select a saved stream card. Its summary shows purpose, source, relevance, hard limits, effective
   last fetch, latest acquisition result, and any incomplete/partial warning.
2. Choose **Fetch up to date**. RFI immediately queues deterministic bounded acquisition from a
   two-day overlap before complete repository coverage through today.
   If a window contains more direct messages than one bounded run permits, RFI continues through
   additional bounded Lore pages. Coverage advances only after the complete page sequence and its
   required relationship context finish successfully.
3. Follow queued, started, completed, failed, or cancellation state in **Fetch queue** while using
   the rest of the page. **Fetch All up to date** queues every eligible stream through the same FIFO
   and duplicate suppression.
4. Choose **Edit** only when configuration must change. Saving an existing stream creates its next
   immutable authoritative revision and displays a modal confirmation.
5. Choose **Add mailing list** for a new stream, then configure at most 31 initial days, optional
   relevance, and hard limits. Review writes nothing; **Create and test stream** saves and retrieves
   one bounded sample.
6. Inspect direct/context labels, relationships, Lore links, and completeness. Use **Artifacts** for
   the complete retained-evidence view.

### State and side effects

Archive validation and Review are read-only. Create and Save change durable source or immutable
stream-revision state. Test and Fetch contact Lore, preserve exact message bytes and provenance,
and record bounded acquisition runs. An exact Message-ID rejected by the selected archive may be
retried through Lore `/all`; retained fallback artifacts are explicitly flagged in provenance and
the message viewer. The queue and status panel are process-local operational
state, not a scheduler or audit store; restart clears them but preserves durable evidence and
reconstructed effective coverage. There is no unbounded mirror.

The page reports two independent dimensions from authoritative records. **Configuration ready**
means the governed source and saved stream revision are executable for a later bounded run.
**Test evidence complete and connected**, **incomplete or truncated**, **empty**, **partial**,
**failed**, or **not run** describes only the latest bounded test evidence. Configuration readiness
never means a truncated test was complete.

### Common problems and recovery

- An invalid Lore URL must be corrected to one canonical HTTPS archive URL.
- If a prior **External Sources** record owns the generated archive identity with a different URL,
  the workflow refuses to replace it. Sources created through current validation store supported
  trailing-slash and host-case variants canonically, so their stable identity is reused. The exact
  malformed, unused TASK-028 legacy Linux Block record is corrected once by schema migration v5,
  preserving its source ID and both persisted projections. Every other mismatch, and every source
  with a durable dependency, remains unchanged and requires a separately reviewed central
  source-governance migration.
- A connectivity failure persists nothing during validation; retry is safe.
- If governed-source creation succeeds but stream creation fails, the page identifies that durable
  partial state. Retry reuses the source rather than duplicating it.
- A failed or partial acquisition is not reported as verified. Any retained evidence remains
  inspectable, and the displayed retryability explains the next action.
- **Reload saved streams** names the state being reloaded and protects unsaved values.
- **Cancel / Abandon all Fetches** requires confirmation, abandons queued work, and requests safe
  cooperative cancellation of a running acquisition. Already durable evidence is not removed.

Related topics: [choosing a Lore list](#choosing-lore),
[bounded acquisition](#bounded-mailing-list-acquisition), [discussion context](#discussion-context),
[generated identities](#generated-identities), [lifecycle](#mailing-list-lifecycle),
[incomplete results](#incomplete-mailing-list-results), [rerun and recovery](#mailing-list-retry),
and [Lore connectivity](#lore-connectivity).

<!-- help-topic: choosing-lore -->
## Choosing a Lore mailing list

The catalog provides human-readable Linux block, NVMe, SCSI, and main-kernel archives. A custom
archive is supported only when its URL has exactly the form
`https://lore.kernel.org/ARCHIVE/`. RFI derives the archive identity from that canonical path,
rejects other hosts, credentials, ports, queries, fragments, and nested paths, then verifies a
real Atom feed before claiming reachability. Selection and validation do not create repository
state.

<!-- help-topic: bounded-mailing-list-acquisition -->
## Bounded mailing-list acquisition

The initial date window is required, cannot extend into the future, and cannot exceed 31 days.
Direct seed messages are capped at 25 and the complete retained result at 100; normal defaults are
5 and 50. Reply depth is capped at 10. The governed source also enforces response-size, timeout,
pacing, concurrency, retry, and backoff policy. Fetch All queues each eligible stream as a separate
bounded job; it is not an unbounded selection. No archive mirror, implicit history, daemon, or
scheduled polling is available.

Keywords search message subject/body, subjects search the Subject field, and participants search
the From field through Lore's bounded public-inbox query interface. Values within one populated
control are alternatives; populated control groups and the date window all constrain the seeds.

<!-- help-topic: discussion-context -->
## Direct matches and discussion context

A direct match satisfies the configured Lore seed criteria. Context-only messages do not need to
match those criteria: they are retained as required ancestors or bounded descendants so the
discussion is not misleadingly disconnected. Immediate reply authority comes from message headers,
not normalized subjects. A required ancestor that returns HTTP 404 from both the configured archive
and Lore's cross-list `/all/` archive becomes an explicit immutable tombstone. The tombstone records
the attempted locations and statuses, contains no synthesized email, and may close the structural
reply path so repository coverage can advance. Other missing connectors, cycles, response limits,
and incomplete thread feeds remain explicit. Every result record shows its inclusion reason,
parent/root context, depth, reply count, connectivity state, and Message-ID. Retrieved messages link
to Lore; tombstones are labeled instead of offering a dead canonical link.

<!-- help-topic: generated-identities -->
## Generated mailing-list identities

Operators provide a human-readable stream name, not repository IDs. RFI derives the governed-source
identity from the canonical Lore archive and a stream identity from the name. Existing equivalent
records are reused. A different record that already owns the generated identity causes RFI to add
a deterministic digest suffix; it never silently overwrites or asks the operator to coordinate row
identifiers. Review shows generated identities as secondary inspection information before save.

<!-- help-topic: mailing-list-lifecycle -->
## Mailing-list validation, creation, and testing

**Validate archive connectivity** performs a live structural Lore check and writes nothing.
**Review mailing-list stream** validates and normalizes the complete draft and writes nothing.
**Create and test stream** first creates or resolves the governed source and immutable stream
revision, then performs the bounded acquisition, stores exact evidence and provenance, publishes
discussion state, executes the saved stream revision, and displays results. Later acquisition is
the same explicit bounded action; it is not validation, save, scheduling, or background polling.

Progress identifies archive validation, source resolution, stream revision, retrieval, context,
evidence storage, and stream verification. Overall success is withheld when any later stage fails.

<!-- help-topic: incomplete-mailing-list-results -->
## Incomplete mailing-list results

`continuation_pending` means the bounded run succeeded, retained valid evidence, and saved an
ancestry or reply frontier for the next run. Repository coverage remains withheld, but complete
stored parent paths remain connected. `policy_truncated` means configured reply depth intentionally
ended expansion and is a valid terminal coverage state. `failed` means provider, integrity, or
execution work prevented terminal progress; valid prior progress remains inspectable and retry may
resume its durable frontier. `incomplete` means required context was unavailable. `quarantined` means
identity or relationship integrity failed. A partial transport outcome may retain useful evidence
but does not establish successful verification. The result page shows active bounds, the
direct/context breakdown, **Configuration ready** as the saved definition's executability, and a
separate **Continuation pending**, **Policy boundary reached**, or **Failed** status where applicable.
Disconnected or structurally incomplete material
is never labeled complete.

`Connected with unavailable ancestors` means relationship closure succeeded through one or more
confirmed Lore 404 tombstones. This state may advance repository coverage because the unavailable
connector is durably and explicitly represented. It is not equivalent to having the ancestor's
email content, and the tombstone remains visible in retained evidence. A 403, timeout, rate limit,
5xx response, malformed response, or single-path 404 never creates a tombstone.

Acquisition-run outcome and discussion connectivity are separate authorities. A run remains
partial when any selected component fails, while each retained message is projected from its own
header-derived parent path. A missing ancestor therefore keeps only that unresolved chain in
**Incomplete or quarantined**; independent components whose paths close at retained roots remain
connected. The supported `rfi mailing-list --state PATH rebuild` command applies the same derivation
offline without changing historical manifests or immutable message artifacts.

<!-- help-topic: mailing-list-retry -->
## Rerunning a mailing-list stream

Select a saved stream to inspect its summary and latest acquisition evidence. **Fetch up to date**
uses deterministic two-day overlap and one or more gap-free, at-most-31-day windows through today.
Duplicate queued/running work is ignored. Immutable artifact content, tombstones, and relationships
remain idempotent. If a relationship run reaches its record allowance, the same seed page resumes
automatically from the SQLite manifest before later seed pages or date windows. A retryable Lore
failure may be queued again; correct terminal URL, selection, or validation errors in **Edit** first.
Pending or failed windows retain evidence but do not advance effective coverage. Confirmed-
unavailable ancestor tombstones do not force the same window to remain permanently incomplete.

<!-- help-topic: lore-connectivity -->
## Troubleshooting Lore connectivity

Confirm the URL uses the supported canonical `https://lore.kernel.org/ARCHIVE/` form. A malformed
or non-Atom response is an unsupported archive, while timeout, rate limit, or transient server
failure is retryable according to the governed policy. Validation writes nothing. During test,
transport failure before useful retrieval records a failed run with no evidence; failure after
useful retrieval records an explicit partial run. Raw network exceptions, HTML bodies, and stack
traces are not exposed to the operator.

<!-- help-topic: artifacts -->
## Artifacts and retained evidence

### Purpose

Inspect exact repository evidence through read-only projections for Firm artifacts, Development
mailing lists, and Artifact streams.

### Prerequisites

[Acquisition](#acquisition) or [stream execution](#streams) must have retained material for it to
appear. Empty branches are a valid state. This page never fetches the original source to build its
repository tree.

### Typical workflow

1. Expand a projection, then its lazy branches.
2. Select a firm document, mailing-list message, or stream membership.
3. Inspect normalized metadata, identities, checksum, provenance, observation/run information,
   inclusion reason, and lineage as applicable.
4. Use Previous observation and Next observation for repeated firm-document observations.
5. Use `Open stored document in new tab` for exact retained bytes. `Open original source` is
   available only when provenance exposes a location.

### State behavior and safety

The Artifact Repository is read-only. Navigation, content preview, metadata collapse, tree resize,
and observation movement do not persist repository state. Layout preferences are disposable
browser-local values. Stored content is integrity checked and served with restrictive headers;
HTML/PDF/text preview uses an isolated sandbox, and unsupported media remains downloadable rather
than being rendered as active console content.

Firm artifacts distinguish stable logical `document_id`, byte-derived `artifact_id`, immutable
`observation_id`, and acquisition `attempt_id`. Mailing-list detail exposes stored connectivity and
inclusion reasons. Stream membership exposes the saved stream revision, execution run, inclusion
kind/reason, completeness, and upstream/seed lineage.

### Common problems and recovery

Missing content or checksum mismatch is an integrity failure, not a cue to silently reacquire or
rewrite evidence. Follow [repository verification and restore](#repository-protection). A stale
pagination cursor means repository authority changed; refresh the projection. Missing expected
material requires checking the [acquisition](#acquisition) or [stream](#streams) run result and its
exact configured revision.

### CLI equivalent

`rfi verify` checks retained content. `rfi mailing-list discussions`, `search`, and `incomplete`
query retained mailing-list state. `rfi stream memberships STREAM_ID` and
`rfi stream inspect-run RUN_ID` inspect stream results. There is no generic firm-artifact CLI tree.

Related topics: [acquisition](#acquisition), [streams](#streams), [revisions and lineage](#revisions-lineage),
and [repository protection](#repository-protection).

<!-- help-topic: streams -->
## Artifact Streams

### Purpose

Configure, revision, execute, and inspect bounded materialized projections over governed external
evidence or saved upstream streams.

### Prerequisites

For a Governed external source input, first
[save a repository-global External Source](#external-sources). For Upstream streams,
[save compatible upstream definitions](#stream-upstream-definitions). Know the intended artifact
schema, selection criteria, context expansion, and hard bounds.

<!-- help-topic: stream-upstream-definitions -->
### Preparing compatible upstream streams

Create each upstream definition by following the [stream revision procedure](#streams): select its
input and artifact schema, validate, preview, and save it before selecting it as an Upstream streams
input. The upstream and downstream schemas must be compatible, every referenced stream must exist,
and the resulting graph must not contain self-reference or a cycle. Saving a definition does not
execute it. Before executing the downstream stream, use `Run dependency chain` to execute required
saved upstream revisions in topology order, or confirm that their current results are already
usable. Inspect upstream runs, memberships, and lineage under [Artifacts](#artifacts).

### Stream revision and execution procedure

1. Choose `New stream`, or select a saved stream to create a revision.
2. Complete Identity, Input, Selection, Context and limits, and Review and save.
3. Choose `Validate`; inspect Normalized validation. Nothing is saved or run. See
   [Stream validation and preview](#stream-validation-preview) for the review contract.
4. Choose `Preview bounded matches`; inspect direct matches, expansion, bounds, warnings, and
   normalized behavior. Nothing is saved, published, or acquired.
5. Choose `Inspect draft YAML` when a canonical representation is useful.
6. Review meaningful differences and choose `Save new stream` or `Save new revision`.
7. Reload/select the saved revision. Only a saved, current, enabled definition can run.
8. Choose `Run saved stream`, or `Run dependency chain` for required upstream execution.
9. Inspect Execution result, topology, Revision history, runs and memberships under
   [Artifacts](#artifacts).
10. Choose `Export saved YAML` for the current revision or Export beside a historical revision;
    see [Stream YAML import and export](#yaml).

### Controls and state changes

Refresh, select, history inspection, Validate, Preview, Inspect draft YAML, schema/template load,
YAML review, and export do not persist or execute. Save creates a new immutable stream revision;
semantically identical YAML import returns `already_current` without a revision. Run persists a
durable run and atomically publishes bounded membership/lineage from retained evidence. Run
dependency chain executes required saved upstream streams in topology order. Neither validation
nor stream execution performs source acquisition.

The common Selection editor creates registered typed predicates. Advanced policy accepts JSON for
the same bounded data contract, never executable code. Unsupported fields/operators, source or
stream references, schema mismatches, self-reference, cycles, and invalid bounds fail validation.

### Expected results and inspection

The stream list shows current revision, membership count, and latest run status. The inspection
area shows normalized validation, bounded preview, semantic differences, topology/history, or
execution output. Artifacts has the durable Artifact streams projection and exact content for each
membership.

### Common problems and recovery

If Run is disabled, select a saved enabled current revision and ensure the draft is clean. Saving
or discarding the unsaved draft is required before execution. An upstream-not-current failure
requires [running the dependency chain](#stream-upstream-definitions) or explicitly bringing
upstream results current. Resolve cycles or incompatible schemas in the draft rather than editing
stored history. Use Rebuild only through the [supported CLI](#cli-reference) when derived
memberships must be reconstructed from retained state.

### CLI equivalent

Use `rfi stream schema`, `validate`, `import`, `export`, `preview`, `save`, `run`, `run-chain`,
`memberships`, `inspect-run`, and `rebuild`. The legacy CLI preview/save inputs are JSON drafts;
canonical interchange uses YAML.

Related topics: [validation and preview](#stream-validation-preview), [YAML](#yaml),
[revisions and lineage](#revisions-lineage), [External Sources](#external-sources), and
[Artifacts](#artifacts).

<!-- help-topic: stream-validation-preview -->
## Stream validation and preview

### Purpose

Review a proposed stream safely before publication and distinguish schema validity from actual
bounded membership evaluation.

`Validate` normalizes and checks the draft contract, registered schema fields/operators,
references, topology, expansion, and bounds. It reads current repository capabilities and saved
definitions but creates no stream revision, run, membership, acquisition, or source change.

`Preview bounded matches` first validates, then reads retained evidence or current upstream
memberships and calculates a bounded proposed result. It creates no stream revision, run,
membership, artifact, or acquisition. Preview output is not a durable execution record and may
change if repository evidence changes.

`Review imported YAML` parses versioned canonical YAML, displays normalized YAML, determines
whether intent is new, revision, or already current, and displays semantic differences. It does
not save or execute. Only the later explicit Import action persists.

Normal sequence: validate, correct every path-specific error, preview, inspect meaningful
differences and bounds, then save. A valid draft can still preview no matches. That is an operating
result to inspect, not proof of persistence failure.

CLI equivalents:

```sh
rfi stream --state STATE validate --file stream.yaml
rfi stream --state STATE preview --file stream-draft.json --limit 25
```

Related topics: [streams](#streams), [YAML](#yaml), and [revisions and lineage](#revisions-lineage).

<!-- help-topic: revisions-lineage -->
## Revisions, immutability, and lineage

### Purpose

Understand why editing creates history and how later results remain attributable to exact saved
configuration.

Concepts, firms, firm source profiles, and streams publish immutable numbered revisions. A stable
identity points to a current revision; old revisions remain inspectable. Optimistic expected
revision IDs reject stale writes rather than silently overwriting newer work. Retirement is a new
revision, not deletion.

External Source identity and transport policy are immutable as a complete source profile. To
change one, clone to a new stable source ID and revise consumers explicitly.

Pull runs snapshot the firm source-profile revision used for planning. Successful acquisition
retains attempt, observation, logical document, exact artifact bytes, and provenance identities.
Repeated equal bytes can reuse a byte artifact while retaining distinct observation history.

Stream runs identify the exact stream revision executed. Membership records state inclusion kind,
reason, expansion, completeness, source document/artifact, and lineage to direct seeds or upstream
memberships. A later definition revision or upstream run never rewrites prior run history.

Historical inspection and export read old revisions. Validation and preview do not create lineage
because they do not publish or execute. Restore preserves identities from the verified archive;
copying selected database or content files is unsupported.

Related topics: [repository model](#repository), [acquisition](#acquisition), [streams](#streams),
and [Artifacts](#artifacts).

<!-- help-topic: yaml -->
## Stream YAML import and export

### Purpose

Review, exchange, and intentionally publish complete versioned stream definitions using the
canonical deterministic YAML contract.

### Browser validation, preview, and import procedure

1. Open [Streams](#streams) and expand `Import YAML`.
2. Choose a `.yaml`/`.yml` file or paste YAML. File selection only reads into browser draft state.
3. Choose `Review imported YAML`.
4. Inspect errors, Normalized YAML preview, semantic fingerprint, import mode, and semantic
   differences. No repository state has changed.
5. If useful, copy the normalized YAML and separately run Preview bounded matches.
6. When the intent is correct, choose `Import as new stream` or `Import as new revision`.
7. Confirm the saved stream/revision in the list and history. Import never executes it.

`Load schema/template` loads the canonical commented version 1 template without persistence.
`Inspect draft YAML` renders the current browser draft without persistence. `Export saved YAML`
downloads deterministic canonical YAML for a saved revision. Formatting-only changes normalize to
the same semantic definition. Import of an identical current normalized definition returns
`already_current` and creates no revision.

An existing identity requires revision intent and optimistic current-revision context. YAML cannot
define source transport policy, credentials, endpoints, pacing, retry, or cursors; it references
the governed source ID only. Import does not acquire evidence, run a stream, alter a source
profile, or write artifact bytes.

### CLI equivalent

```sh
rfi stream schema > stream-template.yaml
rfi stream --state STATE validate --file stream.yaml
rfi stream --state STATE import --file stream.yaml --new
rfi stream --state STATE import --file revised.yaml --revision \
  --expected-revision REVISION_ID
rfi stream --state STATE export --stream STREAM_ID --output stream.yaml
rfi stream --state STATE export --stream STREAM_ID --revision-id REVISION_ID
```

Validation failures return exit status 2 with diagnostics on stderr. Export to stdout contains only
YAML, so shell redirection is safe.

Related topics: [streams](#streams), [validation and preview](#stream-validation-preview), and
[revisions and lineage](#revisions-lineage).

<!-- help-topic: repository-protection -->
## Verify, backup, and restore

### Purpose

Verify both repository authorities, create a complete portable backup, and restore it without
overwriting an existing destination. These supported operations are CLI-only.

### Repository protection procedure

1. Identify the active state path from `rfi admin` startup output. Stop guessing before any backup
   or restore command.
2. Verify health:

```sh
rfi verify --state STATE
```

3. Create a backup at a new output path:

```sh
rfi backup --state STATE --output repository-backup.zip
```

4. Restore to a fresh destination, never over existing state:

```sh
rfi restore --input repository-backup.zip --state FRESH_STATE
```

5. Verify the restored repository and start a separate admin process against it:

```sh
rfi verify --state FRESH_STATE
rfi admin --state FRESH_STATE --port 8766
```

6. Inspect expected [firms](#firms), [source profiles](#source-profiles),
   [external sources](#external-sources), [artifacts](#artifacts), and [streams](#streams) before
   choosing which repository will be used for later operations.

`verify` reads state and checks SQLite integrity, foreign keys, structured relationships, content
references, sizes, checksums, and orphan inventory. It does not repair or discard evidence.
`backup` first verifies both authorities, uses SQLite's online backup API, packages every immutable
content object, and writes a checksummed member manifest. `restore` verifies the complete archive,
accepts only a fresh destination, validates restored state, and removes a failed partial restore.

Do not back up by copying a live SQLite database without its protocol, do not merge archive members
into another repository, and do not delete an orphan merely because verification reported it.
Restore from a verified backup or seek an explicitly authorized repair procedure.

Related topics: [repository model](#repository), [troubleshooting](#troubleshooting), and
[CLI equivalents](#cli-reference).

<!-- help-topic: troubleshooting -->
## Troubleshooting and recovery

### Help and browser behavior

- Help link opens in the current tab: browser policy may choose how named targets appear. Open the
  link in a new window manually if desired. RFI-1 cannot force placement.
- Repeated Help invocation: the application requests the same `rfi-operator-help` target, so a
  conforming browser reuses it and navigates to the new page topic. Browser isolation or user
  settings may instead create another tab.
- Unknown Help topic: the local server returns a safe Help page with an Unknown Help topic notice
  and HTTP 404. It neither redirects to external content nor changes application state.
- Unsaved state: Help does not navigate or submit the administration page. Keep that original tab
  open. Ordinary reload, close, or same-tab navigation remains governed by the page's own dirty
  state protection.

### Configuration and revision failures

- Validation error: follow the displayed field/path, correct the browser draft, validate again.
- Revision conflict: preserve needed draft values, reload the current revision, compare, and
  intentionally reapply. Never bypass optimistic checking.
- No runnable firm artifacts: inspect [Firm Profiles](#source-profiles) and supported retrieval
  candidates.
- No governed stream source: create it under [External Sources](#external-sources), then return to
  [Streams](#streams).
- Stream cycle/schema/reference error: correct topology or schema in a new draft; saved history is
  immutable.
- Run disabled: select a saved enabled current stream and ensure no unsaved/imported draft remains.

### Acquisition and evidence failures

- Configuration problem: use the result link to the exact firm/artifact, save a corrected
  [profile revision](#source-profiles), and create a new [pull run](#acquisition).
- Retrieval failure: inspect adapter attempt diagnostic and runtime network/request identity; retry
  only after the condition is understood.
- Missing artifact: inspect the exact [pull](#acquisition) or [stream](#streams) result and revision.
  Empty repository branches do not imply acquisition succeeded.
- Missing/checksum-invalid content or orphan: run `rfi verify`; do not silently modify evidence.
- Missing mailing-list projection with retained run items: run `rfi mailing-list rebuild`; it uses
  retained bytes without network access.
- Stale artifact cursor: refresh because the authority revision changed.

### Repository failures

Missing, legacy, mixed, incompatible, corrupt, or non-fresh restore destinations fail closed. Use
the exact state path, preserve original files, and restore a verified archive to a new directory.
There is no automatic legacy migration or evidence-rewriting repair command.

Related topics: [getting started](#getting-started), [source readiness](#source-readiness),
[repository protection](#repository-protection), and [Artifacts](#artifacts).

<!-- help-topic: cli-reference -->
## CLI equivalents

Use `rfi --help` and `rfi COMMAND --help` for the exact installed option surface. The installed
`rfi` command and `python -m rfi` call the same implementation.

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
rfi mailing-list --state PATH configure-lore-source [source and policy options]
rfi mailing-list --state PATH preview|acquire --live [selection and limits]
rfi mailing-list --state PATH sources|discussions|search|incomplete|rebuild
rfi stream schema
rfi stream --state PATH validate --file STREAM.yaml
rfi stream --state PATH import --file STREAM.yaml (--new | --revision)
rfi stream --state PATH export --stream STREAM_ID [--revision-id REVISION_ID]
rfi stream --state PATH preview|save --file STREAM.json
rfi stream --state PATH run|run-chain|memberships STREAM_ID
rfi stream --state PATH inspect-run RUN_ID
rfi stream --state PATH rebuild
```

Mailing-list `preview` performs bounded live remote planning/parsing but writes nothing;
`acquire` is the separate explicit persistent action. Both live paths require `--live` and bounded
selection/limits. Offline sources, discussions, search, incomplete, and rebuild operations use
retained repository state.

The browser is the normal editor for concepts, firm revisions, and firm source-profile revisions.
The CLI is the supported surface for lifecycle, firm catalog batch import, pulls, repository
protection, live mailing-list acquisition, and complete stream operations.

Related topics: [getting started](#getting-started), [acquisition](#acquisition), [YAML](#yaml),
and [repository protection](#repository-protection).

<!-- help-topic: glossary -->
## Glossary

- Acquisition attempt: one materially distinct retrieval activity and its outcome.
- Artifact: immutable exact bytes identified by SHA-256.
- Canonical YAML: deterministic versioned representation of a complete stream definition.
- Current revision: immutable revision selected as the present view of a stable identity.
- Document: stable logical source document that may have multiple observations/artifact versions.
- External Source: immutable repository-global Lore/public-inbox identity and transport policy.
- Firm Source Profile: immutable revision of one firm's enabled artifact intent and candidates.
- Help topic ID: explicit stable identifier used by application deep links, independent of heading.
- Import: explicit persistence of reviewed canonical YAML as new identity/revision; never execution.
- Lineage: durable relationship from a stream membership to seeds or upstream memberships.
- Observation: one successful immutable acquisition observation, even when bytes are duplicates.
- Preview: bounded evaluation of proposed behavior without persistence or execution.
- Pull Workflow: shared firm acquisition planner, executor, ingress, and durable result workflow.
- Repository: one SQLite structured-state authority plus immutable content-addressed bytes.
- Revision: immutable numbered state for a stable concept, firm, profile, or stream identity.
- Run: durable record of explicit pull or stream execution.
- Stream: revisioned bounded materialized projection over external evidence or upstream streams.
- Validation: checking and normalization of proposed state without persistence.

Return to [Getting started](#getting-started) or use browser Find to locate a control, error, route,
or command.
