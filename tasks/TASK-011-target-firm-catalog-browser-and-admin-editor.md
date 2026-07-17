# TASK-011 — Target Firm Catalog, Browser, and Admin Editor

## Status

Complete — identity/relationship authority boundary corrected

## Architectural Milestone

Create a durable target-firm catalog and make the firm the primary organizing context for future corpus acquisition, browsing, and source-grounded question answering.

TASK-011 should establish a practical firm registry, browser, and admin editor without prematurely defining the final entity-extraction or knowledge model.

## Purpose

RFI-1 now has a business concept catalog and an operator-facing admin console. The next step is to make the system immediately useful for consulting work by organizing research around the companies being studied.

A target firm should be more than a name in a list. It should provide a stable identity that future subsystems can use to:

- recognize a company across sources;
- associate documents and observations with the correct firm;
- guide source discovery and acquisition;
- browse accumulated knowledge by company;
- support later firm-centric question answering.

The firm catalog should become a natural entry point into the broader intelligence system.

## Product Direction

Selecting a firm should eventually lead to a firm-centered view of:

- identity and aliases;
- source coverage;
- acquired documents;
- filings and earnings materials;
- products and technologies;
- evidence-backed business and corporate-network relationships from a future relationship graph;
- concepts and observations;
- analyst notes;
- unresolved extraction issues;
- consulting workspaces;
- source-grounded questions and answers.

TASK-011 does not need to implement all of those capabilities. It should establish the catalog and user experience that future milestones can extend.

## Required Capabilities

### Target Firm Authority

Create a target-firm subsystem with a clear public contract and durable persistence.

The design should support stable firm identity and practical recognition metadata, including fields such as:

- canonical name;
- legal name;
- aliases;
- ticker symbols;
- exchange or market identifiers;
- website or domain hints;
- headquarters or jurisdiction where useful;
- sector, industry, and technology focus;
- source-discovery hints;
- operator notes;
- status and validity information.

Codex should determine the precise schema and revision model based on the existing repository architecture.

The model must remain extensible because firm identity and recognition practices will evolve
through use. It must not embed business-network or corporate-relationship edges. Competitor,
customer, supplier, partner, technology, strategic, parent, subsidiary, brand, predecessor,
successor, and similar relationships belong in a future evidence-backed relationship graph with
provenance, validity, confidence, and source support.

### Firm Browser

Add a Target Firms tab or equivalent firm-centered page to the admin console.

The browser should support:

- listing and searching firms;
- filtering by useful status or classification fields;
- opening a firm detail view;
- displaying canonical identity and recognition metadata;
- showing aliases, identifiers, classifications, notes, and source hints clearly;
- providing useful empty, error, and loading states.

The browser should follow the interaction standards established by TASK-010.

### Firm Editor

Provide an operator-friendly editor for creating and updating target-firm records.

The editor should:

- use typed controls;
- provide field-level contextual help;
- support repeated values such as aliases, tickers, domains, technology focus, and source hints;
- validate conflicts and missing required fields;
- preserve entered data after validation failure;
- protect unsaved changes;
- make update or revision semantics clear;
- avoid requiring raw JSON editing.

Reuse the shared admin-console patterns from TASK-010 rather than creating a second interaction model.

### Seeded Consulting Proof

Provide representative target-firm records suitable for HDD and adjacent technology consulting.

At minimum include:

- Seagate;
- Western Digital;
- Toshiba.

Additional examples may be included where useful.

The proof should demonstrate that aliases, ticker or market identity, domains, classifications,
notes, and source hints can be entered, browsed, persisted, and retrieved through public contracts.

### Integration Readiness

The firm catalog should be designed so later tasks can attach:

- source acquisition policies;
- source objects and documents;
- extracted entities;
- concepts and observations;
- workspace investigations;
- question-answering context.
- evidence-backed relationship-graph nodes and edges through stable firm references.

TASK-011 should not tightly couple those systems prematurely, but it should define stable identity references that they can use.

## Architectural Principles

- The firm catalog defines **who the target is and how to recognize it**.
- Evidence and source objects define **what was published**.
- Concepts and observations define **what was extracted, calculated, or asserted**.
- Workspaces and intelligence define **how the material is investigated and used**.
- A future relationship graph defines **which evidence-backed business or corporate-network edges
  are asserted**, with provenance, validity, confidence, and source support.

Keep these authority boundaries explicit.

Do not make the firm catalog the storage location for arbitrary extracted knowledge.

## Functional Proof

Demonstrate:

1. Creating a target firm through the admin editor.
2. Editing aliases, identifiers, domains, notes, and source hints.
3. Browsing and searching target firms.
4. Detecting an invalid or conflicting identifier.
5. Preserving operator input after validation failure.
6. Protecting unsaved changes.
7. Persisting records across restart.
8. Retrieving firm records through a public API or service contract.
9. Browsing seeded Seagate, Western Digital, and Toshiba records.
10. Showing that future source and knowledge systems can reference stable firm identities without direct persistence coupling.

## Documentation

Document:

- target-firm subsystem purpose;
- identity and authority boundaries;
- browser and editor workflow;
- field-help approach;
- persistence and update semantics;
- seeded consulting examples;
- extension points for corpus acquisition and question answering;
- known limitations and likely realignment areas.

Add an ADR for the durable firm-identity model and its explicit relationship-graph boundary.

## Validation

Include:

- focused target-firm tests;
- browser and editor proof;
- persistence and restart proof;
- conflict and validation proof;
- full repository tests;
- lint, formatting, and type checks;
- documentation and design-baseline checks;
- review-package integrity;
- repository-standard secret and archive checks where applicable.

## Required Review Package

Produce a TASK-011 review package containing:

- implementation summary;
- architecture summary;
- changed files;
- target-firm contract examples;
- seeded firm proof;
- browser and editor evidence;
- validation and failure evidence;
- persistence proof;
- integration-readiness notes;
- known limitations;
- validation results;
- Architectural Status Summary.

## Non-Goals

TASK-011 does not require:

- production-scale corpus acquisition;
- final entity extraction or normalization;
- a universal corporate hierarchy model;
- competitor, customer, supplier, partner, technology, strategic, or other business-network edges;
- parent, subsidiary, brand, predecessor, successor, or other corporate-network edges;
- automatic subsidiary discovery;
- security-master completeness;
- real-time market data;
- complete product or technology catalogs;
- full competitive-relationship inference;
- question answering across a large corpus;
- authentication or multi-user operation.

## Completion Standard

TASK-011 is complete when RFI-1 has a durable, extensible target-firm authority with a practical browser and editor, representative HDD-industry firms can be managed through the admin console, and future acquisition and question-answering work can rely on stable firm identities without prematurely fixing the broader extraction model.
