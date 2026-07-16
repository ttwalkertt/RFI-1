"""Small generic sample catalog used only as TASK-009 architectural proof."""

from __future__ import annotations

from rfi.concepts.contracts import (
    ConceptDraft,
    ConceptStatus,
    MethodKind,
    ObservationMethod,
)


def extracted(
    method_id: str,
    name: str,
    shape: str,
    units: tuple[str, ...] = (),
    hints: tuple[str, ...] = (),
) -> ObservationMethod:
    """Return one generic extracted observation method."""
    return ObservationMethod(
        method_id=method_id,
        kind=MethodKind.EXTRACTED,
        name=name,
        result_shape=shape,
        units=units,
        extraction_hints=hints,
        comments="Extracted observations retain independent source provenance.",
    )


def sample_concepts() -> tuple[ConceptDraft, ...]:
    """Return diverse proofs, not a complete ontology or financial taxonomy."""
    revenue = ConceptDraft(
        concept_id="revenue",
        display_name="Revenue",
        definition="Economic inflow recognized for a defined entity, scope, and period.",
        comments="Proof case for extracted quantities; accounting policy remains contextual.",
        aliases=("sales", "net revenue"),
        hints=("consolidated statements of operations", "revenue table"),
        status=ConceptStatus.ACTIVE,
        tags=("financial", "quantity", "proof"),
        classifications={"proof_family": "financial"},
        valid_from="2020-01-01",
        sample_date="2024-06-28",
        methods=(
            extracted(
                "reported-revenue",
                "Reported revenue",
                "quantity",
                ("USD",),
                ("Revenue", "Net sales"),
            ),
        ),
        samples=(
            {"value": 1000, "unit": "USD", "period": "example annual period"},
        ),
    )
    gross_profit = ConceptDraft(
        concept_id="gross-profit",
        display_name="Gross Profit",
        definition="Revenue less cost attributable to producing the recognized revenue.",
        status=ConceptStatus.ACTIVE,
        tags=("financial", "quantity", "calculation-input", "proof"),
        valid_from="2020-01-01",
        methods=(
            extracted(
                "reported-gross-profit",
                "Reported gross profit",
                "quantity",
                ("USD",),
            ),
        ),
    )
    cost = ConceptDraft(
        concept_id="cost-of-revenue",
        display_name="Cost of Revenue",
        definition="Cost attributed to recognized revenue for a defined period and scope.",
        aliases=("cost of sales",),
        status=ConceptStatus.ACTIVE,
        tags=("financial", "quantity", "calculation-input", "proof"),
        valid_from="2020-01-01",
        methods=(
            extracted(
                "reported-cost-of-revenue",
                "Reported cost of revenue",
                "quantity",
                ("USD",),
            ),
        ),
    )
    gross_margin = ConceptDraft(
        concept_id="gross-margin",
        display_name="Gross Margin",
        definition="Gross profit expressed relative to revenue for matching scope and period.",
        comments=(
            "Reported and calculated observations coexist. Comparisons are visible and never "
            "silently reconciled."
        ),
        aliases=("gross margin percentage", "GM"),
        hints=("gross margin", "gross profit as a percentage of revenue"),
        status=ConceptStatus.ACTIVE,
        tags=("financial", "ratio", "deterministic", "proof"),
        classifications={"proof_family": "financial"},
        valid_from="2020-01-01",
        sample_date="2024-06-28",
        related_concept_ids=("revenue", "gross-profit", "cost-of-revenue"),
        methods=(
            extracted(
                "reported-gross-margin",
                "Reported gross margin",
                "ratio",
                ("percent",),
                ("gross margin",),
            ),
            ObservationMethod(
                method_id="gross-profit-over-revenue",
                kind=MethodKind.DETERMINISTIC,
                name="Gross profit divided by revenue",
                result_shape="ratio",
                required_inputs=("gross_profit", "revenue"),
                units=("percent",),
                period_expectation="matching period",
                scope_expectation="matching scope and dimensions",
                configuration={
                    "operation": "percentage",
                    "output_unit": "percent",
                    "inputs": [
                        {"role": "gross_profit", "concept_id": "gross-profit", "unit": "USD"},
                        {"role": "revenue", "concept_id": "revenue", "unit": "USD"},
                    ],
                },
                validation_conditions=("revenue must be nonzero",),
                comparison_semantics="Compare independently with reported ratio.",
                tolerance={"absolute": 0.1, "unit": "percentage-point"},
            ),
            ObservationMethod(
                method_id="revenue-less-cost-over-revenue",
                kind=MethodKind.DETERMINISTIC,
                name="Revenue less cost of revenue, divided by revenue",
                result_shape="ratio",
                required_inputs=("revenue", "cost_of_revenue"),
                units=("percent",),
                period_expectation="matching period",
                scope_expectation="matching scope and dimensions",
                configuration={
                    "operation": "margin-from-cost",
                    "output_unit": "percent",
                    "inputs": [
                        {"role": "revenue", "concept_id": "revenue", "unit": "USD"},
                        {
                            "role": "cost_of_revenue",
                            "concept_id": "cost-of-revenue",
                            "unit": "USD",
                        },
                    ],
                },
                validation_conditions=("revenue must be nonzero",),
                comparison_semantics="Compare independently with other margin observations.",
                tolerance={"absolute": 0.1, "unit": "percentage-point"},
            ),
        ),
        samples=(
            {
                "reported_percent": 40.1,
                "gross_profit": 400,
                "revenue": 1000,
                "cost_of_revenue": 600,
            },
        ),
    )
    qualification = ConceptDraft(
        concept_id="hamr-qualification",
        display_name="HAMR Qualification",
        definition=(
            "Qualification state or milestone for heat-assisted magnetic recording within an "
            "explicit customer, product, program, and time context."
        ),
        comments="State values must retain scope; this concept is not a bare Boolean.",
        aliases=("HAMR customer qualification", "HAMR qualified"),
        hints=("qualification", "qualified", "customer acceptance"),
        status=ConceptStatus.ACTIVE,
        tags=("technology", "stateful", "milestone", "proof"),
        classifications={"proof_family": "operational"},
        valid_from="2020-01-01",
        sample_date="2024-01-24",
        methods=(
            ObservationMethod(
                method_id="qualification-state",
                kind=MethodKind.STATE,
                name="Scoped qualification state",
                result_shape="state",
                configuration={
                    "allowed_states": [
                        "not-started",
                        "in-progress",
                        "qualified",
                        "revoked",
                        "unknown",
                    ],
                    "required_context": ["customer_scope", "product_scope", "as_of"],
                },
                extraction_hints=("qualified by", "qualification testing"),
                dimensions=("customer_scope", "product_scope", "program_scope"),
                warnings=("Do not infer all-customer qualification from one scoped assertion.",),
            ),
        ),
        samples=(
            {
                "state": "qualified",
                "customer_scope": "example-customer",
                "product_scope": "example-product",
                "as_of": "2024-01-24",
            },
        ),
    )
    shipments = ConceptDraft(
        concept_id="hamr-shipments",
        display_name="HAMR Shipments",
        definition=(
            "Shipment activity or milestone for HAMR products, retaining the reported shape, "
            "scope, quantity semantics, and time context."
        ),
        comments="Multiple event, quantity, and narrative shapes may coexist.",
        aliases=("HAMR shipping", "HAMR volume shipments"),
        hints=("shipments started", "volume production", "units shipped"),
        status=ConceptStatus.ACTIVE,
        tags=("technology", "event", "multi-shaped", "proof"),
        classifications={"proof_family": "operational"},
        valid_from="2020-01-01",
        sample_date="2024-06-28",
        methods=(
            ObservationMethod(
                method_id="shipment-milestone",
                kind=MethodKind.EVENT,
                name="Shipment milestone event",
                result_shape="event",
                configuration={
                    "event_types": ["shipments-started", "volume-shipments-started"]
                },
                dimensions=("customer_scope", "product_scope"),
            ),
            extracted("units-shipped", "Units shipped", "quantity", ("unit",)),
            extracted("capacity-shipped", "Capacity shipped", "quantity", ("exabyte",)),
            extracted("shipment-assertion", "Narrative shipment assertion", "narrative"),
        ),
        samples=(
            {
                "event_type": "volume-shipments-started",
                "effective_at": "2024-06-28",
                "product_scope": "example-HAMR-platform",
            },
            {"units": 1000, "unit": "unit", "period": "example quarter"},
        ),
    )
    return revenue, gross_profit, cost, gross_margin, qualification, shipments
