# TASK-066 --- Western Digital Business Wire Press Release Acquisition Adapter

## Objective

Implement a complete Western Digital press-release acquisition adapter
using the Business Wire newsroom as the initial provider surface.

Initial discovery seed:

https://www.businesswire.com/newsroom?keywords=ENTIRE_RELEASE%3Atrue%3Awdc

Adapter name: `wdc_press_release`

The objective is to discover Western Digital press releases, retrieve
the complete release content and pertinent source metadata, and persist
immutable source artifacts plus normalized metadata through the existing
RFI acquisition pipeline and SQLite repository.

## Scope

### Required acquisition modes

1.  **Latest release**
    -   Return the newest qualifying Western Digital press release.
2.  **Date-range release**
    -   Accept an inclusive start and end date.
    -   Return the earliest qualifying Western Digital press release
        within the range.
    -   If none exist, return an explicit successful no-result outcome.

Publication timestamps determine ordering. Define deterministic
tie-breaking.

### Configuration

-   Register the adapter through the existing provider infrastructure.
-   Wire it to the existing Western Digital `firms.config.json` entry.
-   Do not introduce parallel configuration mechanisms.

### Discovery

Starting from the configured Business Wire search page:

-   Determine the site's actual deterministic discovery mechanism.
-   Preserve the configured search while paginating.
-   Traverse only as far as necessary.
-   Detect pagination loops.
-   Deduplicate discovered releases.
-   Fail observably if discovery becomes unsupported.

Avoid browser automation unless no deterministic HTTP mechanism exists.

### Qualification

Search membership alone is insufficient.

Accept only releases attributable to Western Digital Corporation using
deterministic publisher metadata.

Reject unrelated releases that merely mention "WDC".

No LLM-based qualification.

### Extraction

Extract where available:

-   title
-   publication timestamp
-   issuer
-   ticker metadata
-   canonical Business Wire URL
-   Business Wire release identifier
-   dateline
-   summary/highlights
-   complete release body
-   contacts
-   attachments
-   source attribution
-   discovery URL
-   retrieval timestamp

Persist the original fetched artifact according to existing repository
conventions.

### Repository integration

Reuse existing acquisition engine, repository contracts, immutable
artifact storage, source profiles, indexing, and provenance.

Do not bypass repository abstractions.

Preserve:

-   immutable source artifacts
-   append-only retrieval history
-   complete provenance
-   idempotent reacquisition
-   durable progress semantics

### Taxonomy

Store using the existing firm and artifact taxonomy.

Extend taxonomy only if press releases are not yet represented.

### Non-goals

-   No generic Business Wire provider.
-   No additional firms.
-   No investment analysis.
-   No semantic classification.
-   No browser automation unless justified.

## Testing

Add deterministic tests covering:

-   registration
-   latest acquisition
-   date-range acquisition
-   pagination
-   duplicate suppression
-   issuer qualification
-   false-positive rejection
-   metadata extraction
-   complete body extraction
-   immutable persistence
-   idempotency
-   malformed discovery pages
-   malformed detail pages
-   repository failures

Use checked-in fixtures.

Perform a bounded live validation demonstrating successful discovery,
retrieval, extraction, and persistence.

## Documentation

Update operator and acquisition documentation.

Generate the normal review package including:

-   implementation summary
-   architectural decisions
-   files changed
-   test results
-   live validation
-   representative persisted artifact
-   known limitations

## Architectural expectation

Although this task is intentionally WDC-specific, structure the
implementation so discovery and parsing components can reasonably evolve
into a future generic Business Wire provider without changing repository
contracts.

Commit the completed implementation and review package to the task
branch and push the branch. Do not merge.
