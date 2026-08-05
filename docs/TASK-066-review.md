# TASK-066 Architectural Review — WDC Business Wire Press Releases

## Result

TASK-066 is **not operationally complete**. The WDC-only adapter, parser, qualification,
selection, immutable persistence, and fixture evidence remain implemented, but no lawful public
Business Wire surface tested from the actual RFI execution environment can provide deterministic
WDC discovery plus complete release bytes. Production transport viability is a blocking acceptance
gap, not a limitation that operators may waive.

The production `UrllibPressReleaseTransport` timed out for both the configured newsroom and a known
release detail. A conventional bounded curl request received raw Akamai HTTP 403 denial responses
for the newsroom, detail, robots, sitemap, and feed-help URLs. No CAPTCHA circumvention, stealth
automation, anti-bot evasion, browser automation, or browser-header impersonation was used.

## Direct-Surface Investigation

The investigated official surfaces were:

- Configured server-rendered newsroom search and a known canonical detail page.
- `robots.txt` and `sitemap.xml`, neither accessible from this execution edge.
- Business Wire's official feed documentation and a reachable preconfigured public RSS feed.
- WDC's issuer-controlled investor-relations listing and detail pages as a possible replacement.

Business Wire's public RSS host returned HTTP 200 and parseable RSS, but the observed feed was a
preconfigured Public Policy/Government category feed, contained no WDC items, exposed truncated
descriptions, and linked every item back to the inaccessible Business Wire detail surface. It
cannot supply complete release text or deterministic WDC discovery. Business Wire's official feed
page describes RSS as headline links and presents full-text Atom, NX, and FTP/SFTP as media-partner
newsfeed offerings. No unauthenticated WDC full-text API or feed contract was established.

The WDC investor-relations archive is publicly indexed with complete releases and Business Wire
source URLs, so it remains the best source-design candidate. However, conventional curl also
received HTTP 403 for its listing and detail pages from this execution edge. It is therefore a
recommendation subject to a separate production-network feasibility gate, not a proven repair.

Raw bodies, response headers, hashes, exact production adapter failures, RSS assessment, and the
surface decision are captured in `validation/transport-viability.json` and
`validation/transport-raw/` inside the review package.

## Earlier Browser-Capture Evidence

The prior bounded validation remains valid but has narrower meaning. On 2026-08-05 a public browser
session captured the configured newsroom and ten detail DOMs; replay through the adapter contract,
real acquisition engine, source profile, and temporary repository selected release
`20260805177075`, rejected a newer Sandisk false positive, extracted the complete 27,940-character
story, persisted 1,553,182 immutable source bytes, and passed repository integrity verification.

That evidence proves live-content parsing, strict qualification, terminal selection, normalized
metadata, and real persistence. It does **not** prove production acquisition and is now labeled
`historical-browser-capture-validation.json` in the package. Browser replay is not an operational
fallback.

## Discovery, Ordering, Qualification, and Selection

The configured search remains:

```text
https://www.businesswire.com/newsroom?keywords=ENTIRE_RELEASE%3Atrue%3Awdc
```

Fixture and captured DOM evidence show page one at the configured URL and subsequent pages by
preserving the query and appending `page=N`. The adapter now makes no newest-to-oldest assumption:
both latest and inclusive-range modes exhaust pagination before selection, subject to the explicit
50-page bound. Repeated page signatures fail as loops, canonical URLs are deduplicated, and hitting
the bound while a next page exists fails observably. A focused regression places the newest
qualified release on page two and verifies that latest mode still selects it.

Qualification remains detail-authoritative: the Business Wire publisher panel issuer must be
`Western Digital` or `Western Digital Corporation`, and ticker must be exactly `NASDAQ:WDC`.
Search membership, title/body mentions, listing snippets, JSON-LD author labels, release IDs, and
listing position cannot qualify a release. Latest chooses the greatest detail
`NewsArticle.datePublished`; inclusive range chooses the least timestamp within the supplied closed
date interval, with release ID and candidate ID as deterministic ties.

## Repository and Implementation Status

The adapter continues to use the existing acquisition trial, terminal-selection, source-profile,
firm-configuration, pull-workflow, and repository contracts. It does not write SQLite or content
storage directly. Exact fetched detail bytes are immutable artifacts; normalized extraction and
provenance are repository-owned attempt diagnostics. Exact reacquisition converges, while changed
bytes add their SHA-256 to validated revision identity and append a new immutable observation.

This successful implementation evidence is retained because it is useful if an authorized,
production-viable transport is later supplied at the existing seam. It does not change the blocked
operational result.

## Validation

The focused suite contains eleven tests, including the new out-of-order multi-page latest
regression. It also covers registration/config projection, strict issuer qualification, inclusive
range and no-result behavior, pagination and loops, complete extraction, idempotency and changed
bytes, malformed pages, repository failures, and the WDC-only boundary.

The regenerated package requires focused tests, configuration regressions, acquisition
regressions, historical browser-evidence verification, direct-transport-evidence verification,
`git diff --check`, and full `make validate` to pass. These validate the implementation and the
truthfulness/integrity of the blocking evidence; they do not convert the transport result to a
pass.

## Recommendation and Required Follow-up

Recommended source decision: **option 2**, after a separate feasibility gate—use WDC's
issuer-controlled archive for discovery and complete acquisition, retaining the canonical Business
Wire URL as related-source metadata. This preserves wire provenance without making the denied
Business Wire detail surface an availability dependency.

If the intended production network cannot directly reach the WDC archive, choose option 3 and
explicitly defer Business Wire support. Option 1 is less desirable than option 2 because discarding
the related Business Wire URL would lose useful provenance. A licensed Business Wire full-text feed
could also be considered in a separately authorized task with credentials, terms, and retention
rights made explicit.

Do not enable or schedule `wdc_press_release` until one of those source decisions is implemented and
validated through the real RFI acquisition path with raw direct-response evidence for latest and
inclusive-range behavior.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Architectural effect / limitation |
|---|---|---|---|
| WDC adapter implementation | Discovery/detail parsing and provenance | Implemented, Operationally Blocked | Transport cannot acquire live pages from RFI edge |
| Pagination/selection | Correct latest and inclusive-range reduction | Complete (fixture-backed) | Exhaustive bounded traversal; no listing-order assumption |
| Qualification | Exact WDC publisher panel and ticker | Complete (fixture/browser-content backed) | Detail metadata remains authority |
| Engine/repository integration | Durable selection and immutable bytes | Complete | Existing contracts and persistence path reused |
| Historical browser validation | Live-content parser and persistence proof | Complete, Non-operational | Does not prove direct transport |
| Direct Business Wire transport | Production discovery and complete retrieval | Blocked | urllib timeout; curl HTTP 403; RSS insufficient |
| WDC issuer archive alternative | Candidate discovery/acquisition source | Not Established | Publicly indexed, but current shell edge also receives 403 |
| Multi-firm Business Wire provider | Generalization | Not Started | Explicitly outside TASK-066 |

The next architectural milestone is an explicitly authorized source/transport decision, not a
claim that TASK-066 is operational and not generic Business Wire provider work.
