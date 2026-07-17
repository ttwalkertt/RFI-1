# Target firm catalog, browser, and admin editor

TASK-011 adds a durable authority for **who the research target is and how operators recognize
it**. The target-firm catalog is separate from evidence, source objects, concepts, observations,
workspaces, and intelligence. Seeded Seagate, Western Digital, and Toshiba records are practical
HDD consulting proofs, not a complete security master or corporate hierarchy.

## Authority and dependency boundaries

```text
Programmatic caller / Target Firms browser
                    |
                    v
              FirmService
                    |
                    v
             FirmRepository
        immutable identity revisions
        recognition-conflict checks
                    |
                    v
       FirmReference(firm_id, optional revision_id)
                    |
                    +---- future acquisition policy
                    +---- future source/document association
                    +---- future knowledge and observations
                    +---- future workspaces and questions
```

`rfi.firms` imports none of those future repositories. Downstream systems can persist a
`FirmReference` or simply the stable `firm_id` without reading firm persistence. An optional exact
revision pin is available when a result must retain the recognition semantics used at that time.
The catalog does not store filings, extracted products, competitive claims, observations, analyst
notes, or question-answering results.

## Contract and persistence

`FirmDraft` provides canonical and legal names, aliases, typed identifiers, normalized domains,
headquarters and jurisdiction hints, sector and industry classifications, technology focus,
lightweight relationships, source-discovery hints, operator notes, lifecycle status, and business
validity. `FirmIdentifier` represents kind, value, and optional market/registry. `FirmRelationship`
points to another stable firm ID using `parent`, `subsidiary`, `brand`, `related`, or `competitor`.
`SourceDiscoveryHint` is typed operator guidance and never acquired evidence.

Creation or editing publishes a complete immutable `FirmRevision` with a content-derived identity,
monotonic revision number, exact predecessor, creation/update times, and stable `firm_id`. The
repository stores an atomically replaced current/history pointer plus immutable revision files:

```text
<admin-concept-state>/firm-catalog/
  catalog.json
  revisions/firm-revision-<sha256>.json
```

Writes publish a revision file before replacing the pointer. Restart verification checks schema,
file inventory, revision sequence, predecessor chain, current selection, and content digest.
Optimistic `expected_revision_id` checks prevent stale editors from overwriting a newer revision.
Retirement appends history; it never deletes identity.

Current records cannot share the same normalized `(identifier kind, market, value)` or domain.
Identifiers remain strings so leading zeroes and nonnumeric market codes are preserved. Aliases,
technology labels, and repeated structures reject duplicates within a firm. Relationship targets
are stable-ID references and may intentionally point forward to a firm not yet cataloged; this
supports incremental consulting setup without claiming referentially complete corporate data.

## Browser and editor workflow

Start the existing local console and open `/firms`. The top navigation moves between Concept
Catalog and Target Firms while retaining TASK-010's visual language and operator workflow:

```text
List/Search → Detail/Browser → Edit/Create Revision → Validate → Preview → Save Revision
```

The list searches names, aliases, identifiers, domains, technologies, notes, and source hints and
filters by status, sector, and industry. Detail shows canonical/legal identity, recognition
metadata, classifications, relationships, hints, notes, and immutable history. Loading, empty,
failure, saved, and retired states remain explicit.

The editor uses native typed controls and repeated rows for aliases, domains, technologies,
identifiers, relationships, and source hints. It does not expose JSON. Significant labels use the
central `rfi.admin.field_definitions` registry. Help works on hover and keyboard focus and can be
pinned with click or touch. Client validation provides an immediate page summary; `FirmService`
and `FirmRepository` remain authoritative for publication and cross-record conflicts.

A failed validation or save does not reconstruct or close the form, so entered values remain.
Dirty state is visible; Cancel, Escape, reload, close, and browser navigation protect unsaved work.
Preview describes the current/proposed revision and changed identity groups before Save appends an
immutable revision.

## Seeded consulting examples

- **Seagate** includes STX/NASDAQ and SEC CIK recognition, `seagate.com`, source hints, operator
  notes, and a competitor reference to Western Digital.
- **Western Digital** includes WDC/NASDAQ and SEC CIK recognition, `westerndigital.com`, source
  hints, notes, and a competitor reference to Seagate.
- **Toshiba** includes TSE 6502, `global.toshiba`, corporate/product discovery hints, and a
  deliberately lightweight relationship to its storage operating organization.

These values demonstrate data shape and workflow. They must be revised from governed operator
research when legal, market, or organizational details change.

## Public API and validation

The local HTTP adapter exposes the same service used by Python callers:

- `GET|POST /api/firms`
- `POST /api/firms/validate`
- `GET|PUT /api/firms/{firm_id}`
- `GET /api/firms/{firm_id}/history`
- `POST /api/firms/{firm_id}/retire`

Run the focused proof and tests with:

```sh
make task011-proof
PYTHONPATH=src .venv/bin/python -m unittest tests.test_task011 -v
```

Run complete validation and regenerate the auditable package with `make validate` and
`make review-package`.

## Known limitations and likely realignment

- The relationship vocabulary is intentionally small and has no inverse-edge maintenance,
  effective dates, ownership percentages, or universal hierarchy semantics.
- Identifier normalization is exact case-insensitive text plus market. It is not a security master
  and has no merger, reuse, or exchange-history policy.
- Domains are unique recognition hints; shared corporate infrastructure may require a future
  scoped-domain model.
- Seed data is repository-owned proof data, not automatically refreshed market or legal data.
- No automatic subsidiary, brand, product, or source discovery is performed.
- The console remains unauthenticated, local-only, and single-user.
- Firm-to-source and firm-to-knowledge associations are stable-reference extension points, not yet
  persisted integrations.

## Architectural Status Summary

- **Target-firm authority — Complete for local consulting use.** Public contracts, immutable
  revision persistence, lifecycle, integrity, lookup, and conflict checks are durable.
- **Recognition model — Usable with limitations.** Names, aliases, identifiers, domains,
  classifications, relationships, and hints support immediate HDD research; security-master and
  corporate-hierarchy semantics remain intentionally provisional.
- **Firm browser/editor — Complete for TASK-011.** Search, filters, detail, typed repeated editing,
  centralized help, validation, preview, dirty protection, revision history, and failure recovery
  reuse TASK-010 conventions.
- **Seeded consulting catalog — Complete as proof.** Seagate, Western Digital, and Toshiba persist
  and are retrievable through public contracts and the GUI.
- **Integration readiness — Complete at the identity boundary.** `FirmReference` permits future
  layers to attach by stable identity without persistence coupling; actual corpus/knowledge joins
  are not started.
- **Next architectural milestone — firm-scoped acquisition and source coverage.** Use stable firm
  references to attach governed source policies and inspectable document coverage while retaining
  evidence authority outside the catalog.
