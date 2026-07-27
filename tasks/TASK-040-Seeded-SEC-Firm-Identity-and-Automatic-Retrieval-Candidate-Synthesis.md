# TASK-040: Seeded SEC Firm Identity and Automatic Retrieval Candidate Synthesis

## Status

Draft

## Objective

Reduce operator effort by automatically synthesizing deterministic SEC
retrieval candidates from verified firm identity information.

The operator should identify a public company once. RFI should
automatically configure the standard SEC retrieval candidate for
supported filing types (10-K, 10-Q, 8-K, DEF 14A, etc.) rather than
requiring manual entry of CIKs, SEC endpoints, parser hints, and stable
locators.

------------------------------------------------------------------------

## Motivation

The current Source Profile exposes implementation details that are
deterministic and belong to the retrieval subsystem.

For SEC filings, operators should not repeatedly enter:

-   CIK
-   SEC endpoints
-   Stable locator
-   Parser hint
-   Retrieval mode

These values are derived from verified SEC issuer identity.

------------------------------------------------------------------------

## Scope

### 1. Firm SEC identity

Extend the Target Firm model with durable SEC identity metadata:

-   SEC legal issuer name
-   Normalized CIK
-   Filing regime
-   Verification status
-   Verification timestamp
-   Verification source

This identity belongs to the firm rather than individual source items.

### 2. Seed dataset

Add a repository seed containing a modest collection of well-known
public companies.

Suggested initial population:

-   Alphabet
-   Microsoft
-   Apple
-   Amazon
-   Meta
-   NVIDIA
-   AMD
-   Intel
-   Seagate
-   Western Digital
-   IBM
-   Dell
-   Hewlett Packard Enterprise
-   Broadcom
-   Micron
-   TSMC
-   Samsung Electronics

Seed only durable identity information. Do not seed filing metadata.

### 2a. Reference identity catalog

The initial SEC identity seed shall be implemented as a **reference
identity catalog**, not as application configuration.

Requirements:

-   Store the catalog separately from application configuration.
-   Load the catalog during initialization or migration to populate
    missing firm SEC identities.
-   Existing firm records are not overwritten.
-   The catalog is versioned so future updates can extend or correct
    reference data.
-   Future provider-specific identity catalogs (e.g., Companies House,
    EDINET, SEDAR+, OpenCorporates) can follow the same pattern without
    redesigning the Target Firm model.

The reference catalog is an implementation detail supporting initial
population and future maintenance. It is not an operator-managed
configuration artifact.

### 3. Automatic synthesis

When:

-   a verified SEC identity exists, and
-   an SEC-backed source item is enabled,

RFI automatically synthesizes the default retrieval candidate.

The operator should not manually populate CIKs, SEC URLs, parser hints,
or stable locators for normal cases.

### 4. Runtime derivation

At acquisition time derive:

-   SEC submissions endpoint
-   Filing metadata
-   Accession number
-   Archive URL
-   Primary document URL

These are acquisition provenance and must not become durable
configuration.

### 5. UI

Replace mostly-empty SEC configuration forms with synthesized
configuration.

Example information displayed:

-   Issuer
-   Verified CIK
-   Verification status
-   Retrieval automatically configured
-   Adapter
-   Selection policy

Provide an Advanced section for overrides.

### 6. Overrides

Allow explicit operator overrides while preserving visibility of
inherited configuration.

Provide Reset to default.

------------------------------------------------------------------------

## Out of Scope

-   Automatic internet company lookup
-   SEC search services
-   Automatic CIK discovery
-   New acquisition adapters
-   Changes to acquisition behavior beyond consuming synthesized
    configuration

------------------------------------------------------------------------

## Acceptance Criteria

-   Firm records support durable SEC identity.
-   Repository contains an initial SEC identity seed dataset.
-   Existing repositories migrate successfully.
-   Supported SEC document types automatically synthesize retrieval
    candidates.
-   Operators are no longer required to manually configure normal SEC
    retrieval metadata.
-   Runtime URLs remain derived rather than persisted.
-   Existing manual configurations continue to work unchanged.
-   Override behavior is explicit and reversible.

------------------------------------------------------------------------

## Review Checklist

Verify:

-   Deterministic synthesis
-   Correct generation for seeded firms
-   Override precedence
-   Reset behavior
-   Runtime URLs are not persisted
-   Graceful behavior for firms without SEC identity
-   Clean repository migration
-   No regressions for non-SEC sources

------------------------------------------------------------------------

## Validation

### Unit

-   SEC identity model
-   Seed loader
-   Candidate synthesis
-   Override precedence
-   Migration

### Integration

1.  Create a Target Firm for Alphabet.
2.  Enable the 10-K source.
3.  Verify the SEC retrieval candidate is automatically populated.
4.  Acquire the latest filing successfully.

### Regression

-   Existing repositories remain functional.
-   Manual SEC configurations continue to operate.
-   Export/import preserves synthesized and overridden state.

------------------------------------------------------------------------

## Notes

Keep this task intentionally focused on usability and deterministic
configuration synthesis. Automatic issuer discovery, online
verification, and broader provider integration are deferred to future
tasks.
