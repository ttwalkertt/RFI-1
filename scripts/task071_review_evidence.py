#!/usr/bin/env python3
"""Validate TASK-071 retained-corpus traces and emit bounded review evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.acquisition import AcquisitionRepository
from rfi.artifacts import ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.research import ResearchReportWriter, TranscriptKnowledgeAccess, TranscriptScope
from task071_emit_reports import scope_from_run
from rfi.source_profiles import load_canonical_template

ROOT = Path(__file__).resolve().parents[1]
TRACE_CASES = {
    "sentiment": ("supported", "partial"),
    "demand": ("supported", "partial"),
    "technology": ("supported", "partial"),
    "chronology": ("supported", "partial"),
    "insufficient": ("insufficient",),
}


def imports(path: Path) -> tuple[str, ...]:
    """Return normalized imports for an architectural dependency check."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return tuple(sorted(set(values)))


def trace_summary(
    path: Path,
    report_path: Path,
    expected_statuses: tuple[str, ...],
    repository_snapshot: str,
    artifacts: ArtifactQueryService,
) -> dict[str, Any]:
    """Validate one complete trace against public retained artifact bytes."""
    value = json.loads(path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if value["repository_snapshot"] != repository_snapshot:
        raise ValueError(f"trace uses a different repository snapshot: {path.name}")
    if not str(value["runtime_identity"]).startswith("openai:"):
        raise ValueError(f"trace does not exercise the live replaceable adapter: {path.name}")
    result = value["result"]
    if result["status"] not in expected_statuses:
        raise ValueError(
            f"unexpected evidence status for {path.name}: {result['status']}"
        )
    trace = value["trace"]
    calls = [
        item for item in trace
        if item["action"] in {"tool_call", "recovery_tool_call"}
    ]
    if not calls or calls[0]["detail"]["name"] != "describe_corpus":
        raise ValueError(f"trace did not orient before investigation: {path.name}")
    names = [item["detail"]["name"] for item in calls]
    if "search_transcripts" not in names:
        raise ValueError(f"trace omitted search: {path.name}")
    actions = [item["action"] for item in trace]
    if actions[-2:] != ["investigation_closed", "consistency_pass"]:
        raise ValueError(f"trace omitted separate closed-record evaluation: {path.name}")
    if trace[-1]["detail"].get("retrieval_performed") is not False:
        raise ValueError(f"consistency pass did not attest zero retrieval: {path.name}")
    search_results = [
        item["detail"]["output"]
        for item in trace
        if item["action"] in {"tool_result", "recovery_tool_result"}
        and item["detail"]["name"] == "search_transcripts"
        and "output" in item["detail"]
        and "error" not in item["detail"]["output"]
    ]
    expanded = {
        evidence["evidence_id"]
        for item in trace
        if item["action"] in {"tool_result", "recovery_tool_result"}
        and item["detail"]["name"] == "expand_segments"
        for evidence in item["detail"]["output"].get("evidence", [])
    }
    cited = {
        evidence_id
        for claim in result["claims"]
        for evidence_id in claim["evidence_ids"]
    }
    if not cited.issubset(expanded):
        raise ValueError(f"trace cites an unexpanded candidate: {path.name}")
    admissible = {
        item["evidence_id"]
        for item in value["investigation_record"]["admissible_evidence"]
    }
    if admissible != expanded:
        raise ValueError(f"closed evidence set differs from expansions: {path.name}")
    evidence_dates = {
        item["evidence_id"]: item["event_date"] for item in result["evidence"]
    }
    for claim in result["claims"]:
        claim_dates = {evidence_dates[item] for item in claim["evidence_ids"]}
        if any(period not in claim_dates for period in claim["periods"]):
            raise ValueError(f"claimed period lacks same-date evidence: {path.name}")
    for evidence in result["evidence"]:
        content = artifacts.content(evidence["document_id"]).content
        exact = content[
            int(evidence["context_byte_start"]):int(evidence["context_byte_end"])
        ]
        if hashlib.sha256(exact).hexdigest() != evidence["context_sha256"]:
            raise ValueError(f"trace evidence no longer matches retained bytes: {path.name}")
        if exact.decode("utf-8", "replace").strip() != evidence["text"]:
            raise ValueError(f"trace evidence text is not the exact retained span: {path.name}")
    if path.stem != "insufficient" and not cited:
        raise ValueError(f"positive trace has no mapped evidence: {path.name}")
    if path.stem == "insufficient":
        if not result["gaps"] or not result["failed_searches"]:
            raise ValueError(f"insufficient trace omits gaps or failed searches: {path.name}")
    assessment = result["assessment"]
    if not result["answer"].startswith(assessment["lead_paragraph"]):
        raise ValueError(f"report does not begin with evaluated lead: {path.name}")
    if assessment["support_calibration"] not in {"strong", "bounded", "none"}:
        raise ValueError(f"support uses pseudo-precision or unknown category: {path.name}")
    rework = [item for item in trace if item["action"] == "rework_request"]
    if len(rework) > 1:
        raise ValueError(f"trace contains an open-ended recovery loop: {path.name}")
    if path.stem == "demand" and len(rework) != 1:
        raise ValueError("demand proving case did not exercise one bounded recovery")
    if path.stem in {"technology", "chronology", "insufficient"} and rework:
        raise ValueError(f"unnecessary recovery triggered for {path.name}")
    if report["status"] != result["status"]:
        raise ValueError(f"ResearchReport changed final status: {path.name}")
    if report["lead_paragraph"] != assessment["lead_paragraph"]:
        raise ValueError(f"ResearchReport changed adjudicated lead: {path.name}")
    if report["accepted_claims"] != result["claims"]:
        raise ValueError(f"ResearchReport broadened accepted claims: {path.name}")
    if report["evidence"] != result["evidence"]:
        raise ValueError(f"ResearchReport changed governed evidence: {path.name}")
    expected_mappings = [
        {
            "claim_index": index,
            "evidence_ids": claim["evidence_ids"],
            "periods": claim["periods"],
        }
        for index, claim in enumerate(result["claims"])
    ]
    if report["claim_to_evidence_mappings"] != expected_mappings:
        raise ValueError(f"ResearchReport changed claim mappings: {path.name}")
    if bool(rework) != report["recovery"]["occurred"]:
        raise ValueError(f"ResearchReport changed recovery history: {path.name}")
    regenerated = ResearchReportWriter().write_serialized(
        value, scope_from_run(value), report["trace_reference"]
    )
    regenerated_json = json.loads(json.dumps(asdict(regenerated), default=str))
    if regenerated_json != report:
        raise ValueError(f"ResearchReport is not deterministic: {path.name}")
    return {
        "case": path.stem,
        "question": result["question"],
        "status": result["status"],
        "support_calibration": assessment["support_calibration"],
        "completeness_calibration": assessment["completeness_calibration"],
        "consistency_findings": assessment["findings"],
        "recovery_cycles": len(rework),
        "recovery_tool_calls": sum(
            item["action"] == "recovery_tool_call" for item in trace
        ),
        "tool_calls": len(calls),
        "model_turns": sum(
            item["action"] == "model_turn" for item in trace
        ),
        "searches": len(search_results),
        "empty_searches": sum(not item["hits"] for item in search_results),
        "expanded_evidence": len(expanded),
        "cited_evidence": len(cited),
        "dates_cited": sorted({item["event_date"] for item in result["evidence"]}),
        "failed_searches": result["failed_searches"],
        "model_usage": value["model_usage"],
        "stopping_reason": result["stopping_reason"],
        "validation": "PASS",
        "research_report_id": report["report_id"],
    }


def main() -> int:
    """Validate the retained corpus and complete representative live trace set."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactQueryService(
        AcquisitionRepository(arguments.state / "acquisition"),
        FirmRepository.open(arguments.state / "firm-catalog"),
        load_canonical_template(),
    )
    access = TranscriptKnowledgeAccess(artifacts, TranscriptScope(("seagate",)))
    try:
        corpus = asdict(access.describe_corpus())
        (arguments.output / "retained-corpus.json").write_text(
            json.dumps(corpus, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        earliest = access.search(
            "40 terabyte", match="all", order="oldest", limit=5,
            max_per_document=2,
        )
        latest = access.search(
            "40 terabyte", match="all", order="latest", limit=5,
            max_per_document=2,
        )
        negative = access.search(
            "employee attrition geography", match="all", order="relevance",
            limit=5, max_per_document=2,
        )
        probes = {
            "chronology_oldest": asdict(earliest),
            "chronology_latest": asdict(latest),
            "insufficient_exact_conjunction": asdict(negative),
        }
        (arguments.output / "access-probes.json").write_text(
            json.dumps(probes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summaries = [
            trace_summary(
                arguments.traces / f"{case}.json",
                arguments.reports / f"{case}.json",
                status,
                access.repository_snapshot,
                artifacts,
            )
            for case, status in TRACE_CASES.items()
        ]
    finally:
        access.close()
    harness_imports = imports(ROOT / "src/rfi/research/harness.py")
    access_imports = imports(ROOT / "src/rfi/research/access.py")
    reporting_imports = imports(ROOT / "src/rfi/research/reporting.py")
    forbidden = {
        "rfi.acquisition", "rfi.storage", "rfi.mailing_lists.repository",
        "rfi.artifacts.repository",
    }
    if forbidden.intersection((*harness_imports, *access_imports)):
        raise ValueError("investigator or IQA imports a forbidden repository implementation")
    report_forbidden = {
        "rfi.research.access", "rfi.research.adjudication",
        "rfi.research.harness", "rfi.research.openai",
    }
    if report_forbidden.intersection(reporting_imports):
        raise ValueError("ResearchReportWriter imports an IQA, model, or reasoning layer")
    evaluation = {
        "result": "PASS",
        "corpus": {
            "repository_snapshot": corpus["repository_snapshot"],
            "documents": len(corpus["documents"]),
            "segments": corpus["segment_count"],
            "date_from": corpus["date_from"],
            "date_through": corpus["date_through"],
            "metadata_gaps": corpus["metadata_gaps"],
        },
        "dependency_check": {
            "result": "PASS",
            "harness_imports": harness_imports,
            "access_imports": access_imports,
            "reporting_imports": reporting_imports,
            "forbidden_repository_implementation_imports": [],
            "forbidden_report_writer_dependencies": [],
        },
        "trace_cases": summaries,
    }
    (arguments.output / "vertical-slice-evaluation.json").write_text(
        json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(evaluation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
