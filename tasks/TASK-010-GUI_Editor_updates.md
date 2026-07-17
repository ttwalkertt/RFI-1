# TASK-010 — Admin Console Usability and Schema-Aware Concept Editor

## Status

Complete

Implement TASK-010 with the following product and interaction guidance.

Product intent

The Concept Catalog editor is not merely a one-off TASK-009 interface. It is the reference implementation for the rest of the RFI-1 admin console.

Design it so an operator can return after several weeks, with little memory of the underlying contracts, and still understand:

* what each field means;
* how the system uses it;
* what is safe to edit;
* what will happen when a revision is saved;
* how to add structured methods and samples without knowing the serialized representation.

Prioritize durable usability over implementation convenience.

Field-help model

Every important field must have contextual help through an accessible info hotspot or equivalent control.

Help must work through:

* hover;
* keyboard focus;
* click;
* tap or touch.

Do not rely on hover alone.

Use two help sources.

System field semantics

Editor help should come from a centralized, reusable field-definition registry.

It should explain the system meaning of fields such as:

* Valid from;
* Valid through;
* Sample date;
* Status;
* Result shape;
* Scope;
* Effective at;
* Period start;
* Period end;
* Unit;
* Dimensions;
* Method kind;
* Required inputs;
* Optional inputs;
* Comparison semantics;
* Confidence rules;
* Tolerance;
* Warnings.

The help should explain behavior, not merely restate the label.

Examples:

* Valid from is the earliest business date for which a definition or method applies. It is not the revision creation timestamp.
* Sample date dates an illustrative sample. It does not make that sample authoritative evidence.
* Result shape defines the structural form of an observation, such as quantity, state, event, narrative, or relationship.
* Effective at is the point in time when an event or state became applicable.
* Period start and Period end define the interval covered by a reported quantity or result.

Do not duplicate these strings throughout templates or JavaScript.

Concept-specific context

Browser and detail-page help should derive from the current concept revision and method records where appropriate.

Use:

* concept definition;
* comments;
* aliases;
* hints;
* method comments;
* warnings;
* sample descriptions;
* related concepts;
* validation guidance.

Do not hard-code concept-specific explanations into the browser.

Editing model

Routine editing must use typed, schema-aware controls.

Do not require raw JSON editing in the operator GUI.

The operator should edit:

* concept metadata;
* aliases;
* hints;
* tags;
* classifications;
* comments;
* status;
* validity dates;
* sample date;
* related concepts;
* warnings;
* methods;
* method inputs;
* units;
* dimensions;
* scope and period expectations;
* validation rules;
* confidence rules;
* comparison semantics;
* tolerance guidance;
* samples.

The system may continue to persist generic structured records behind the scenes.

The standard is:

Operators edit typed fields; the system produces structured records.

Raw JSON generation can remain a developer or Codex-assisted workflow outside normal GUI operation.

Repeated structures

Provide usable add, edit, and remove controls for repeated items.

Where meaningful, support reordering.

Examples include:

* aliases;
* hints;
* tags;
* warnings;
* methods;
* required inputs;
* optional inputs;
* units;
* dimensions;
* sample cases;
* validation conditions;
* confidence rules;
* related concepts.

Prevent or clearly report duplicates where duplicates are invalid or confusing.

Shape-aware editors

Method and sample forms should adapt to the selected method kind and result shape.

At minimum, support practical typed editing for:

* extracted quantity;
* deterministic derivation;
* categorical or state observation;
* event or milestone observation.

Hide irrelevant fields or place them in clearly labeled conditional sections.

Do not expose every possible field at once.

Sample editing

Provide distinct typed editing experiences for representative sample families.

Quantity sample

Support fields such as:

* period label, or period start and end;
* value;
* unit;
* scope;
* dimensions;
* comments or description.

Event sample

Support:

* effective date;
* event type;
* product scope;
* customer or other scope;
* comments or description.

State sample

Support:

* effective or as-of date;
* state value;
* scope;
* dimensions;
* comments or description.

The implementation does not need to define the final universal sample schema, but it must be extensible.

HAMR Shipments proof

Use the HAMR Shipments concept as a concrete usability proof.

The operator must be able to add and edit, through typed controls:

* a volume-shipments-started event;
* a units-shipped sample;
* a TB-shipped sample.

A representative result may be equivalent to:

[
  {
    "effective_at": "2024-06-28",
    "event_type": "volume-shipments-started",
    "product_scope": "example-HAMR-platform"
  },
  {
    "period": "example quarter",
    "value": 1000,
    "unit": "unit"
  },
  {
    "period": "example quarter",
    "value": 250000,
    "unit": "TB"
  }
]

The exact internal representation remains an implementation decision.

Prefer generic value plus unit semantics rather than unit-specific value field names.

Validation

Place validation close to the affected control.

Support:

* field-level errors;
* repeated-row errors;
* method-level errors;
* sample-level errors;
* page-level error summary;
* focus or navigation to invalid controls where practical.

Preserve entered values after validation failure.

Clearly distinguish:

* missing required values;
* invalid date intervals;
* duplicate identifiers or aliases;
* invalid method configuration;
* invalid deterministic inputs;
* incompatible units;
* malformed quantity, event, or state samples;
* optimistic revision conflicts;
* server or persistence failures.

Do not collapse all failures into a generic banner.

Revision semantics

The editor must clearly communicate that Save creates a new immutable revision.

Before saving, provide a preview or change summary showing:

* current revision;
* proposed status;
* changed metadata;
* methods added, removed, or modified;
* samples changed;
* validity changes;
* warnings;
* revision creation behavior.

Do not present the operation as editing history in place.

Unsaved changes

Detect dirty editor state.

At minimum:

* warn before navigation;
* warn before reload or close where supported;
* provide explicit Save and Cancel actions;
* clearly distinguish saved state from draft state.

Never silently discard operator work.

List, browser, and editor workflow

Establish a consistent admin workflow:

List/Search
→ Detail/Browser
→ Edit/Create Revision
→ Validate
→ Preview
→ Save New Revision

Standardize reusable patterns for:

* page context;
* primary and secondary actions;
* statuses;
* loading;
* empty states;
* success messages;
* errors;
* retiring or destructive actions;
* return navigation.

Treat these patterns as reusable components or conventions for future admin-console tabs.

Accessibility and touch behavior

The admin console should be practically usable through:

* keyboard navigation;
* visible focus indicators;
* properly labeled controls;
* accessible help controls;
* touch-friendly targets;
* non-hover help interaction;
* semantic association between fields and errors;
* reasonable behavior at narrower window sizes.

Formal certification is not required, but obvious accessibility regressions are unacceptable.

Architectural boundaries

Preserve the TASK-009 authority model.

The GUI must:

* use ConceptService and public catalog contracts;
* create revisions through the normal service path;
* preserve historical revisions;
* remain local-only by default;
* avoid direct persistence-file edits;
* avoid creating a parallel concept authority;
* avoid overfitting to the seeded sample concepts.

Keep the server and frontend dependency footprint modest.

Proof expectations

The review package should visibly prove:

* centralized field-help behavior;
* keyboard and click/touch help access;
* concept-record-sourced browser help;
* typed metadata editing;
* repeated-field controls;
* typed extracted and deterministic method editing;
* typed quantity, event, and state sample editing;
* HAMR Shipments TB sample addition;
* inline validation;
* page-level error summary;
* preservation of entered data after failure;
* revision preview;
* immutable revision save;
* unsaved-change protection;
* persistence after restart;
* reusable admin-console interaction patterns.

Product standard

The final result should feel like an operator tool, not an internal schema inspector.

An operator should not need to remember:

* storage structure;
* field names from Python contracts;
* serialized JSON shape;
* revision implementation details;
* which fields apply to which method type.

The interface should carry that knowledge.
