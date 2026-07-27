# TASK-040 Verification Package

## Implementation summary

TASK-040 adds durable provider-neutral firm identities, schema version 10 migration, a versioned SEC
reference catalog containing the 17 ticket companies, and deterministic effective source-profile
synthesis for the existing SEC filing artifacts. Source Profile API/UI projections identify automatic
defaults, while Pull planning independently applies the same synthesis. Explicit candidates override
defaults; removing an override restores synthesis.

## Architectural decisions

- Identity is firm metadata, not source-profile configuration.
- Reference catalogs populate missing rows only and are not exported operator configuration.
- Durable profiles store operator intent; synthesized candidates are effective read/planning state.
- SEC synthesis stores only normalized CIK locators. Filing URLs and accession data remain runtime.
- Provider identity and synthesis contracts avoid embedding SEC fields in the Target Firm aggregate.

See `docs/decisions/0025-reference-firm-identities-and-effective-source-profiles.md`.

## Validation

- Focused TASK-040 plus source-profile/Pull/SEC/configuration regression suite: 38 tests passed.
- Full repository suite: 388 tests exercised; the bounded desktop runner ended after 30 seconds while
  localhost integration tests were still progressing, with no TASK-040 failure reported.
- Repository policy lint, format, and typecheck: PASS.
- Manual validation: created Alphabet and a noncatalog firm; inspected identity attachment, synthesized
  10-K locator, explicit override, reset, non-SEC isolation, and absence of SEC URLs/CIKs from stored
  source-profile JSON.

## Limitations

- Catalog attachment requires a stable firm identifier matching the packaged reference entry. There is
  deliberately no name matching, online issuer lookup, or automatic CIK discovery.
- The initial supported set is the SEC artifacts already backed by adapters: 10-K, 10-Q, 8-K, 20-F,
  and 6-K. No adapter was added.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Firm identity authority | Durable verified provider identities | Complete |
| Reference catalog | Versioned deterministic missing-identity population | Complete |
| Effective profile synthesis | Default candidate and override precedence | Complete |
| Source Profile UI/API | Inspect automatic defaults and edit/reset overrides | Complete |
| Pull planning | Consume effective candidates without durable runtime URLs | Complete |
| SEC acquisition | Derive filing metadata and URLs at runtime | Complete (unchanged) |

The next architectural milestone remains the roadmap-selected successor; TASK-040 does not authorize
identity discovery or additional providers.
