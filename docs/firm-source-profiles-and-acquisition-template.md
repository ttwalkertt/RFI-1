# Firm source profiles and canonical acquisition template

TASK-014 adds acquisition *configuration* without adding acquisition execution. It consists of a
repository-owned canonical template, an independently revisioned firm source-profile aggregate,
and a template-driven local administration interface.

## Canonical template

The single acquisition catalog is shipped as application data at
`src/rfi/resources/source-profile-template.yaml`. It is packaged with `rfi`, loaded at runtime, and
validated before the source-profile repository or admin console can open. Python contains schema
and semantic validation but no parallel category or artifact list.

The YAML template owns:

- ordered source categories and artifact items;
- stable canonical identifiers and globally unique concise `short_name` values;
- display labels and descriptions;
- default enabled state and addressability class;
- retrieval-field definitions;
- retrieval-mode candidate shapes and requirements; and
- the retrieval modes supported by each artifact.

Category and item `order` values must be positive, unique within their scope, and ascending in the
file. Identifiers and short names must be unique. Unsupported addressability classes, retrieval
modes, fields, field types, malformed arrays, and nonconcise short names fail closed. Maintainers
should edit this one resource when changing the acquisition catalog and add or update template
validation evidence; they should not add a Python or browser list.

### Conservative universal default policy

The canonical defaults are deliberately conservative because the same general-purpose template is
shown for US public companies, foreign issuers, private companies, subsidiaries, hyperscalers,
component suppliers, and enterprise storage vendors. A default means only “broadly useful enough
to present as initially selected”; it does not assert that the artifact exists for every firm.

The exact default-enabled set is:

- `annual_report`;
- `earnings_release`;
- `press_release`;
- `corporate_news`; and
- `product_page`.

All other canonical items default off. In particular, jurisdiction- or issuer-type-specific
filings (10-K, 10-Q, 8-K, 20-F, 6-K, proxy, ownership and insider filings), reporting-practice
specific materials (call transcripts, prepared remarks, earnings presentations, supplemental
tables), specialized technical publications, social channels, conference material, patents, and
market signals require explicit operator enablement. Explicit saved profile configuration always
overrides these display defaults, so a US issuer can enable 10-K retrieval without changing the
single global template or adding firm-type inference.

This policy intentionally does not introduce jurisdiction rules, company-type inference, dynamic
defaults, or multiple templates.

## Addressability and retrieval candidates

Addressability describes future retrieval planning, not artifact classification:

- `deterministic`: a stable identifier, feed, API, endpoint, or direct URL can locate artifacts;
- `semi-deterministic`: a stable archive, listing page, or portal exists but its children require
  discovery; and
- `discovery-based`: bounded search hints or domains are necessary because no complete stable
  endpoint exists.

A profile item can contain zero or more candidates. Candidates have unique positive priorities
within the item and are persisted in priority order. Depending on the canonical retrieval-mode
shape, they can contain a URL, stable locator, preferred domains, discovery hints, expected media
type, parser or adapter hint, and operator notes. URLs accept only credential-free HTTP(S)
locations. Mode-specific required fields and supported fields are defined in the YAML template.

Configured URLs, locators, and hints are acquisition intent. They are not retrieved URLs,
provenance, immutable artifacts, or source objects. A future acquisition subsystem may interpret
this configuration but must create its own retrieval and provenance records.

## Independent immutable aggregate

Firm source profiles are stored under the application state's `source-profiles/` directory. The
aggregate is keyed by the stable `firm_id`, but it has its own catalog pointer, revision files,
content-derived revision identifiers, revision numbers, timestamps, supersession chain, atomic
publication, optimistic concurrency check, and integrity verification.

The profile repository never writes the target-firm repository. The profile service reads the firm
catalog only to reject unknown firms. Conversely, target-firm create, revise, import, and retire
operations do not open or publish source-profile revisions. This keeps identity and recognition
metadata separate from future acquisition configuration.

Before the first profile is saved, the service returns a view with `revision_number: 0`, no
revision identifier or timestamps, `is_default: true`, and each canonical item's template default.
This view is not stored and does not appear in history. The first save creates revision 1. Later
saves append revisions; previous revisions remain readable. Validation and interrupted publication
leave the prior pointer and revision set unchanged.

Profile entries are normalized to canonical template order, missing entries receive canonical
defaults, and candidates are sorted by priority. Each firm's history and future acquisition
pipeline remain independent. Cross-firm deduplication is intentionally absent.

## Administration interface

The firm-level interface is available at `/source-profiles`. It loads firms, the canonical
template, profile state, and history through public JSON APIs. Categories and artifact rows are
rendered by iterating the runtime template. Each compact artifact row shows the enable control,
short name, display label, addressability, and configuration summary. Expanding the row reveals
item notes and zero or more prioritized retrieval-candidate editors. Candidate controls are
generated from the selected mode's canonical `supported_fields` definitions.

Saving appends only a source-profile revision. Historical profile revisions are inspect-only.
Canonical defaults remain visible and editable before revision 1 without being represented as
stored state.

## Explicit non-goals

TASK-014 does not retrieve networks or files; schedule, poll, or discover sources; parse artifacts;
create source objects; deduplicate across firms; rank source quality; or migrate among template
versions. The repository ships one template version. Future acquisition execution is a separate
architectural milestone and must preserve the distinction between configuration and retrieved
provenance.

## Verification

Run focused tests and the deterministic proof:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_task014 -v
make task014-proof
```

Run all regressions and quality gates with `make validate`. Both `.venv/bin/rfi` and
`.venv/bin/python -m rfi` use the same lifecycle implementation and initialize the independent
source-profile catalog alongside existing application state.

## Architectural Status Summary

- Canonical acquisition configuration: **Complete** as one shipped, validated application-data
  template.
- Firm source-profile aggregate: **Complete** for immutable local revision history, atomic
  publication, history inspection, and cross-firm isolation.
- Administrative configuration: **Complete** for template-driven category, item, and candidate
  editing in the local console.
- Acquisition execution and retrieved source objects: **Not started** by design.
- Important limitation: the console is a local single-operator interface and no template migration
  mechanism exists because the repository currently owns one template version.
- Next architectural milestone: define acquisition execution as a separate consumer of published
  profile configuration while preserving retrieved provenance and source-object boundaries.
