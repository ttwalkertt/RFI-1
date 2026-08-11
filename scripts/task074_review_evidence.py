#!/usr/bin/env python3
"""Validate and summarize the preserved TASK-074 QA/repair experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from rfi.investigation_qa import (
    CaseIdentity,
    QADisposition,
    SingleRepairLifecycle,
    parse_qa1,
    parse_qa2,
    parse_repair,
)
from rfi.investigation_qa.prompts import qa1_prompt, qa2_prompt, repair_prompt
from task074_qa_repair_experiment import CASES, EXPECTED_ANSWER_SHA256, fixed_proving_set

ALLOWED_MCP_CAPABILITIES = {
    "mcp.protocol:initialize",
    "mcp.protocol:notifications/initialized",
    "mcp.resources.list",
    "mcp.resources.templates.list",
    "mcp.tools.list",
    "query_artifacts",
    "read_artifact_bytes",
    "resource:artifacts",
    "resource:transcript-corpora",
    "resource:transcript-segments",
    "search_transcript_segments",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_stage_files(experiment: Path, stage: dict[str, Any]) -> None:
    for field in ("prompt", "schema", "events", "output", "mcp_trace"):
        path = experiment / str(stage[field])
        if digest(path) != stage[f"{field}_sha256"]:
            raise ValueError(f"stage {stage['case']}/{stage['stage']} changed: {field}")
    if not stage["fresh_context"]:
        raise ValueError("stage does not declare a fresh context")
    if stage["mcp_surface"] != "unchanged TASK-073 read-only RFI MCP":
        raise ValueError("stage used an unexpected MCP surface")


def verify_mcp_trace(path: Path) -> dict[str, Any]:
    trace = rows(path)
    capabilities = {str(item["capability"]) for item in trace}
    unexpected = capabilities - ALLOWED_MCP_CAPABILITIES
    if unexpected:
        raise ValueError(f"QA-specific or unexpected MCP capability: {sorted(unexpected)}")
    snapshots = {item.get("repository_snapshot") for item in trace}
    generations = {
        item["access_generation"]["generation_id"]
        for item in trace
        if item.get("access_generation")
    }
    if len(snapshots) != 1 or len(generations) != 1:
        raise ValueError("stage mixed repository snapshots or access generations")
    return {
        "operations": len(trace),
        "capabilities": dict(Counter(item["capability"] for item in trace)),
        "errors": sum(bool(item.get("error")) for item in trace),
        "repository_snapshot": snapshots.pop(),
        "generation_id": generations.pop(),
    }


def thread_id(path: Path) -> str:
    events = rows(path)
    started = [item for item in events if item.get("type") == "thread.started"]
    if len(started) != 1:
        raise ValueError(f"event stream does not identify one fresh thread: {path}")
    return str(started[0]["thread_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--startup-failure", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    experiment = arguments.experiment.resolve()
    source = arguments.source.resolve()
    adjudication = load(arguments.adjudication)
    manifest_path = experiment / "manifest.json"
    manifest = load(manifest_path)
    if digest(manifest_path) != adjudication["experiment_manifest_sha256"]:
        raise ValueError("post-run adjudication does not identify this experiment")
    if manifest["experiment_version"] != "task074.independent-qa-single-repair.v1":
        raise ValueError("unexpected experiment version")
    if [item["case"] for item in manifest["cases"]] != list(CASES):
        raise ValueError("experiment does not contain the five fixed cases in ticket order")
    fixed = manifest["fixed_proving_set"]
    if fixed["expected_answer_sha256"] != EXPECTED_ANSWER_SHA256:
        raise ValueError("fixed answer catalog changed")
    if not fixed["source_unchanged"] or fixed["first_pass_investigations_rerun"]:
        raise ValueError("TASK-073 proving outputs were changed or rerun")
    if not manifest["repository_unchanged"]:
        raise ValueError("TASK-074 changed retained repository authority")
    if manifest["repair_cycle_limit"] != 1 or manifest["escalation_available"]:
        raise ValueError("experiment escaped the hard one-cycle boundary")
    if manifest["qa_specific_mcp_tools"]:
        raise ValueError("experiment added QA-specific MCP tools")
    questions, answers = fixed_proving_set(source)
    summaries: list[dict[str, Any]] = []
    resolution_matrix: list[dict[str, Any]] = []
    thread_ids: list[str] = []
    for item in manifest["cases"]:
        case = str(item["case"])
        if item["fixed_answer_sha256"] != EXPECTED_ANSWER_SHA256[case]:
            raise ValueError(f"{case}: fixed answer association changed")
        qa1_stage = item["qa1"]
        repair_stage = item["repair1"]
        qa2_stage = item["qa2"]
        if repair_stage is None:
            raise ValueError(f"{case}: proving QA #1 unexpectedly bypassed repair")
        for stage in (qa1_stage, repair_stage, qa2_stage):
            verify_stage_files(experiment, stage)
            thread_ids.append(thread_id(experiment / stage["events"]))
        qa1_payload = load(experiment / qa1_stage["output"])
        qa1 = parse_qa1(qa1_payload, case)
        if qa1.disposition is not QADisposition.REPAIR_REQUIRED:
            raise ValueError(f"{case}: preserved repair lacks repair_required QA #1")
        finding_ids = tuple(finding.finding_id for finding in qa1.findings)
        repair_payload = load(experiment / repair_stage["output"])
        repair = parse_repair(repair_payload, case, finding_ids)
        qa2_payload = load(experiment / qa2_stage["output"])
        qa2 = parse_qa2(qa2_payload, case, finding_ids)
        if (experiment / qa1_stage["prompt"]).read_text(encoding="utf-8") != qa1_prompt(
            case, questions[case], answers[case]
        ):
            raise ValueError(f"{case}: QA #1 prompt includes unapproved context")
        if (experiment / repair_stage["prompt"]).read_text(
            encoding="utf-8"
        ) != repair_prompt(case, questions[case], answers[case], qa1):
            raise ValueError(f"{case}: repair prompt includes unapproved context")
        if (experiment / qa2_stage["prompt"]).read_text(encoding="utf-8") != qa2_prompt(
            case, questions[case], repair.repaired_answer, qa1, repair
        ):
            raise ValueError(f"{case}: QA #2 prompt includes unapproved context")
        lifecycle = SingleRepairLifecycle(
            CaseIdentity.from_content(case, questions[case], answers[case]),
            answers[case],
        )
        lifecycle.record_qa1(qa1)
        lifecycle.record_repair(repair)
        lifecycle.record_qa2(qa2)
        expected_record = json.loads(json.dumps(lifecycle.snapshot()))
        observed_record = load(experiment / item["lifecycle_record"])
        if expected_record != observed_record:
            raise ValueError(f"{case}: lifecycle record association changed")
        if observed_record["repair_cycle_count"] != 1 or not observed_record["terminal"]:
            raise ValueError(f"{case}: lifecycle did not stop after the one repair cycle")
        trace_summaries = {
            stage["stage"]: verify_mcp_trace(experiment / stage["mcp_trace"])
            for stage in (qa1_stage, repair_stage, qa2_stage)
        }
        resolution_by_id = {
            resolution.finding_id: resolution for resolution in qa2.resolutions
        }
        for finding in qa1.findings:
            resolution = resolution_by_id[finding.finding_id]
            resolution_matrix.append(
                {
                    "case_id": case,
                    "finding_id": finding.finding_id,
                    "severity": finding.severity.value,
                    "defect_class": finding.defect_class.value,
                    "resolution": resolution.state.value,
                    "attribution": (
                        resolution.attribution.value if resolution.attribution else None
                    ),
                }
            )
        summaries.append(
            {
                "case_id": case,
                "qa1_disposition": qa1.disposition.value,
                "qa1_findings": len(qa1.findings),
                "qa1_severity_counts": dict(
                    Counter(finding.severity.value for finding in qa1.findings)
                ),
                "qa1_mcp_operations": trace_summaries["qa1"]["operations"],
                "repair_mcp_operations": trace_summaries["repair1"]["operations"],
                "unresolved_repair_items": len(repair.unresolved_items),
                "qa2_mcp_operations": trace_summaries["qa2"]["operations"],
                "qa2_disposition": qa2.disposition.value,
                "qa2_new_findings": len(qa2.new_findings),
                "duration_seconds": round(
                    qa1_stage["duration_seconds"]
                    + repair_stage["duration_seconds"]
                    + qa2_stage["duration_seconds"],
                    3,
                ),
            }
        )
    if len(thread_ids) != len(set(thread_ids)):
        raise ValueError("one or more QA/repair stages reused a Codex thread context")
    startup_failure = None
    if arguments.startup_failure and arguments.startup_failure.is_dir():
        failure_events = arguments.startup_failure / "codex/qa1/sentiment.jsonl"
        failure_trace = arguments.startup_failure / "mcp/qa1/sentiment.jsonl"
        event_rows = rows(failure_events)
        startup_trace = rows(failure_trace)
        evidence_operations = [
            item
            for item in startup_trace
            if not str(item["capability"]).startswith("mcp.")
        ]
        startup_failure = {
            "stage": "sentiment/qa1",
            "classification": "structured_output_schema_startup_failure",
            "model_review_completed": any(
                item.get("type") == "turn.completed" for item in event_rows
            ),
            "mcp_startup_operations": len(startup_trace),
            "mcp_evidence_operations": len(evidence_operations),
            "preserved": True,
        }
        if (
            startup_failure["model_review_completed"]
            or startup_failure["mcp_evidence_operations"]
        ):
            raise ValueError("startup negative control unexpectedly performed review or MCP access")
    aggregate = adjudication["aggregate"]
    summary = {
        "result": "PASS",
        "meaning": "experiment integrity and lifecycle proof; not analytical acceptance",
        "experiment_manifest_sha256": digest(manifest_path),
        "fixed_proving_set_unchanged": True,
        "first_pass_investigations_rerun": False,
        "repository_unchanged": True,
        "fresh_contexts": len(thread_ids),
        "unique_fresh_contexts": len(set(thread_ids)),
        "repair_cycles": len(CASES),
        "second_repairs": 0,
        "escalations": 0,
        "mcp_surface_changed": False,
        "cases": summaries,
        "resolution_matrix": resolution_matrix,
        "false_positive_false_negative": aggregate,
        "diagnostic_attribution": adjudication["diagnostic_attribution"],
        "startup_negative_control": startup_failure,
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "experiment-evidence-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (arguments.output / "finding-resolution-matrix.json").write_text(
        json.dumps(resolution_matrix, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
