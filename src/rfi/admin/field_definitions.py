"""Central operator-facing semantics for reusable admin-console fields."""

from __future__ import annotations

from typing import Final


FIELD_DEFINITIONS: Final[dict[str, str]] = {
    "concept_id": (
        "The stable machine identifier for this concept. It cannot change after the first "
        "revision is created."
    ),
    "display_name": (
        "The operator-facing name used in catalog lists, search results, and concept details."
    ),
    "definition": "The authoritative plain-language meaning of the concept for this revision.",
    "comments": (
        "Longer operating notes, boundaries, and interpretation guidance that travel with "
        "this revision."
    ),
    "aliases": (
        "Alternative names used for operator lookup and extraction. Aliases must be unique "
        "within the concept."
    ),
    "hints": (
        "Terms or phrases that help locate this concept in source material; they are guidance, "
        "not evidence."
    ),
    "tags": "Reusable labels for search and grouping. Tags do not change the concept's meaning.",
    "classifications": (
        "Named category/value pairs used to organize concepts without imposing a fixed ontology."
    ),
    "status": (
        "The operator-owned lifecycle state. Draft is not ready for normal use; active is "
        "usable; retired and superseded remain in immutable history."
    ),
    "valid_from": (
        "The earliest business date for which a definition or method applies. It is not the "
        "revision creation timestamp."
    ),
    "valid_through": (
        "The final business date for which the definition or method applies. Leave empty for "
        "an open-ended interval."
    ),
    "sample_date": (
        "The date attached to illustrative samples. It does not make a sample authoritative "
        "evidence."
    ),
    "related_concept_ids": (
        "Stable identifiers of concepts that help an operator navigate or interpret this "
        "definition. They do not create derivation inputs."
    ),
    "warnings": (
        "Cautions that must remain visible when operators or downstream systems use this "
        "definition or method."
    ),
    "method_id": (
        "A stable identifier for one admissible observation or derivation method within this "
        "concept revision."
    ),
    "method_kind": (
        "How a result is produced. Extracted reads evidence, deterministic derives from inputs, "
        "state records a condition, and event records a milestone."
    ),
    "result_shape": (
        "The structural form of an observation, such as quantity, state, event, narrative, or "
        "relationship."
    ),
    "required_inputs": (
        "Named input roles that a deterministic method must receive. Each role maps to a "
        "concept dependency."
    ),
    "optional_inputs": (
        "Input roles that may enrich or qualify a method but are not required for it to run."
    ),
    "units": (
        "Allowed measurement labels for results. Exact labels are currently compared; "
        "automatic conversion is not performed."
    ),
    "dimensions": (
        "Context axes that must remain with a result, such as product, geography, customer, "
        "or entity."
    ),
    "scope": (
        "The business boundary to which a result applies, such as consolidated, a product "
        "family, or a customer."
    ),
    "period_expectation": (
        "Guidance about the reporting interval a method expects, such as quarter, year, "
        "point-in-time, or not applicable."
    ),
    "effective_at": "The point in time when an event or state became applicable.",
    "period_start": "The first date in the interval covered by a reported quantity or result.",
    "period_end": "The last date in the interval covered by a reported quantity or result.",
    "validation_conditions": (
        "Checks that a produced result should satisfy before it is accepted for downstream use."
    ),
    "confidence_rules": (
        "Guidance for assigning or interpreting confidence without turning confidence into "
        "source authority."
    ),
    "comparison_semantics": (
        "How observations from this method may be compared while keeping each result distinct."
    ),
    "tolerance": (
        "Reconciliation guidance for deciding whether differences are acceptable. It does not "
        "merge or overwrite observations."
    ),
    "samples": (
        "Illustrative, typed examples that explain expected structure. Samples are not "
        "authoritative observations or source evidence."
    ),
    "sample_family": (
        "The sample structure to edit. Quantity uses value and unit, event uses an effective "
        "date and event type, and state uses an as-of date and state value."
    ),
    "firm_id": (
        "The stable repository identity for a target firm. Future source, knowledge, and "
        "workspace records may reference it; it cannot change after creation."
    ),
    "canonical_name": (
        "The concise operator-facing name used for browsing and firm-centered workflows."
    ),
    "legal_name": (
        "The formal legal issuer or corporate name when known. It may differ from the "
        "canonical consulting name."
    ),
    "firm_aliases": (
        "Alternative company, issuer, or commonly used names that help recognize the target. "
        "They are hints, not extracted entity assertions."
    ),
    "identifiers": (
        "Typed recognition keys such as ticker, CIK, or LEI. Kind, optional market, and value "
        "together must not conflict with another current firm."
    ),
    "domains": (
        "Normalized domain hints used to recognize official web properties. A domain is unique "
        "to one current firm in this catalog."
    ),
    "headquarters": "An operator-maintained location hint; it is not source-grounded evidence.",
    "jurisdiction": (
        "The legal or incorporation jurisdiction useful for distinguishing corporate identities."
    ),
    "sector": "A broad, operator-owned classification used for firm browsing and filtering.",
    "industry": "A narrower, operator-owned classification used for browsing and filtering.",
    "technology_focus": (
        "Technologies relevant to consulting scope and source discovery. These labels do not "
        "assert product ownership or extracted facts."
    ),
    "source_hints": (
        "Operator guidance for locating likely sources, such as investor-relations sites or "
        "regulatory identifiers. Hints are not acquired evidence."
    ),
    "firm_notes": (
        "Operating context and identity cautions maintained by the catalog operator. Extracted "
        "facts and arbitrary research findings belong in their own authorities."
    ),
}


def field_definitions() -> dict[str, str]:
    """Return a copy so adapters cannot mutate the shared registry."""
    return dict(FIELD_DEFINITIONS)
