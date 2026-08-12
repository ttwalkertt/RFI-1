"""Strict, non-authoritative work-product contract for the TASK-075 QA gauge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

GAUGE_SCHEMA_VERSION = "task075.qa-gauge.v1"
DISPOSITIONS = ("supported", "defective", "indeterminate")
DEFECT_CLASSES = (
    "absence_overstatement",
    "aggregation_error",
    "ambiguous_reference_overresolved",
    "attribution_unsupported",
    "boundary_inclusion_error",
    "causal_overstatement",
    "chronology_basis_mismatch",
    "chronology_boundary_incorrect",
    "claim_strength_overstatement",
    "conflicting_evidence_omitted",
    "corpus_completeness_overstatement",
    "date_imputation",
    "denominator_error",
    "duplicate_counting",
    "entity_conflation",
    "evidence_mapping_incorrect",
    "evidence_mapping_missing",
    "false_absence",
    "insufficiency_miscalibrated",
    "internal_inconsistency",
    "numeric_mismatch",
    "provenance_authority_error",
    "qualification_omitted",
    "quote_context_distortion",
    "record_eligibility_error",
    "status_mischaracterized",
    "temporal_scope_mismatch",
    "timezone_conversion_error",
    "undefined_evaluation_criterion",
    "unit_mismatch",
    "unsupported_claim",
    "version_supersession_ignored",
)


@dataclass(frozen=True)
class GaugeFinding:
    """One material QA finding; it never becomes repository truth."""

    finding_id: str
    defect_class: str
    affected_claim: str
    finding: str
    evidence_locators: tuple[str, ...]


@dataclass(frozen=True)
class GaugeReview:
    """One independent whole-answer judgment."""

    schema_version: str
    evaluation_id: str
    disposition: str
    findings: tuple[GaugeFinding, ...]
    rationale: str


def gauge_output_schema(evaluation_id: str, allowed_locators: tuple[str, ...]) -> dict[str, Any]:
    """Build the exact structured-output schema for one isolated review."""
    if not evaluation_id:
        raise ValueError("evaluation_id must be non-empty")
    if not allowed_locators:
        raise ValueError("a QA case must expose at least one evidence locator")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "evaluation_id",
            "disposition",
            "findings",
            "rationale",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": GAUGE_SCHEMA_VERSION},
            "evaluation_id": {"type": "string", "const": evaluation_id},
            "disposition": {"type": "string", "enum": list(DISPOSITIONS)},
            "findings": {
                "type": "array",
                "maxItems": len(DEFECT_CLASSES),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "finding_id",
                        "defect_class",
                        "affected_claim",
                        "finding",
                        "evidence_locators",
                    ],
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "pattern": "^F[0-9]{3}$",
                        },
                        "defect_class": {
                            "type": "string",
                            "enum": list(DEFECT_CLASSES),
                        },
                        "affected_claim": {"type": "string", "minLength": 1},
                        "finding": {"type": "string", "minLength": 1},
                        "evidence_locators": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "string",
                                "enum": list(allowed_locators),
                            },
                        },
                    },
                },
            },
            "rationale": {"type": "string", "minLength": 1},
        },
    }


def parse_gauge_review(
    payload: dict[str, Any],
    *,
    evaluation_id: str,
    allowed_locators: tuple[str, ...],
) -> GaugeReview:
    """Validate semantics beyond JSON Schema and return an immutable review."""
    schema = gauge_output_schema(evaluation_id, allowed_locators)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda item: list(item.path),
    )
    if errors:
        detail = "; ".join(error.message for error in errors[:3])
        raise ValueError(f"invalid gauge output: {detail}")
    findings = tuple(
        GaugeFinding(
            finding_id=str(item["finding_id"]),
            defect_class=str(item["defect_class"]),
            affected_claim=str(item["affected_claim"]),
            finding=str(item["finding"]),
            evidence_locators=tuple(str(value) for value in item["evidence_locators"]),
        )
        for item in payload["findings"]
    )
    expected_ids = tuple(f"F{index:03d}" for index in range(1, len(findings) + 1))
    if tuple(item.finding_id for item in findings) != expected_ids:
        raise ValueError("finding IDs must be contiguous and ordered from F001")
    classes = tuple(item.defect_class for item in findings)
    if len(classes) != len(set(classes)):
        raise ValueError("one review may report each defect class at most once")
    if any(len(item.evidence_locators) != len(set(item.evidence_locators)) for item in findings):
        raise ValueError("one finding may report each evidence locator at most once")
    disposition = str(payload["disposition"])
    if disposition == "supported" and findings:
        raise ValueError("supported disposition cannot contain material findings")
    if disposition != "supported" and not findings:
        raise ValueError("non-supported disposition requires a material finding")
    return GaugeReview(
        schema_version=str(payload["schema_version"]),
        evaluation_id=str(payload["evaluation_id"]),
        disposition=disposition,
        findings=findings,
        rationale=str(payload["rationale"]),
    )
