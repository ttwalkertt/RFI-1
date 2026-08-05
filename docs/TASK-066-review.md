# TASK-066 Architectural Review — WDC Business Wire Press Releases

## Result

TASK-066 is complete within its WDC-only boundary. The production pull composition now registers
`wdc_press_release`, projects the provider from Western Digital's external firm configuration,
discovers Business Wire release pages, qualifies issuer identity deterministically, and persists
one terminally selected release through the existing acquisition engine and immutable repository.
No provider writes SQLite or content storage directly, and no generic Business Wire abstraction was
introduced.

## Discovery, Parsing, Qualification, and Selection

The configured search is:

```text
https://www.businesswire.com/newsroom?keywords=ENTIRE_RELEASE%3Atrue%3Awdc
```

Business Wire's actual pagination control preserves that query and navigates to `page=N`; page two
was observed at the configured URL plus `&page=2`. Page one omits the parameter. The adapter parses
server-visible release cards, canonicalizes same-host detail URLs, deduplicates them, rejects
repeated page signatures and URLs as loops, and stops only on an explicit selection-aware boundary
or configured 50-page maximum. Release-ID dates are advisory traversal bounds only; detail-page
`NewsArticle.datePublished` is selection authority.

Detail parsing is separate from listing discovery. It extracts title, publication timestamp,
Business Wire publisher panel, canonical URL, release ID, dateline, subhead, complete story,
contacts, attachment links, and source attribution without script execution. Void HTML elements are
handled without extending extraction beyond their owning story/contact/sidebar containers.

Qualification requires the detail-page Business Wire publisher panel issuer to be either
`Western Digital` or `Western Digital Corporation` and the panel ticker to be exactly
`NASDAQ:WDC`. Live pages demonstrated both issuer labels and also demonstrated that JSON-LD
`author.name` may contain a media-contact label, so author metadata is deliberately not issuer
authority. Search membership, WDC mentions, titles, bodies, and listing order cannot qualify a
release.

Latest mode selects the greatest publication timestamp. Inclusive range mode selects the least
timestamp between supplied dates. Ties use Business Wire release ID and candidate ID. Exhaustive
range traversal with no qualifying release is a successful no-result outcome.

## Repository and Configuration Integration

`PressReleaseAcquisitionTarget` and its closed selection modes travel through `PullWorkflow`, the
existing adapter registry, terminal selection policy, `AcquisitionEngine`, source-profile revision,
and `AcquisitionRepository`. The existing `press_release` taxonomy is reused. The external firm
configuration remains authoritative; the checked-in WDC example and both schema copies admit only
the exact WDC-specific provider and configured search hint.

Fetched detail bytes are the immutable artifact. Normalized extraction and provenance are stored on
the repository-owned successful attempt. Exact reacquisition converges on retained evidence.
Changed source bytes add their SHA-256 to validated revision identity, producing a new immutable
artifact and observation while retaining the old bytes and history. Repository integrity and
conflict failures remain distinct observable terminal failures.

## Tests and Validation

The focused fixture suite contains ten tests covering registration and firm-config projection,
latest selection, inclusive range selection, explicit no-result, pagination, duplicate suppression,
strict qualification and a newer Sandisk false positive, metadata and complete-body extraction,
immutable idempotency and changed bytes, malformed discovery and detail pages, pagination loops,
repository failure classification, and rejection of non-WDC firm use.

The review generator records focused tests, configuration regressions, acquisition regressions,
live-evidence verification, `git diff --check`, and the full `make validate` suite in the package.
All commands must exit zero before package construction.

## Bounded Live Validation

On 2026-08-05, the configured newsroom returned ten first-page candidates. Seven qualified from
their detail publisher panels; the newest search hit was a Sandisk release and was rejected. The
selected release was `20260805177075`, “WD Reports Fiscal Fourth Quarter and Fiscal Year 2026
Financial Results,” published `2026-08-05T20:02:00+00:00`. Extraction retained a 27,940-character
complete story, 317-character subhead, 191-character contacts block, canonical URL, dateline, and
all other normalized fields. The real repository path persisted 1,553,182 evidence bytes as
artifact `artifact-737310dcc9d00f5c5a2ba97904336829973f2e76a8c9cb7f23efecbd8b8139ac`;
the stored SHA-256 and repository integrity verification both passed.

Direct command-line investigation was attempted first. Python HTTPS timed out, while a bounded curl
probe with browser-equivalent public headers received Business Wire Akamai `HTTP 403 Access
Denied`. Because direct access was demonstrably unavailable from this execution edge, the bounded
validation used a public browser session to load the configured newsroom and ten linked detail
pages. Complete `documentElement` HTML was serialized without modification, then replayed through
the adapter transport contract, acquisition engine, source profile, and real temporary repository.
The evidence explicitly records `browser_assisted_same_session_dom_capture`. Production remains
direct `urllib` HTTPS and contains no browser dependency or automation.

This validates live discovery content, detail retrieval content, parsing, qualification, selection,
and persistence, but it does not claim that this host's direct Business Wire edge path succeeded.

## Files Changed

- Acquisition contracts, WDC adapter, engine failure classification, and production registry.
- Pull workflow, source-profile validation, firm-config schemas/template, and WDC config example.
- Six press-release fixtures, focused tests, live validator, review generator, and baseline list.
- Acquisition/operator documentation, roadmap status, and this architectural review.

## Known Limitations and Follow-up

- Business Wire's DOM, JSON-LD timestamp, publisher panel, and `page=N` contract are external and may
  change; malformed or unsupported shapes fail observably rather than guessing.
- The production HTTP transport has a 25 MB response limit, 30-second request timeout, and no
  provider-local retry loop. Repository reruns provide durable retry semantics.
- Range traversal is capped at 50 pages unless a smaller source-profile maximum is configured.
- Release-ID dates are trusted only for traversal stopping, never for qualification or ordering.
- Attachments are retained when the story exposes direct multimedia or recognized document links;
  the selected live release exposed none in its story.
- A future generic Business Wire provider should extract the separated listing/detail parsers and
  transport contract only after another firm establishes shared semantics. TASK-066 must not be
  retroactively generalized.
- A future live run from an edge accepted by Business Wire should repeat the default direct-HTTPS
  validator and replace the browser-assisted transport limitation with raw-response evidence.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Architectural effect / limitation |
|---|---|---|---|
| WDC Business Wire adapter | HTTP discovery, parsing, candidate provenance | Complete | WDC-only; external markup contract |
| Terminal selection policy | Publisher qualification, date modes, deterministic ties | Complete | Two observed WDC publisher labels |
| Firm configuration/source profile | Authoritative provider and exact seed projection | Complete | External config remains operator-owned |
| Acquisition engine/repository | Durable selection, immutable bytes, history, idempotency | Complete | Existing contracts reused |
| Fixture validation | Deterministic behavior and failure coverage | Complete | Six checked-in fixtures |
| Live validation | Current discovery, extraction, qualification, persistence evidence | Usable with Limitations | Browser-assisted capture after direct edge denial |
| Future provider generalization | Multi-firm Business Wire semantics | Not Started | Requires a separately authorized milestone |

The next architectural milestone is not genericization by default. The recommended follow-up is a
direct-HTTPS live rerun from a Business Wire-accepted network edge; generic provider work should
wait for a second explicitly scoped firm and shared contract evidence.
