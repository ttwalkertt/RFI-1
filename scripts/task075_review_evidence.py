#!/usr/bin/env python3
"""Verify the frozen TASK-075 calibration evidence without held-out access."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rfi.qa_gauge import BenchmarkCorpus, parse_gauge_review
from rfi.qa_gauge.prompts import prompt_for_design


def digest(path: Path) -> str:
    """Return one file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    """Load one JSON object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def rows(path: Path) -> list[dict[str, Any]]:
    """Load a JSON-lines file."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_record(
    *, experiment: Path, record: dict[str, Any], corpus: BenchmarkCorpus, design: str
) -> dict[str, int]:
    """Verify one preserved judgment record and its reference-free prompt."""
    for field in ("prompt", "schema", "events", "stderr"):
        path = experiment / str(record[field])
        if not path.is_file():
            raise ValueError(f"missing {field}: {path}")
        digest_field = f"{field}_sha256"
        if digest_field in record and digest(path) != record[digest_field]:
            raise ValueError(f"changed {field}: {path}")
    output_name = record.get("output")
    case_id = str(record["case_id"])
    expected_prompt = prompt_for_design(design, corpus.reviewer_payload(case_id))
    prompt_path = experiment / str(record["prompt"])
    if prompt_path.read_text(encoding="utf-8") != expected_prompt:
        raise ValueError(f"prompt projection changed: {case_id}/{record['repeat']}")
    if output_name:
        output_path = experiment / str(output_name)
        if digest(output_path) != record["output_sha256"]:
            raise ValueError(f"changed output: {output_path}")
        payload = load(output_path)
        projected = corpus.reviewer_payload(case_id)
        parse_gauge_review(
            payload,
            evaluation_id=str(projected["evaluation_id"]),
            allowed_locators=corpus.allowed_locators(case_id),
        )
    elif not record.get("invalid_reason"):
        raise ValueError("record lacks both output and invalid reason")
    event_rows = rows(experiment / str(record["events"]))
    return {
        "attempts": len(record["attempts"]),
        "timeouts": sum(item["exit_code"] is None for item in record["attempts"]),
        "threads": sum(item.get("type") == "thread.started" for item in event_rows),
        "invalid": int(bool(record.get("invalid_reason"))),
    }


def verify_experiment(
    *, path: Path, corpus: BenchmarkCorpus, history_entry: dict[str, Any]
) -> dict[str, Any]:
    """Verify one v2 calibration iteration and return transport counts."""
    manifest_path = path / "manifest.json"
    score_path = path / "score.json"
    if digest(manifest_path) != history_entry["manifest_sha256"]:
        raise ValueError(f"manifest differs from calibration history: {path}")
    if digest(score_path) != history_entry["score_sha256"]:
        raise ValueError(f"score differs from calibration history: {path}")
    manifest = load(manifest_path)
    if manifest["partition"] != "calibration" or manifest["case_count"] != 44:
        raise ValueError("evaluation is not the frozen 44-case calibration partition")
    if manifest["design"] != history_entry["design"]:
        raise ValueError("design differs from calibration history")
    totals = {"attempts": 0, "timeouts": 0, "threads": 0, "invalid": 0}
    for record in manifest["records"]:
        result = verify_record(
            experiment=path,
            record=record,
            corpus=corpus,
            design=str(manifest["design"]),
        )
        for field, value in result.items():
            totals[field] += value
    return {
        "iteration": manifest["iteration"],
        "design": manifest["design"],
        "logical_judgments": manifest["model_call_count"],
        "valid_case_rate": load(score_path)["metrics"]["valid_evaluation_rate"],
        "transport_invocations": totals["attempts"],
        "timed_out_invocations": totals["timeouts"],
        "thread_started_events": totals["threads"],
        "invalid_judgments": totals["invalid"],
    }


def main() -> int:
    """Verify controls, freeze, trajectory, and raw v2 calibration evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    corpus_root = arguments.corpus.resolve()
    control = arguments.control.resolve()
    state = arguments.state.resolve()
    calibration = arguments.calibration.resolve()
    if (corpus_root / "validation/cases.jsonl").exists() or (
        corpus_root / "validation/fixtures.json"
    ).exists():
        raise ValueError("held-out validation must remain absent at this review checkpoint")
    corpus = BenchmarkCorpus.load(corpus_root, partition="calibration")
    if len(corpus.cases) != 44:
        raise ValueError("calibration corpus does not contain exactly 44 cases")
    freeze_path = control / "frozen-gauge-manifest.json"
    freeze = load(freeze_path)
    history = load(control / "calibration-history.json")
    phase = load(state / "phase.json")
    ledger = load(state / "calibration-ledger.json")
    if phase["phase"] != "frozen" or phase["validation_attempted"]:
        raise ValueError("gauge is not frozen before an untouched validation")
    if freeze["calibration_all_thresholds_passed"] or freeze["termination_reason"] != "budget":
        raise ValueError("freeze does not preserve the negative calibration result")
    if ledger["model_calls_reserved"] != 220:
        raise ValueError("v2 logical-judgment accounting differs from the frozen history")
    experiment_paths = (
        calibration / "baseline-decomposed-v2",
        calibration / "iteration-01-epistemic-root-cause-v3",
        calibration / "terminal-epistemic-root-cause-v3",
    )
    iterations = history["v2_iterations"]
    if len(iterations) != len(experiment_paths):
        raise ValueError("calibration history does not identify every v2 iteration")
    verified = [
        verify_experiment(path=path, corpus=corpus, history_entry=entry)
        for path, entry in zip(experiment_paths, iterations, strict=True)
    ]
    terminal_score = load(experiment_paths[-1] / "score.json")
    if terminal_score["all_thresholds_passed"]:
        raise ValueError("terminal result unexpectedly passes")
    summary = {
        "result": "PASS",
        "meaning": "frozen calibration integrity; not held-out or analytical acceptance",
        "benchmark_version": corpus.benchmark_version,
        "calibration_cases": len(corpus.cases),
        "validation_files_physically_absent": True,
        "validation_attempted": False,
        "quarantine_cases": 4,
        "freeze_sha256": digest(freeze_path),
        "frozen_design": freeze["design"],
        "freeze_termination_reason": freeze["termination_reason"],
        "calibration_all_thresholds_passed": False,
        "v2_logical_judgments": ledger["model_calls_reserved"],
        "iterations": verified,
        "terminal_metrics": terminal_score["metrics"],
        "terminal_invalid_cases": terminal_score["invalid_cases"],
        "mcp_access_changes": freeze["mcp_access_changes"],
        "post_freeze_tuning_permitted": freeze["post_freeze_tuning_permitted"],
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "experiment-evidence-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
