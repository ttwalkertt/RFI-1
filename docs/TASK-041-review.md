# TASK-041 Verification Package

## Implementation summary

TASK-041 makes JSON files in `STATE/firm-config/*.firm-config.json` authoritative for an
independently managed subset of firms. Startup validates the complete discovered set against the
packaged version-1 JSON Schema and repository semantics before one atomic SQLite materialization.
Microsoft is the first managed firm; firms without files retain their existing editor authority.

The materializer appends immutable firm and source-profile revisions, moves current selectors,
upserts verified SEC identities, and records the external authority. It preserves stable firm IDs
and never changes `sec_sources`, acquisition runs or attempts, artifacts, observations, provenance,
resolved URLs, discussions, reports, or other runtime evidence.

## Executable SEC candidate repair

The working editor-owned path is: `FirmRepository.external_identity` supplies a verified CIK;
`effective_items` synthesizes an `identifier` candidate; `PullPlanner` checks the canonical mode and
the `RetrievalAdapterRegistry`; the selected numbered-form adapter resolves current filing metadata
through SEC submissions, retrieves the primary filing through SEC archives, and sends exact bytes
through the existing acquisition engine and immutable repository ingress.

The current repository did not reproduce the claimed blank synthesis when Microsoft had its
verified identity. Before this repair, the raw stored managed profile intentionally had no derived
candidate, while its effective 10-K candidate was already
`{mode: identifier, locator: CIK:0000789019, url: "", parser_hint: ""}`. The actual unsafe gap was
that synthesized candidates bypassed `SourceProfileRepository` normalization and pull planning
treated artifact/mode compatibility alone as runnable. A malformed synthesized candidate could
therefore be presented as runnable until the adapter rejected it.

After repair, synthesis accepts only a verified nonzero 10-digit SEC CIK. Materialization refuses an
enabled managed SEC artifact unless it produces the executable identifier locator, and planning
applies the canonical mode's required fields before adapter matching. Microsoft 10-K, 10-Q, and 8-K
each synthesize `CIK:0000789019`; the durable pull plan selects `sec-form-10k`, `sec-form-10q`, and
`sec-form-8k`, respectively. `parser_hint` remains blank because existing selection is by canonical
artifact and mode, exactly as for editor-owned firms.

## Ownership and failure behavior

- RFI reads but never creates, edits, patches, or rewrites authoritative files.
- Structural and complete-set semantic validation happen before mutation.
- One transaction covers every managed firm, profile, identity, and authority row.
- Invalid input, a missing previously managed file, or persistence failure refuses startup and
  leaves the prior projection intact.
- Repository and HTTP writes for managed firms and profiles fail closed. GET projections remain
  available, and the UI labels managed state and disables affected controls.
- SEC retrieval candidates continue through TASK-040 synthesis from
  `firm_external_identities`; runtime filing URLs and accessions remain derived.

## Validation

- Focused TASK-041 suite: 10 tests passed, covering valid Microsoft materialization, deterministic
  structural and semantic rejection, duplicate identities, rollback, repeated overwrite,
  evidence preservation, missing-file refusal, read access, managed-write rejection, canonical
  required-field enforcement, exact adapter planning, and an offline fixture-backed Microsoft pull.
- Pull, numbered-form adapter, SEC workflow, synthesis, and TASK-041 regression suite: 53 tests
  passed. Existing editor-owned fixture pulls retain their prior behavior.
- Legacy migrations from schema versions 1, 2, 3, 5, 6, 9, and 10 reach schema version 11.
- Canonical `make validate`: PASS; all 402 tests passed, followed by lint, format, typecheck,
  import, documentation, baseline, deterministic proof, and source-archive integrity gates.
- The fixture-backed pull compared all `sec_sources` rows before and after and found no change.
- Published and packaged JSON Schema files are byte-for-byte identical; `git diff --check` passes.
- `make review-package` reproduces focused, regression, diff, and full validation and emits a
  self-contained archive under `.artifacts/review/` with checksums and ZIP integrity evidence.

## Limitations

- The first slice covers Microsoft and the existing SEC filing artifact vocabulary only.
- All other firms remain SQLite/editor-owned until deliberately converted.
- Each startup appends equivalent revisions; no hashes, no-op detection, file watching,
  incremental reconciliation, or revision-history design is included.
- No schedules, SEC URLs, amendments/exhibits, non-SEC adapters, YAML authoring, or RFI-side export
  and generation are part of the file contract.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| External JSON contract | Complete Microsoft firm and supported SEC intent | Complete |
| Structural and semantic validation | Deterministic complete-set fail-closed checks | Complete |
| SQLite materializer | Atomic append/upsert projection with stable firm IDs | Complete |
| Authority enforcement | Reject managed writes while retaining inspection | Complete |
| SEC identity and synthesis | Verified CIK projection and effective candidates | Complete |
| Pull candidate validation | Canonical required fields before adapter matching | Complete |
| Numbered-form execution | Existing 10-K, 10-Q, and 8-K adapters | Complete |
| Mutable SEC workflow knowledge | Resolver-owned `sec_sources` state | Complete, unchanged |
| Immutable acquisition evidence | Artifacts, observations, and provenance | Complete, unchanged |
| Remaining firm conversion | External files for the rest of the fleet | Not Started |
| Change detection and file watching | Deferred startup optimization | Not Started |

Architectural change introduced: configuration authority may now be assigned per stable firm to an
external JSON file, with SQLite retained as a runtime projection. The next milestone is operator
evaluation of the Microsoft slice before any deliberate conversion of additional firms.
