# Admin Console Schema-Aware Editor

TASK-010 turns the Concept Catalog into the reference interaction model for future RFI-1 admin
tabs. The normal workflow is List/Search → Detail/Browser → Edit/Create Revision → Validate →
Preview → Save New Revision.

## Operator interaction model

Every significant field has an info control backed by `rfi.admin.field_definitions`. Help opens on
hover or keyboard focus and can be pinned with click or touch. The detail browser separately builds
concept guidance from the selected revision's definition, comments, aliases, hints, method comments,
warnings, and sample records. System semantics are never copied into individual templates.

The revision editor provides typed controls for concept metadata, classifications, repeated values,
methods, deterministic inputs, units, dimensions, scope/period expectations, validation and
confidence rules, comparison semantics, tolerance, and warnings. Repeated records can be added,
removed, and reordered. Method-specific sections appear for extracted, deterministic, state, and
event families.

Quantity, event, and state samples have distinct typed forms. Older generic sample records remain
preserved as inspectable legacy structured samples until an operator removes or replaces them. No
raw JSON editor is presented.

## Validation and revision safety

Client validation places errors by the affected control and builds a focusable page summary. It
distinguishes required values, identifiers and duplicates, date intervals, deterministic inputs,
quantity/event/state shapes, and quantity units. The service performs the authoritative validation
before publication. Server responses classify optimistic conflicts, method failures, unit failures,
and persistence failures so the draft can remain open with focused recovery guidance.

Dirty state is visible. Cancel, Escape, reload, and close paths warn before discarding work. Preview
shows the current and proposed revision, status, metadata/method/sample/validity changes, warnings,
and the immutable append behavior. Save always uses `ConceptService.revise` or `create`; historical
revisions remain inspectable.

## Verification

Run:

```sh
make task010-proof
PYTHONPATH=src .venv/bin/python -m unittest tests.test_task010 -v
```

The HAMR Shipments proof appends a revision containing a volume-shipments-started event, a
units-shipped quantity, and a 250,000 TB-shipped quantity, then reopens the catalog to prove
persistence and immutable history.

## Limitations

- Registered extension method and result families are preserved but do not yet receive bespoke
  controls.
- Historical generic sample shapes are preserved, not edited field-by-field.
- Unit labels are exact strings; there is no conversion or dimensional-analysis service.
- Browser validation improves usability but does not replace service validation.
- The local console remains unauthenticated and single-user.

## Architectural Status Summary

- **Concept catalog — Complete architecture; provisional domain maturity.** Immutable revision
  authority and generic contracts remain unchanged.
- **Admin console shell — Complete for local single-user use.** Search, detail, consistent actions,
  status, empty/error/success states, and return navigation establish reusable conventions.
- **Schema-aware concept editor — Complete for common families.** Metadata, repeated structures,
  extracted and deterministic methods, and quantity/event/state samples are typed; extension-family
  projections remain future work.
- **Field and concept help — Complete.** Central system semantics and revision-derived business
  context are separate and accessible by pointer, keyboard, and touch interaction.
- **Revision safety — Complete for local optimistic editing.** Dirty-state protection, validation,
  preview, append-only save, conflict reporting, and restart persistence are proven.
- **Accessibility — Usable with limitations.** Labels, focus indicators, semantic errors, keyboard
  interaction, touch targets, and narrow layouts are implemented; formal certification is absent.
- **Next architectural milestone — operator use and the next authoritative task ticket.** Future
  admin tabs should reuse these console conventions; extension-family editors and production
  administration should be prioritized from real operator evidence rather than inferred here.
