# ADR 0025: Reference Firm Identities and Effective Source Profiles

## Status

Accepted for TASK-040.

## Decision

Verified external identity is durable firm metadata in the provider-neutral
`firm_external_identities` relation. Versioned packaged catalogs populate only missing identities
for firms whose stable `firm_id` matches a catalog entry; they never overwrite a row.

Source-profile revisions continue to contain operator intent only. An empty candidate list means
"use the provider default" where verified identity and a supported artifact permit synthesis.
Explicit candidates take precedence. Resetting removes explicit candidates. The same pure synthesis
function serves UI projection and Pull planning.

SEC endpoints, accession numbers, archive paths, primary-document URLs, and filing observations are
not synthesized into durable configuration. Acquisition adapters continue to derive them at runtime.

## Consequences

- Additional providers can use the same firm identity boundary and add their own synthesizers.
- Reference data remains separate from configuration export/import.
- Existing explicit source-profile candidates retain their prior behavior.
- Catalog matching is deterministic and intentionally performs no online discovery.
