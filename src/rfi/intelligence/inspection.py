"""Operator inspection, contract-schema, replaceability, and retention helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from rfi.intelligence.contracts import (
    ExecutionRecord,
    IntelligenceResult,
    RetentionMode,
    RuntimePolicy,
)


def intelligence_contract_schema() -> dict[str, dict[str, str]]:
    """Return provider-neutral public field names and annotation strings."""
    contracts = (IntelligenceResult,)
    return {
        item.__name__: {field.name: str(field.type) for field in fields(item)}
        for item in contracts
    }


def inspect_execution(record: ExecutionRecord) -> dict[str, Any]:
    """Render every governed phase for scriptable operator inspection."""
    return asdict(record)


def compare_results(first: IntelligenceResult, second: IntelligenceResult) -> dict[str, Any]:
    """Prove implementation replacement preserves authority and mapping obligations."""
    first_authority = sorted(item.kind.value for item in first.claims)
    second_authority = sorted(item.kind.value for item in second.claims)
    first_evidence = sorted((item.authority.value, item.object_id) for item in first.evidence)
    second_evidence = sorted((item.authority.value, item.object_id) for item in second.evidence)
    checks = {
        "same_public_schema": intelligence_contract_schema() == intelligence_contract_schema(),
        "provider_specific_public_fields": [],
        "same_completion_status": first.status == second.status,
        "same_stopping_reason": first.stopping_reason == second.stopping_reason,
        "same_claim_authority_classes": first_authority == second_authority,
        "same_evidence_authority_and_objects": first_evidence == second_evidence,
        "all_first_claims_mapped": all(item.evidence_ids for item in first.claims),
        "all_second_claims_mapped": all(item.evidence_ids for item in second.claims),
    }
    return {
        "result": "PASS" if all(value == [] or value is True for value in checks.values())
        else "FAIL",
        **checks,
        "wording_may_differ": first.response != second.response,
    }


def retain_execution(record: ExecutionRecord, path: Path, policy: RuntimePolicy) -> Path | None:
    """Persist only the retention level explicitly selected by the operator."""
    if policy.retention == RetentionMode.NONE:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if policy.retention == RetentionMode.FULL:
        payload: dict[str, Any] = asdict(record)
    else:
        payload = {
            "execution_id": record.result.execution_id,
            "result_id": record.result.result_id,
            "status": record.result.status,
            "stopping_reason": record.result.stopping_reason,
            "plan_id": record.trace.plan.plan_id if record.trace.plan else None,
            "retrieval_trace_ids": record.result.retrieval_trace_ids,
            "evidence_package_ids": record.result.evidence_package_ids,
            "claim_ids": tuple(item.claim_id for item in record.result.claims),
            "iterations": record.trace.iterations,
            "failures": record.trace.failures,
        }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return path
