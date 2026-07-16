# TASK-009 — Extensible Business Concept Catalog and Admin Console

## Status

Ready

## Architectural Milestone

Establish an extensible business concept catalog and the first repository-hosted admin web console for RFI-1.

The concept catalog provides durable, editable definitions for business concepts that may be observed through extracted evidence, deterministic calculation, categorical state, event, range, forecast, relationship, narrative assertion, or other future observation modes.

The admin web console becomes the operator-facing administration surface for managing these definitions. The concept catalog is implemented as one tab within that broader console architecture.

## Purpose

RFI-1 can now acquire evidence, derive knowledge, retrieve governed evidence, perform bounded intelligence, and preserve consulting investigations.

The next architectural need is a durable way to define what the repository means by a business concept and how that concept may be observed or derived.

The initial implementation must remain deliberately generic because the concept model is expected to evolve through operational use and domain learning.

TASK-009 must establish:

- durable concept definitions;
- extensible observation and derivation methods;
- historical validity;
- operator lookup, browsing, and editing;
- a simple local admin web console;
- practical proof using both financial and non-financial concepts.

The task should avoid prematurely fixing the final ontology, financial schema, calculation language, or extraction architecture.

## Core Principles

### Concept and Observation Separation

A concept definition describes what a concept means and the admissible ways it may be observed or derived.

An observation is a specific assertion, value, state, event, relationship, range, forecast, or calculated result associated with a concept.

Concept definitions must remain distinct from:

- source evidence;
- extracted observations;
- calculated observations;
- reconciliation results;
- retrieval indexes;
- intelligence results;
- workspace investigations.

### Multiple Observation Methods

A concept may support zero, one, or multiple observation methods.

Examples include:

- directly extracted quantity;
- directly extracted ratio;
- deterministic calculation;
- categorical state;
- event or milestone;
- Boolean assertion;
- range;
- directional statement;
- forecast or target;
- relationship;
- narrative claim;
- future method types not yet anticipated.

Different methods for the same concept may coexist.

An extracted value must not overwrite a calculated value.

A calculated value must not suppress an extracted value.

### Generic Foundation

The base implementation must be generic enough to support substantial future realignment.

The initial model must not assume that every concept is:

- numeric;
- financial;
- a ratio;
- a date;
- reducible to a fixed schema;
- populated by only one method.

Codex should use engineering judgment to choose a disciplined extensibility model.

## Required Capabilities

### Durable Concept Definitions

The catalog must support durable concept definitions with at least:

- stable identifier;
- pretty or display name;
- concise definition;
- longer comments or notes;
- aliases;
- lookup and extraction hints;
- status;
- tags or classification metadata;
- valid-from date;
- optional valid-through date;
- optional sample or example date;
- creation timestamp;
- update timestamp;
- revision or version identity.

Codex may add fields where useful, but should avoid over-specializing the base model.

### Validity and Historical Versions

Concept definitions must preserve historical meaning.

The system must support:

- current definitions;
- prior revisions;
- validity intervals;
- supersession or retirement;
- inspection of prior versions;
- prevention of silent historical mutation.

Edits to a concept definition must not invisibly reinterpret historical observations.

### Observation and Derivation Methods

A concept may reference zero or more admissible methods.

A method definition may describe, as appropriate:

- method identity;
- method kind;
- value or result shape;
- extraction hints;
- aliases;
- expected evidence locations;
- deterministic formulas or derivation rules;
- required inputs;
- optional inputs;
- units;
- dimensions;
- period and scope expectations;
- validation conditions;
- comparison semantics;
- confidence rules;
- tolerance or reconciliation guidance;
- warnings;
- comments;
- validity metadata;
- sample cases.

The base architecture should allow method-specific configuration without requiring the core catalog to understand every future method type.

### Deterministic Derivation

The catalog must support methods that produce deterministic results from other observations.

The implementation must prove:

- explicit input dependencies;
- deterministic evaluation;
- unit and period checks where applicable;
- failed preconditions;
- missing-input behavior;
- preserved input lineage;
- result provenance;
- no overwrite of extracted observations;
- coexistence and comparison of extracted and calculated values.

The task does not require a complete financial calculation engine or final formula language.

### Nonnumeric Concepts

The architecture must support concepts that are not ratios, dates, or simple numeric values.

Examples include:

- HAMR qualification state;
- shipment milestone;
- volume shipment start;
- customer qualification;
- guidance state;
- product relationship;
- narrative assertion.

The sample implementation must prove at least one categorical or stateful concept and one event-oriented concept.

### Lookup

The system must support concept lookup by practical operator-facing criteria, including:

- stable ID;
- pretty name;
- alias;
- keyword;
- tag or classification;
- status;
- validity date.

Lookup must be available through both a programmatic interface and the admin web console.

### Browser

The operator must be able to browse:

- concept lists;
- concept details;
- aliases and hints;
- current revision;
- version history;
- validity intervals;
- observation methods;
- deterministic derivations;
- validation rules;
- related concepts;
- comments;
- sample cases;
- warnings.

### Editor

The operator must be able to:

- create a concept;
- edit descriptive metadata;
- add or remove aliases and hints;
- add comments;
- assign tags or classification;
- set validity dates;
- define or revise observation methods;
- define or revise deterministic derivations;
- validate the definition;
- inspect prior versions;
- retire or supersede a concept;
- save a new revision without deleting history.

The editor must clearly distinguish current edits from historical versions.

## Admin Web Console

### Console Architecture

TASK-009 must establish a simple repository-hosted admin web console.

The concept catalog GUI is one tab within the console.

The architecture should permit later admin tabs for other repository subsystems without requiring a rewrite of the web application.

Potential future tabs might include:

- source registry;
- acquisition status;
- retrieval health;
- workspace administration;
- operational metrics;
- backup and restore.

These future tabs are not required by TASK-009.

### Hosting Requirements

The admin console must:

- run locally from the repository;
- use a small-footprint Python server;
- bind to a local interface by default;
- avoid external cloud dependencies;
- expose a documented startup command;
- support configurable host and port;
- have clear shutdown behavior;
- use a repository-controlled data location;
- integrate with catalog public contracts rather than bypassing them.

Codex may select the server and UI stack.

The task does not prescribe Flask, FastAPI, Starlette, Bottle, a standard-library server, or any specific frontend framework.

### Minimum Console Experience

The admin console must provide at least:

- a persistent top-level console shell;
- navigation suitable for multiple admin tabs;
- a Concept Catalog tab;
- concept search and filtering;
- concept list;
- concept detail view;
- create/edit form;
- method and derivation editing;
- version-history view;
- validation results;
- sample or example display;
- clear error handling.

Visual polish is secondary to practical usability and maintainable architecture.

### Security Boundary

The initial console is single-user and local-only.

At minimum:

- bind locally by default;
- do not expose credentials;
- do not persist secrets in browser-visible state;
- validate all writes;
- protect against accidental arbitrary file access;
- document that authentication and multi-user authorization are not yet implemented.

## Sample Concept Proof Set

Provide a small, diverse sample catalog sufficient to prove the architecture.

At minimum include:

### Revenue

Demonstrate a concept commonly populated through extracted quantities.

### Gross Margin

Demonstrate:

- an extracted reported ratio;
- a deterministic calculation from gross profit and revenue;
- an alternate deterministic calculation from revenue and cost of revenue;
- coexistence of extracted and calculated observations;
- a sample reconciliation or comparison;
- preserved lineage.

### HAMR Qualification

Demonstrate a categorical, stateful, or milestone concept.

The implementation should preserve scope and context rather than reducing the concept to a bare Boolean.

### HAMR Shipments

Demonstrate an event-oriented and potentially multi-shaped concept.

Examples may include:

- shipments started;
- volume shipments started;
- units shipped;
- capacity shipped;
- customer count;
- narrative shipment assertion.

The sample concepts are architectural proofs, not the final RFI-1 business ontology.

## Functional Proof

Demonstrate:

1. Initialize the concept catalog.
2. Start the local admin web console.
3. Open the Concept Catalog tab.
4. Browse seeded concepts.
5. Look up concepts by ID, name, alias, keyword, and validity date.
6. Create a new generic concept.
7. Edit its metadata and comments.
8. Add validity and sample dates.
9. Add an extracted observation method.
10. Add a deterministic derivation method.
11. Validate the concept.
12. Save a new revision.
13. Inspect revision history.
14. Retire or supersede a concept without deleting history.
15. Demonstrate extracted and calculated gross-margin observations coexisting.
16. Demonstrate deterministic calculation lineage.
17. Demonstrate HAMR qualification as a nonnumeric state or milestone.
18. Demonstrate HAMR shipments as an event-oriented or multi-shaped concept.
19. Restart the server and confirm persistence.
20. Exercise the programmatic lookup API independently of the GUI.

## Failure Semantics

Demonstrate behavior for:

- invalid concept identifier;
- duplicate identifier;
- invalid validity interval;
- malformed method configuration;
- unknown method kind;
- invalid deterministic derivation;
- missing required inputs;
- incompatible units or periods where applicable;
- calculation failure;
- invalid revision update;
- attempted historical mutation;
- corrupted catalog state;
- invalid browser request;
- invalid form submission;
- unsafe file path or traversal attempt;
- unavailable port;
- interrupted write.

Failures must remain visible and must not silently corrupt catalog history.

## Architectural Constraints

- Catalog storage and lifecycle remain independent of evidence storage.
- Concept definitions do not become source evidence.
- Catalog definitions do not become observations merely by existing.
- Deterministic derivations must retain input lineage.
- Historical revisions must remain inspectable.
- The GUI must use catalog public contracts.
- The GUI must not directly edit persistence internals.
- The admin console must be structured for future tabs.
- The base implementation must remain generic and extensible.
- The sample catalog must not be treated as a complete domain ontology.
- The system must not silently reconcile conflicting observations.
- The implementation must not fabricate unavailable values, dates, units, confidence, or provenance.

## Documentation Requirements

Document:

- concept catalog architecture;
- distinction among concepts, methods, observations, and derivations;
- revision and validity semantics;
- deterministic derivation behavior;
- admin console architecture;
- local startup and shutdown;
- data location;
- host and port configuration;
- backup implications;
- sample concepts;
- extension guidance;
- known limitations;
- expected areas of future learning and realignment.

Create an ADR for the catalog and admin-console architecture.

## Validation Expectations

Validation must include:

- concept lifecycle;
- version history;
- validity semantics;
- lookup behavior;
- extracted method support;
- deterministic derivation support;
- nonnumeric concept support;
- event-oriented concept support;
- lineage preservation;
- GUI startup;
- GUI browsing and editing;
- local-only default binding;
- invalid request handling;
- persistence across restart;
- repository-wide validation;
- documentation validation;
- design baseline checks;
- secret scan;
- review-package integrity.

## Required Review Package

Produce:

- implementation summary;
- architectural decisions;
- catalog schema or contract overview;
- concept/method/observation boundary explanation;
- admin console walkthrough;
- screenshots or rendered proof of the Concept Catalog tab;
- concept lookup examples;
- editing and revision examples;
- validity examples;
- deterministic calculation example;
- extracted-versus-calculated coexistence example;
- HAMR qualification example;
- HAMR shipments example;
- failure proofs;
- validation results;
- known limitations;
- cumulative patch;
- Architectural Status Summary.

## Architectural Status Summary

Report status for:

- repository foundation;
- acquisition;
- immutable evidence;
- source objects;
- derived knowledge;
- governed retrieval;
- model-guided intelligence;
- consulting workspace;
- execution journal and logging;
- business concept catalog;
- deterministic derivation;
- admin web console;
- operational hardening.

Clearly distinguish architectural completeness from operational maturity and domain-model maturity.

## Non-Goals

This task does not require:

- a final business ontology;
- a comprehensive financial taxonomy;
- full XBRL support;
- automatic production-grade extraction;
- a complete formula language;
- automatic reconciliation of conflicts;
- authentication;
- multi-user authorization;
- remote hosting;
- cloud deployment;
- collaboration;
- workflow scheduling;
- polished visual design;
- mobile optimization;
- production observability;
- public internet exposure.

## Completion Standard

TASK-009 is complete when RFI-1 has a durable, revision-aware, extensible business concept catalog that supports multiple observation and derivation methods, deterministic calculation lineage, nonnumeric and event-oriented concepts, programmatic lookup, and practical operator management through a Concept Catalog tab in a locally hosted repository admin web console.
