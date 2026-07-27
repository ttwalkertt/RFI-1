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
- TASK-024 regression repair: the obsolete Seagate fixture was replaced with the synthetic
  `task024-no-sec-identity` firm. Its enabled 10-Q item has no effective candidate, the aggregate
  result remains `failed`, and the pull-results API retains the exact firm/artifact navigation
  identity. The complementary TASK-040 test proves seeded Seagate receives `CIK:0001137789` and is
  not classified as missing candidate configuration.
- Baseline inventory repair: `scripts/check_baseline.py` now includes exactly
  `resources/reference-identities-v1.json` and `source_profiles/synthesis.py` in its ordered product
  file inventory; focused baseline validation passed.
- Final canonical validation command: `/usr/bin/time -p make validate`.
- Final canonical result: PASS in 54.85 seconds. All 392 tests passed; no tests were skipped or
  deselected. Acquisition, engine, EDGAR, SEC API, TASK-005 through TASK-023 deterministic proofs,
  lint, format, typecheck, import, documentation, and baseline gates passed. The source archive built
  with 412 members, 2,563,076 bytes, SHA-256
  `e4d959969d85c33d4e51c4b59f218583770efea1dd8ffd455ccc6d21d8e958f0`, and integrity PASS.
- Focused commands: `/usr/bin/time -p make baseline-check` passed in 0.05 seconds;
  `/usr/bin/time -p env PYTHONPATH=src .venv/bin/python -m unittest
  tests.test_task024.PullConfigurationNavigationTests.test_pull_results_api_supplies_exact_navigation_identity
  -v` passed 1 test in 0.88 seconds; `/usr/bin/time -p env PYTHONPATH=src .venv/bin/python -m
  unittest tests.test_task040 -v` passed 5 tests in 0.32 seconds. Neither focused suite reported skips
  or deselections.
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
