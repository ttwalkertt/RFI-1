#!/usr/bin/env python3
"""Run fresh QA #1, one bounded repair, and fresh terminal QA #2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rfi.investigation_qa import (
    CaseIdentity,
    QADisposition,
    SingleRepairLifecycle,
    parse_qa1,
    parse_qa2,
    parse_repair,
    qa1_output_schema,
    qa2_output_schema,
    repair_output_schema,
)
from rfi.investigation_qa.prompts import qa1_prompt, qa2_prompt, repair_prompt

ROOT = Path(__file__).resolve().parents[1]
CASES = ("sentiment", "demand", "technology", "chronology", "insufficient")
EXPECTED_ANSWER_SHA256 = {
    "sentiment": "3131d8a5c831f46bf95e07b61dd2548e3ff975a08a96e78902fdd5a4aa1d8f32",
    "demand": "2549968bd230fe8b23b9f2cba99ec1c2cc38cfabe9fd97f176d3884639d1a652",
    "technology": "c219837d6f1ed9dc76c5cc60ca88efe0b6953d9bea90feab5de5237a32d00b83",
    "chronology": "d53bc60cdef6b229f34dd45c9d7d61cc3a0bc4a10e6893a4aa799d9708a74c59",
    "insufficient": "04c42238700b5d28127918af9bb09ef2e19861e7326a9556503454e87f9b55b3",
}


def digest(path: Path) -> str:
    """Return one file digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_fingerprint(state: Path) -> dict[str, Any]:
    """Fingerprint retained authority before and after the read-only experiment."""
    database = state / "repository.sqlite3"
    content = state / "content/sha256"
    files = sorted(path for path in content.rglob("*") if path.is_file())
    return {
        "database_sha256": digest(database),
        "database_bytes": database.stat().st_size,
        "content_files": len(files),
        "content_manifest_sha256": hashlib.sha256(
            "\n".join(
                f"{path.name}:{digest(path)}:{path.stat().st_size}" for path in files
            ).encode()
        ).hexdigest(),
    }


def fixed_proving_set(source: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Load exactly the five preserved TASK-073 answers and prove their identity."""
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("experiment_version") != "task073.codex-work.v1":
        raise ValueError("fixed proving set is not the TASK-073 experiment")
    if [item.get("case") for item in manifest.get("cases", [])] != list(CASES):
        raise ValueError("fixed proving set does not contain the five cases in ticket order")
    questions: dict[str, str] = {}
    answers: dict[str, str] = {}
    for item in manifest["cases"]:
        case = str(item["case"])
        answer_path = source / str(item["answer"])
        observed = digest(answer_path)
        if observed != EXPECTED_ANSWER_SHA256[case]:
            raise ValueError(f"{case}: preserved TASK-073 answer digest changed")
        questions[case] = str(item["question"])
        answers[case] = answer_path.read_text(encoding="utf-8")
    return questions, answers


def source_manifest(source: Path) -> dict[str, Any]:
    """Record every first-pass proving file without disclosing any trace to reviewers."""
    return {
        path.relative_to(source).as_posix(): {
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(source.rglob("*"))
        if path.is_file()
    }


def mcp_counts(path: Path) -> dict[str, Any]:
    """Summarize one stage's frozen MCP operations without judging them."""
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "operation_count": len(rows),
        "search_count": sum(
            row.get("capability") == "search_transcript_segments" for row in rows
        ),
        "exact_segment_read_count": sum(
            row.get("capability") == "resource:transcript-segments" for row in rows
        ),
        "artifact_byte_read_count": sum(
            row.get("capability") == "read_artifact_bytes" for row in rows
        ),
        "error_count": sum(bool(row.get("error")) for row in rows),
    }


def run_stage(
    *,
    case: str,
    stage: str,
    prompt: str,
    schema: dict[str, Any],
    state: Path,
    output: Path,
    model: str | None,
    codex_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one fresh ephemeral context with only the unchanged RFI MCP configured."""
    prompt_path = output / "prompts" / stage / f"{case}.txt"
    schema_path = output / "schemas" / stage / f"{case}.json"
    events = output / "codex" / stage / f"{case}.jsonl"
    result_path = output / "outputs" / stage / f"{case}.json"
    access_trace = output / "mcp" / stage / f"{case}.jsonl"
    stderr_path = output / "codex" / stage / f"{case}.stderr.txt"
    for path in (prompt_path, schema_path, events, result_path, access_trace, stderr_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    server_args = [
        "-m",
        "rfi.mcp.server",
        "--state",
        str(state),
        "--trace",
        str(access_trace),
    ]
    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--json",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(result_path),
        "-c",
        f"mcp_servers.rfi.command={json.dumps(str(ROOT / '.venv/bin/python'))}",
        "-c",
        f"mcp_servers.rfi.args={json.dumps(server_args)}",
        "-c",
        f"mcp_servers.rfi.cwd={json.dumps(str(ROOT))}",
        "-c",
        f"mcp_servers.rfi.env={{PYTHONPATH={json.dumps(str(ROOT / 'src'))}}}",
        "-c",
        "mcp_servers.rfi.required=true",
        "-c",
        "mcp_servers.rfi.startup_timeout_sec=60",
        "-c",
        "mcp_servers.rfi.tool_timeout_sec=60",
        "-c",
        'mcp_servers.rfi.default_tools_approval_mode="auto"',
    ]
    if model:
        command.extend(("--model", model))
    started = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix=f"task074-{case}-{stage}-") as workspace:
        command.extend(("--cd", workspace, prompt))
        with events.open("w", encoding="utf-8") as stream:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=os.environ,
                stdout=stream,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1800,
                check=False,
            )
    ended = datetime.now(UTC)
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"{case}/{stage}: Codex exited {completed.returncode}")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    record = {
        "case": case,
        "stage": stage,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "exit_code": completed.returncode,
        "runtime_identity": {
            "codex_version": codex_version,
            "model_override": model,
            "model_selection": "explicit override" if model else "Codex CLI default",
            "user_configuration_loaded": False,
            "ephemeral": True,
            "sandbox": "read-only",
        },
        "prompt": str(prompt_path.relative_to(output)),
        "prompt_sha256": digest(prompt_path),
        "schema": str(schema_path.relative_to(output)),
        "schema_sha256": digest(schema_path),
        "events": str(events.relative_to(output)),
        "events_sha256": digest(events),
        "output": str(result_path.relative_to(output)),
        "output_sha256": digest(result_path),
        "mcp_trace": str(access_trace.relative_to(output)),
        "mcp_trace_sha256": digest(access_trace),
        "stderr": str(stderr_path.relative_to(output)),
        "command": command[:-1] + ["<EXACT PROMPT STORED SEPARATELY>"],
        "fresh_context": True,
        "mcp_surface": "unchanged TASK-073 read-only RFI MCP",
        "mcp_metrics": mcp_counts(access_trace),
    }
    return payload, record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model")
    arguments = parser.parse_args()
    state = arguments.state.resolve()
    source = arguments.source.resolve()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    codex_version = subprocess.run(
        ["codex", "--version"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    ).stdout.strip().splitlines()[-1]
    before = state_fingerprint(state)
    source_before = source_manifest(source)
    questions, answers = fixed_proving_set(source)
    cases: list[dict[str, Any]] = []
    for case in CASES:
        identity = CaseIdentity.from_content(case, questions[case], answers[case])
        lifecycle = SingleRepairLifecycle(identity, answers[case])
        qa1_payload, qa1_run = run_stage(
            case=case,
            stage="qa1",
            prompt=qa1_prompt(case, questions[case], answers[case]),
            schema=qa1_output_schema(case),
            state=state,
            output=output,
            model=arguments.model,
            codex_version=codex_version,
        )
        qa1 = parse_qa1(qa1_payload, case)
        lifecycle.record_qa1(qa1)
        repair_run = None
        if qa1.disposition is QADisposition.REPAIR_REQUIRED:
            finding_ids = tuple(item.finding_id for item in qa1.findings)
            repair_payload, repair_run = run_stage(
                case=case,
                stage="repair1",
                prompt=repair_prompt(case, questions[case], answers[case], qa1),
                schema=repair_output_schema(case, finding_ids),
                state=state,
                output=output,
                model=arguments.model,
                codex_version=codex_version,
            )
            repair = parse_repair(repair_payload, case, finding_ids)
            lifecycle.record_repair(repair)
        finding_ids = tuple(item.finding_id for item in qa1.findings)
        qa2_payload, qa2_run = run_stage(
            case=case,
            stage="qa2",
            prompt=qa2_prompt(
                case,
                questions[case],
                lifecycle.qa2_submission,
                qa1,
                lifecycle.repair,
            ),
            schema=qa2_output_schema(case, finding_ids),
            state=state,
            output=output,
            model=arguments.model,
            codex_version=codex_version,
        )
        qa2 = parse_qa2(qa2_payload, case, finding_ids)
        lifecycle.record_qa2(qa2)
        record_path = output / "records" / f"{case}.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(lifecycle.snapshot(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        cases.append(
            {
                "case": case,
                "question": questions[case],
                "fixed_answer_sha256": identity.original_answer_sha256,
                "qa1": qa1_run,
                "repair1": repair_run,
                "qa2": qa2_run,
                "lifecycle_record": str(record_path.relative_to(output)),
                "lifecycle_record_sha256": digest(record_path),
            }
        )
    after = state_fingerprint(state)
    source_after = source_manifest(source)
    manifest = {
        "experiment_version": "task074.independent-qa-single-repair.v1",
        "codex_version": codex_version,
        "model_override": arguments.model,
        "fixed_proving_source": str(source),
        "fixed_proving_set": {
            "case_order": list(CASES),
            "expected_answer_sha256": EXPECTED_ANSWER_SHA256,
            "source_files_before": source_before,
            "source_files_after": source_after,
            "source_unchanged": source_before == source_after,
            "first_pass_investigations_rerun": False,
        },
        "repository_before": before,
        "repository_after": after,
        "repository_unchanged": before == after,
        "lifecycle": "TASK-073 answer -> QA #1 -> at most one repair -> fresh QA #2 -> stop",
        "repair_cycle_limit": 1,
        "escalation_available": False,
        "qa_specific_mcp_tools": False,
        "cases": cases,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if before == after and source_before == source_after else 1


if __name__ == "__main__":
    raise SystemExit(main())
