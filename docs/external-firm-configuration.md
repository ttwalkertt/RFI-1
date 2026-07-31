# External firm configuration

TASK-041 permits external tooling to own a bounded set of complete firm configurations while RFI
retains SQLite as its runtime/query representation.

## File location and contract

For state `STATE`, RFI reads exactly:

```text
STATE/firm-config/*.firm-config.json
```

There are no other search paths and no file watcher. The version-1 authoring contract is
`docs/firm-config-v1.schema.json`; `docs/microsoft.firm-config.example.json` is the initial example.
RFI reads these files but never creates, edits, normalizes, exports, or patches them.

Every discovered file is parsed with duplicate-key rejection, checked against the Draft 2020-12
schema, and then checked for repository semantics. The entire lexical filename-ordered set must be
valid before configuration changes. Diagnostics identify the filename and JSON Pointer. A malformed,
invalid, duplicate, conflicting, or missing previously managed file refuses startup.

## Ownership and projection

An accepted file owns the current configuration projection for its `firm.id`:

- `firms`, `firm_revisions`, `firm_identifiers`, and `firm_domains`;
- `firm_external_identities` for the verified SEC identity;
- `source_profiles`, `source_profile_revisions`, and `source_profile_items`; and
- `firm_config_authorities`, which records ownership and the exact canonical JSON projection.

Materialization appends immutable firm/profile revisions and moves their current selectors. Stable
`firm_id` values and old revisions remain intact. Rewriting occurs on every startup; unchanged-file
no-op detection is intentionally absent.

The transaction does **not** write `sec_sources`. That table remains mutable SEC workflow knowledge
owned and refreshed by the authoritative SEC retrieval workflow. It also does not write governed
sources, acquisition runs, attempts, observations, artifacts, hashes, provenance, resolved URLs or
accessions, discussions, streams, reports, source objects, or derived knowledge.

The SEC file identity populates `firm_external_identities`. Existing source-profile synthesis then
provides CIK candidates for enabled SEC artifacts; endpoints, filing metadata, accessions, archive
URLs, and primary-document URLs continue to be derived during acquisition.

## Startup and rollback

Database initialization/migration runs first. Fresh initialization validates and materializes the
complete file set in one `BEGIN IMMEDIATE` transaction. Ordinary serving and acquisition startup
validates and loads the set without publishing projection revisions; explicit governed
materialization applies deliberate configuration changes.
Any persistence error rolls back every firm, identity, profile, current selector, ownership row, and
repository revision change in the set. RFI does not continue with partially loaded configuration.

Once `firm_config_authorities` marks a firm external, removal of its file fails startup. Authority
does not silently return to SQLite editors. Other firms can remain editor-owned during the bounded
transition.

## Operator behavior

Externally managed firms and source profiles remain visible in the Target Firms
pages and through GET APIs. They show the external filename and are read-only. Repository, service,
and HTTP publication paths reject attempts to revise, retire, or save a managed firm/profile.

The initial Microsoft example enables current 10-K, 10-Q, and 8-K artifacts. The contract contains
no schedules, SEC endpoint URLs, amendment/exhibit policy, historical selection policy, arbitrary
non-SEC parsers, or unimplemented adapters.

For each enabled SEC artifact, startup requires the verified external identity to synthesize the
existing executable `identifier` candidate with locator `CIK:<10 digits>`. Pull planning applies the
canonical retrieval-mode requirements before capability matching. The numbered-form adapter is
then selected by canonical artifact plus mode (`sec-form-10k`, `sec-form-10q`, or `sec-form-8k`);
`parser_hint` is not required and remains blank. Failure to synthesize a valid locator refuses
startup without writing `sec_sources`.

## Verification

Run focused coverage with:

```sh
make task041-test
```

Run the canonical repository gate and generate the review package with:

```sh
make validate
make review-package
```
