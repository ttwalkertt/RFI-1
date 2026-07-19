# ADR-0018 — Artifact-specific SEC numbered-form adapters

## Status

Accepted and implemented by TASK-022.

## Decision

Add four concrete adapters for canonical `sec_10q`, `sec_8k`, `sec_20f`, and `sec_6k`. Each owns
one exact base form, amendment exclusion, multiplicity semantics, canonical mapping, and
form-specific no-match result. Retain the concrete Form 10-K adapter.

Extract a small `SecNumberedFormAdapter` mechanics base for deterministic latest selection,
duplicate-accession conflict detection, primary-document projection, CIK validation, and common
provider-native provenance. It has no runtime form configuration or dispatch table. Continue to
use `SecProviderClient` solely for bounded provider mechanics and existing Pull Workflow,
acquisition, repository, query, browser, and integrity contracts for all downstream behavior.

Treat an accession as provider-native filing identity associated with the issuer by the
authoritative issuer submissions record. Do not require its prefix to equal the issuer CIK; live
evidence proved valid filings can use a third-party filer prefix. Continue to validate accession
syntax and build the archive path beneath the issuer CIK directory.

## Alternatives

A universal form-parameterized adapter, arbitrary form-code configuration engine, generic SEC
policy table, pull-workflow form branches, persistence-aware adapters, amendment inclusion,
complete-submission or exhibit retrieval, and historical stream synchronization were rejected.

## Consequences

New canonical numbered forms require a new explicit adapter policy class and non-overlapping
capability. Shared mechanics can evolve once for all five adapters without absorbing canonical
policy. Form 8-K and Form 6-K remain high-frequency streams even though the current pull selects
one latest filing. Later bounded history can reuse accession/document identity without changing
repository semantics. Adapters remain independent of SQLite and every persistence substrate.
