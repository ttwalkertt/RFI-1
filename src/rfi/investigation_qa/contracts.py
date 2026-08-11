"""Structured, non-authoritative QA and bounded-repair work products."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "task074.investigation-qa.v1"
CASE_ID_PATTERN = r"^[a-z][a-z0-9_-]{1,63}$"
RFI_REFERENCE_PATTERN = r"^rfi://[^\s]+$"


class Severity(StrEnum):
    """Materiality of an answer defect."""

    MATERIAL = "material"
    SIGNIFICANT = "significant"
    MINOR = "minor"


class DefectClass(StrEnum):
    """Ticket-authorized QA defect taxonomy."""

    UNSUPPORTED_CLAIM = "unsupported_claim"
    INCORRECT_CHRONOLOGY = "incorrect_chronology"
    EVIDENCE_MAPPING_MISSING = "evidence_mapping_missing"
    EVIDENCE_MAPPING_INCORRECT = "evidence_mapping_incorrect"
    SCOPE_OVERSTATEMENT = "scope_overstatement"
    QUALIFICATION_MISSING = "qualification_missing"
    INSUFFICIENCY_MISCALIBRATED = "insufficiency_miscalibrated"
    ABSENCE_OVERSTATEMENT = "absence_overstatement"
    REPOSITORY_LIMITATION_OMITTED = "repository_limitation_omitted"
    INTERNAL_INCONSISTENCY = "internal_inconsistency"
    MATERIAL_AMBIGUITY = "material_ambiguity"


class QADisposition(StrEnum):
    """Per-case reviewer disposition."""

    PASS = "pass"
    REPAIR_REQUIRED = "repair_required"
    INSUFFICIENT_FOR_REVIEW = "insufficient_for_review"


class ReviewConfidence(StrEnum):
    """Reviewer confidence in one finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResolutionState(StrEnum):
    """Terminal QA #2 disposition of one QA #1 finding."""

    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    UNRESOLVED = "unresolved"
    SUPERSEDED = "superseded"


class Attribution(StrEnum):
    """Diagnostic attribution permitted by TASK-074."""

    QA_REVIEWER_FAILURE = "qa_reviewer_failure"
    MCP_ACCESS_FAILURE = "mcp_access_failure"
    INVESTIGATOR_REPAIR_FAILURE = "investigator_repair_failure"
    REPAIR_INDUCED_REGRESSION = "repair_induced_regression"
    REPOSITORY_AUTHORITY_LIMITATION = "repository_authority_limitation"
    UNRESOLVED_BOUNDED_REPAIR = "unresolved_bounded_repair"


@dataclass(frozen=True)
class EvidenceReference:
    """Stable RFI evidence or repository-fact reference used by a finding."""

    uri: str
    description: str


@dataclass(frozen=True)
class QAFinding:
    """One bounded, evidence-grounded instruction from an independent reviewer."""

    finding_id: str
    case_id: str
    severity: Severity
    defect_class: DefectClass
    affected_claim: str
    defect: str
    supporting_evidence: tuple[EvidenceReference, ...]
    conflicting_or_missing_evidence: tuple[EvidenceReference, ...]
    why_it_matters: str
    repair_instruction: str
    confidence: ReviewConfidence
    additional_investigation_required: bool


@dataclass(frozen=True)
class QAReview:
    """Independent first review of one submitted answer."""

    schema_version: str
    case_id: str
    disposition: QADisposition
    summary: str
    findings: tuple[QAFinding, ...]


@dataclass(frozen=True)
class RepairFindingAction:
    """What the repairer attempted for one QA #1 finding."""

    finding_id: str
    action: str
    evidence_references: tuple[EvidenceReference, ...]


@dataclass(frozen=True)
class UnresolvedRepairItem:
    """A finding the single bounded repair could not fully resolve."""

    finding_id: str
    limitation: str
    limitation_kind: str
    preserved_in_answer: bool


@dataclass(frozen=True)
class RepairResult:
    """One repaired submission plus explicit unresolved work."""

    schema_version: str
    case_id: str
    repaired_answer: str
    finding_actions: tuple[RepairFindingAction, ...]
    unresolved_items: tuple[UnresolvedRepairItem, ...]
    repair_summary: str


@dataclass(frozen=True)
class FindingResolution:
    """Fresh QA #2 disposition for one QA #1 finding."""

    finding_id: str
    state: ResolutionState
    explanation: str
    evidence_references: tuple[EvidenceReference, ...]
    attribution: Attribution | None


@dataclass(frozen=True)
class QA2Review:
    """Terminal fresh review after the only permitted repair opportunity."""

    schema_version: str
    case_id: str
    disposition: QADisposition
    summary: str
    resolutions: tuple[FindingResolution, ...]
    new_findings: tuple[QAFinding, ...]
    unresolved_item_assessment: tuple[str, ...]


def _nonempty_string() -> dict[str, Any]:
    return {"type": "string", "minLength": 1}


def _evidence_reference_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["uri", "description"],
        "properties": {
            "uri": {"type": "string", "pattern": RFI_REFERENCE_PATTERN},
            "description": _nonempty_string(),
        },
    }


def _finding_schema(case_id: str, stage: str) -> dict[str, Any]:
    escaped = re.escape(case_id.upper())
    finding_pattern = rf"^TASK074-{escaped}-{stage}-F[0-9]{{3}}$"
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "finding_id",
            "case_id",
            "severity",
            "defect_class",
            "affected_claim",
            "defect",
            "supporting_evidence",
            "conflicting_or_missing_evidence",
            "why_it_matters",
            "repair_instruction",
            "confidence",
            "additional_investigation_required",
        ],
        "properties": {
            "finding_id": {"type": "string", "pattern": finding_pattern},
            "case_id": {"type": "string", "const": case_id},
            "severity": {
                "type": "string",
                "enum": [item.value for item in Severity],
            },
            "defect_class": {
                "type": "string",
                "enum": [item.value for item in DefectClass],
            },
            "affected_claim": _nonempty_string(),
            "defect": _nonempty_string(),
            "supporting_evidence": {
                "type": "array",
                "minItems": 1,
                "items": _evidence_reference_schema(),
            },
            "conflicting_or_missing_evidence": {
                "type": "array",
                "items": _evidence_reference_schema(),
            },
            "why_it_matters": _nonempty_string(),
            "repair_instruction": _nonempty_string(),
            "confidence": {
                "type": "string",
                "enum": [item.value for item in ReviewConfidence],
            },
            "additional_investigation_required": {"type": "boolean"},
        },
    }


def qa1_output_schema(case_id: str) -> dict[str, Any]:
    """Return the strict structured-output schema for QA #1."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "case_id", "disposition", "summary", "findings"],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "case_id": {"type": "string", "const": case_id},
            "disposition": {
                "type": "string",
                "enum": [item.value for item in QADisposition],
            },
            "summary": _nonempty_string(),
            "findings": {
                "type": "array",
                "items": _finding_schema(case_id, "Q1"),
            },
        },
    }


def repair_output_schema(case_id: str, finding_ids: tuple[str, ...]) -> dict[str, Any]:
    """Return the strict structured-output schema for the only repair cycle."""
    identifiers = list(finding_ids)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "case_id",
            "repaired_answer",
            "finding_actions",
            "unresolved_items",
            "repair_summary",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "case_id": {"type": "string", "const": case_id},
            "repaired_answer": _nonempty_string(),
            "finding_actions": {
                "type": "array",
                "minItems": len(identifiers),
                "maxItems": len(identifiers),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["finding_id", "action", "evidence_references"],
                    "properties": {
                        "finding_id": {"type": "string", "enum": identifiers},
                        "action": _nonempty_string(),
                        "evidence_references": {
                            "type": "array",
                            "items": _evidence_reference_schema(),
                        },
                    },
                },
            },
            "unresolved_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "finding_id",
                        "limitation",
                        "limitation_kind",
                        "preserved_in_answer",
                    ],
                    "properties": {
                        "finding_id": {"type": "string", "enum": identifiers},
                        "limitation": _nonempty_string(),
                        "limitation_kind": {
                            "type": "string",
                            "enum": [
                                "evidence_or_access_limitation",
                                "repository_authority_limitation",
                                "repairer_inability",
                            ]
                        },
                        "preserved_in_answer": {"type": "boolean"},
                    },
                },
            },
            "repair_summary": _nonempty_string(),
        },
    }


def qa2_output_schema(case_id: str, finding_ids: tuple[str, ...]) -> dict[str, Any]:
    """Return the strict structured-output schema for terminal QA #2."""
    identifiers = list(finding_ids)
    resolution_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "finding_id",
            "state",
            "explanation",
            "evidence_references",
            "attribution",
        ],
        "properties": {
            "finding_id": (
                {"type": "string", "enum": identifiers}
                if identifiers
                else {"type": "string"}
            ),
            "state": {
                "type": "string",
                "enum": [item.value for item in ResolutionState],
            },
            "explanation": _nonempty_string(),
            "evidence_references": {
                "type": "array",
                "items": _evidence_reference_schema(),
            },
            "attribution": {
                "anyOf": [
                    {
                        "type": "string",
                        "enum": [item.value for item in Attribution],
                    },
                    {"type": "null"},
                ]
            },
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "case_id",
            "disposition",
            "summary",
            "resolutions",
            "new_findings",
            "unresolved_item_assessment",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "case_id": {"type": "string", "const": case_id},
            "disposition": {
                "type": "string",
                "enum": [item.value for item in QADisposition],
            },
            "summary": _nonempty_string(),
            "resolutions": {
                "type": "array",
                "minItems": len(identifiers),
                "maxItems": len(identifiers),
                "items": resolution_schema,
            },
            "new_findings": {
                "type": "array",
                "items": _finding_schema(case_id, "Q2"),
            },
            "unresolved_item_assessment": {
                "type": "array",
                "items": _nonempty_string(),
            },
        },
    }


def _validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda item: list(item.path),
    )
    if errors:
        locations = [
            f"{'/'.join(str(part) for part in item.path) or '<root>'}: {item.message}"
            for item in errors
        ]
        raise ValueError("structured output failed validation: " + "; ".join(locations))


def _reference(payload: dict[str, Any]) -> EvidenceReference:
    return EvidenceReference(str(payload["uri"]), str(payload["description"]))


def _finding(payload: dict[str, Any]) -> QAFinding:
    return QAFinding(
        str(payload["finding_id"]),
        str(payload["case_id"]),
        Severity(str(payload["severity"])),
        DefectClass(str(payload["defect_class"])),
        str(payload["affected_claim"]),
        str(payload["defect"]),
        tuple(_reference(item) for item in payload["supporting_evidence"]),
        tuple(_reference(item) for item in payload["conflicting_or_missing_evidence"]),
        str(payload["why_it_matters"]),
        str(payload["repair_instruction"]),
        ReviewConfidence(str(payload["confidence"])),
        bool(payload["additional_investigation_required"]),
    )


def _expected_finding_ids(case_id: str, stage: str, count: int) -> list[str]:
    return [
        f"TASK074-{case_id.upper()}-{stage}-F{index:03d}"
        for index in range(1, count + 1)
    ]


def parse_qa1(payload: dict[str, Any], case_id: str) -> QAReview:
    """Validate and freeze a QA #1 model result."""
    _validate(payload, qa1_output_schema(case_id))
    review = QAReview(
        str(payload["schema_version"]),
        str(payload["case_id"]),
        QADisposition(str(payload["disposition"])),
        str(payload["summary"]),
        tuple(_finding(item) for item in payload["findings"]),
    )
    identifiers = [item.finding_id for item in review.findings]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("QA #1 finding IDs must be unique")
    if identifiers != _expected_finding_ids(case_id, "Q1", len(identifiers)):
        raise ValueError("QA #1 finding IDs must be sequential in output order")
    if review.disposition is QADisposition.PASS and review.findings:
        raise ValueError("a passing QA #1 review cannot include repair findings")
    if review.disposition is QADisposition.REPAIR_REQUIRED and not review.findings:
        raise ValueError("repair_required must include at least one finding")
    return review


def parse_repair(
    payload: dict[str, Any], case_id: str, finding_ids: tuple[str, ...]
) -> RepairResult:
    """Validate and freeze the only repair result."""
    _validate(payload, repair_output_schema(case_id, finding_ids))
    result = RepairResult(
        str(payload["schema_version"]),
        str(payload["case_id"]),
        str(payload["repaired_answer"]),
        tuple(
            RepairFindingAction(
                str(item["finding_id"]),
                str(item["action"]),
                tuple(_reference(reference) for reference in item["evidence_references"]),
            )
            for item in payload["finding_actions"]
        ),
        tuple(
            UnresolvedRepairItem(
                str(item["finding_id"]),
                str(item["limitation"]),
                str(item["limitation_kind"]),
                bool(item["preserved_in_answer"]),
            )
            for item in payload["unresolved_items"]
        ),
        str(payload["repair_summary"]),
    )
    action_ids = [item.finding_id for item in result.finding_actions]
    if sorted(action_ids) != sorted(finding_ids) or len(action_ids) != len(
        set(action_ids)
    ):
        raise ValueError("repair must record exactly one action for every QA #1 finding")
    unresolved_ids = [item.finding_id for item in result.unresolved_items]
    if len(unresolved_ids) != len(set(unresolved_ids)):
        raise ValueError("repair unresolved finding IDs must be unique")
    if any(not item.preserved_in_answer for item in result.unresolved_items):
        raise ValueError("every unresolved repair limitation must be preserved in the answer")
    return result


def parse_qa2(
    payload: dict[str, Any], case_id: str, finding_ids: tuple[str, ...]
) -> QA2Review:
    """Validate and freeze terminal QA #2 output."""
    _validate(payload, qa2_output_schema(case_id, finding_ids))
    result = QA2Review(
        str(payload["schema_version"]),
        str(payload["case_id"]),
        QADisposition(str(payload["disposition"])),
        str(payload["summary"]),
        tuple(
            FindingResolution(
                str(item["finding_id"]),
                ResolutionState(str(item["state"])),
                str(item["explanation"]),
                tuple(_reference(reference) for reference in item["evidence_references"]),
                Attribution(str(item["attribution"])) if item["attribution"] else None,
            )
            for item in payload["resolutions"]
        ),
        tuple(_finding(item) for item in payload["new_findings"]),
        tuple(str(item) for item in payload["unresolved_item_assessment"]),
    )
    resolution_ids = [item.finding_id for item in result.resolutions]
    if sorted(resolution_ids) != sorted(finding_ids) or len(resolution_ids) != len(
        set(resolution_ids)
    ):
        raise ValueError("QA #2 must resolve every QA #1 finding exactly once")
    new_ids = [item.finding_id for item in result.new_findings]
    if len(new_ids) != len(set(new_ids)):
        raise ValueError("QA #2 new finding IDs must be unique")
    if new_ids != _expected_finding_ids(case_id, "Q2", len(new_ids)):
        raise ValueError("QA #2 new finding IDs must be sequential in output order")
    if result.disposition is QADisposition.PASS and (
        result.new_findings
        or any(
            item.state
            not in {ResolutionState.RESOLVED, ResolutionState.SUPERSEDED}
            for item in result.resolutions
        )
    ):
        raise ValueError("a passing QA #2 review cannot retain unresolved defects")
    return result


def to_dict(value: Any) -> dict[str, Any]:
    """Serialize a frozen contract with string enum values."""
    return asdict(value)
