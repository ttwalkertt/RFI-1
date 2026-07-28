# TASK-045 Verification Package

## Review Scope

TASK-045 corrects Linux Block/Linux NVMe cross-post admission, adds durable observation-backed
canonical lineage, enforces source-scoped continuation integrity, and supplies a bounded copied-state
repair. No live operator state was modified during implementation or validation.

Authoritative inputs:

- `tasks/TASK-045-source-scoped-mailing-list-observations-and-canonical-cross-list-lineage.md`
- `docs/decisions/0026-source-observations-and-canonical-mailing-list-lineage.md`

## Architecture and Transaction Boundaries

### Canonical and source authority

- Canonical node: globally unique normalized `Message-ID` in
  `canonical_mailing_list_messages`.
- Source acquisition identity: `(source_id, normalized Message-ID)`.
- Successful source observation: immutable artifact plus source document, run item, source message,
  and canonical link.
- Same-source bytes are checked before admission. The global representative artifact is never used
  for that decision.

Normal publication registers or reuses the canonical node, inserts the run observation, inserts its
bounded relationship claims, and refreshes source projections in one SQLite transaction after exact
bytes have been durably recorded by the acquisition substrate.

### Claims and deterministic lineage

Claims retain exact asserted values and source/run/artifact provenance. Current emitted types are
`header_in_reply_to/immediate_parent` and `header_references/ancestor_reference`. Resolution is a
query-time join to the canonical registry. Corpus traversal deduplicates canonical nodes, aggregates
agreeing edge claims, exposes differing parent sets as ambiguous, and returns unresolved boundaries.
The optional source filter selects claims and source observations without changing corpus identity.

### Acquisition and delivery provenance

Existing candidate locations and `fallback_archive_url` identify configured versus fallback
acquisition. `source_id` identifies the configured acquisition policy. No delivery source is asserted
without existing explicit evidence. A required fallback ancestor may join the source discussion to
close the acquisition-policy graph; membership does not prove list delivery.

### Continuation invariant

Before reuse, every acquired/completed/active-frame ID in a frontier must resolve to
`mailing_list_messages` under that source. Pending child IDs remain provider work and are not treated
as acquired. Conflict or quarantine forces failed relationship status, non-retryable conflict where
applicable, no continuation, and withheld coverage.

## Schema and Migration

Schema version 12:

- adds nullable-during-migration `mailing_list_messages.canonical_message_id`;
- adds `mailing_list_relationship_claims` and child/reference indexes;
- backfills canonical nodes and run/source links from every successful historical RFC822 observation,
  allowing byte variants across sources;
- deterministically backfills immediate-parent and ordered ancestry-reference claims from retained
  projections and run provenance; and
- extends repository validation to require correct canonical links and valid bounded claims.

Migration is additive. Artifacts, documents, runs, conflict evidence, and source projections are not
deleted or rewritten. Backup/restore validation covers schema 12.

## Copied-State Repair Evidence

Source state was copied from `/Users/tim-macbook/Documents/rfi/1` to a disposable `/private/tmp`
directory before migration or repair. The live source was never opened for write by TASK-045 tools.

Repair command:

```text
PYTHONPATH=src .venv/bin/python scripts/task045_repair.py \
  --state-copy <copy> \
  --source-id linux-nvme-lore \
  --historical-run-id mailrun-107f408d21eb4646b4f11ef1d6696268
```

Observed result:

- eligible/repaired: 18;
- skipped: 0;
- schema version: 12;
- SQLite integrity: ok;
- foreign keys: ok;
- repeated repair: 0 repaired (idempotent);
- 21 unrelated unresolved conflicts remained outside the authorized historical run.

The repair retained the historical conflict observations and failed manifests, created deterministic
`mailrepair-*` provenance, reused preserved candidate artifacts, and did not rewrite immutable bytes.

Copied-state retry command:

```text
PYTHONPATH=src .venv/bin/python scripts/task045_copied_state_retry.py \
  --state-copy <repaired-copy> \
  --stream-id linux-block-mailing-list-0872ffc6
```

The retry rejected the legacy invalid frontier and restarted discovery offset 105. It completed 47
successful NVMe acquisition runs without an error code, exhausted discovery at offset 325, recorded
`discovery_has_more=0` and `coverage_complete=1`, and published downstream stream run
`streamrun-1f2a59277184400b94a159dc15ef0bb2` successfully with 5 direct and 39 context memberships.
The original failed fetch-history record remains unchanged.

The repaired copy then produced verified backup
`sha256:6d953194edb5a2fb0b81ca4dc3b3c901dc359294fa814ed06cf19eb4eddcbe5b`
with 1,619 members. Restore reported schema 12/PASS, and repository validation on the restored state
reported SQLite integrity `ok`, foreign keys `ok`, 46 tables, and PASS. A pre-existing Finder
`.DS_Store` in the copied content directory was preserved outside the disposable copy before backup
because the inventory verifier correctly classified it as a non-artifact orphan.

## Automated Verification

Focused TASK-045 tests cover:

- byte-different cross-source observations on one canonical node;
- source-specific artifacts/documents and multiple discussion memberships;
- cross-list descendant branches and source-filtered lineage;
- ambiguous immediate parentage;
- ordered `References` ancestry without direct edges;
- multi-ID `In-Reply-To` parser evidence without claims;
- unresolved boundaries without placeholder canonical nodes;
- terminal same-source conflicts without frontiers;
- invalid legacy frontier rejection; and
- deterministic, idempotent repair plus backup/restore validation.
- migration from schema 11 with evidence-count preservation and canonical-link backfill;
- late parent resolution without durable-claim mutation;
- agreeing cross-source parent assertions producing one edge with two claims; and
- independent fail-closed evaluation of all six repair predicates.

Focused TASK-045 execution passed 12 tests. The required regression command passed 130 tests:

```text
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_task045 tests.test_task023 tests.test_task030 tests.test_task031 \
  tests.test_task035 tests.test_task028 tests.test_task028_message_viewer \
  tests.test_task029 tests.test_task029_ui_polish tests.test_task032 \
  tests.test_task038 tests.test_task039
```

TASK-037 conflict-quarantine coverage is contained in `tests.test_task023`; there is no standalone
`tests.test_task037` module.

Final `make validate` passed. Its repository-wide unittest discovery ran 424 tests, and its
supplemental focused unittest target ran 7 tests; both reported OK. All fixture-proof targets,
lint, formatting, type checking, import checking, documentation, baseline, and build gates passed.
The final source archive contained 430 members, 2,619,052 bytes, and verified SHA-256
`a1bbb4aaa697626b979fc2119c6bb431dca05aa53bea70381fb6d079edb107ce`.

Static validation already passes lint, formatting, type checking, import checking, documentation,
design baseline, and source archive build/integrity. TASK-044 removed the former source-profile page
but left its TASK-014 fixture proof, baseline file inventory, and TASK-017 browser harness referring
to that deleted path. TASK-045 removes those stale references and exercises the same preference
contract through the surviving Pull Sources page; it makes no UI change.

## Limitations

- Canonical lineage is a bounded repository query, not a graph-analysis engine.
- Only retained RFC822 observations create canonical nodes.
- Provider-parent and heuristic-parent claim types remain unused because no qualifying current
  evidence contract exists.
- Delivery source remains unknown unless existing retained evidence explicitly establishes it.
- Repair is intentionally limited to one explicitly named historical run and copied state.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Immutable acquisition | Exact source RFC822 bytes and retrieval observations | Complete |
| Canonical message registry | Corpus logical identity by normalized Message-ID | Complete |
| Source message observations | Source-scoped documents, message records, and same-source conflicts | Complete |
| Relationship claims | Durable bounded header assertions with observation provenance | Complete |
| Canonical lineage | Derived cross-list branches, ambiguity, and unresolved boundaries | Complete |
| Source discussions | Acquisition-policy-specific thread projections | Complete |
| Continuation and coverage | Retained-source frontier integrity and truthful terminal outcomes | Complete |
| Historical NVMe repair | Deterministic copied-state repair for the affected 18 observations | Complete |

Architectural changes: schema 12 adds source-to-canonical linkage and a durable claim authority;
lineage is derived rather than independently stored. TASK-035's global byte-conflict admission rule is
narrowed to same-source observations.

Important limitations and debt: lineage exposes evidence-backed topology only; it does not rank or
resolve ambiguous parents. Existing source relationship `authority/certainty` columns remain a legacy
source projection contract and are not reused as canonical confidence.

Next architectural milestone: resume the roadmap-selected work after TASK-045; no broader graph or UI
work is authorized by this correction.
