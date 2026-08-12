#!/usr/bin/env python3
"""Verify TASK-075 calibration, freeze, and one-shot held-out evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from rfi.qa_gauge import BenchmarkCorpus, GaugeReview, parse_gauge_review, score_partition
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
) -> tuple[dict[str, int], GaugeReview | None]:
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
    review: GaugeReview | None = None
    if output_name:
        output_path = experiment / str(output_name)
        if digest(output_path) != record["output_sha256"]:
            raise ValueError(f"changed output: {output_path}")
        payload = load(output_path)
        projected = corpus.reviewer_payload(case_id)
        review = parse_gauge_review(
            payload,
            evaluation_id=str(projected["evaluation_id"]),
            allowed_locators=corpus.allowed_locators(case_id),
        )
    elif not record.get("invalid_reason"):
        raise ValueError("record lacks both output and invalid reason")
    event_rows = rows(experiment / str(record["events"]))
    return (
        {
            "attempts": len(record["attempts"]),
            "timeouts": sum(item["exit_code"] is None for item in record["attempts"]),
            "threads": sum(item.get("type") == "thread.started" for item in event_rows),
            "invalid": int(bool(record.get("invalid_reason"))),
            "retried": int(len(record["attempts"]) > 1),
        },
        review,
    )


def verify_experiment(
    *,
    path: Path,
    corpus: BenchmarkCorpus,
    identity: dict[str, Any],
    partition: str,
    case_ids: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Verify, reconstruct, and deterministically rescore one experiment."""
    manifest_path = path / "manifest.json"
    score_path = path / "score.json"
    if digest(manifest_path) != identity["manifest_sha256"]:
        raise ValueError(f"manifest differs from recorded identity: {path}")
    if digest(score_path) != identity["score_sha256"]:
        raise ValueError(f"score differs from recorded identity: {path}")
    manifest = load(manifest_path)
    score = load(score_path)
    if manifest["partition"] != partition or manifest["case_count"] != len(case_ids):
        raise ValueError(f"experiment partition or size differs: {path}")
    if manifest["design"] != identity["design"]:
        raise ValueError(f"design differs from recorded identity: {path}")
    if set(case_ids) != set(corpus.by_id):
        raise ValueError(f"case IDs differ from the authoritative {partition} corpus")
    totals = {"attempts": 0, "timeouts": 0, "threads": 0, "invalid": 0, "retried": 0}
    reviews: dict[str, dict[int, GaugeReview]] = defaultdict(dict)
    for record in manifest["records"]:
        counts, review = verify_record(
            experiment=path,
            record=record,
            corpus=corpus,
            design=str(manifest["design"]),
        )
        for field, value in counts.items():
            totals[field] += value
        if review is not None:
            reviews[str(record["case_id"])][int(record["repeat"])] = review
    reviews_by_case = {
        case_id: tuple(by_repeat[index] for index in sorted(by_repeat))
        for case_id, by_repeat in reviews.items()
    }
    reconstructed = score_partition(
        cases=[corpus.by_id[case_id] for case_id in case_ids],
        reviews_by_case=reviews_by_case,
        contract=contract,
        required_runs=int(manifest["repeat_count"]),
    )
    json_reconstructed = json.loads(json.dumps(reconstructed))
    if json_reconstructed != score:
        raise ValueError(f"deterministic rescore differs from preserved score: {path}")
    return {
        "iteration": manifest["iteration"],
        "partition": partition,
        "design": manifest["design"],
        "logical_judgments": manifest["model_call_count"],
        "valid_case_rate": score["metrics"]["valid_evaluation_rate"],
        "all_thresholds_passed": score["all_thresholds_passed"],
        "transport_invocations": totals["attempts"],
        "retried_judgments": totals["retried"],
        "timed_out_invocations": totals["timeouts"],
        "thread_started_events": totals["threads"],
        "invalid_judgments": totals["invalid"],
        "manifest_sha256": digest(manifest_path),
        "score_sha256": digest(score_path),
    }


def main() -> int:
    """Verify controls, trajectory, freeze, and the one held-out attempt."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    corpus_root = arguments.corpus.resolve()
    control = arguments.control.resolve()
    state = arguments.state.resolve()
    calibration = arguments.calibration.resolve()
    validation_path = arguments.validation.resolve()
    recorded_result = load(arguments.result.resolve())
    for relative, expected in recorded_result["restored_validation_files"].items():
        restored = corpus_root / relative
        if not restored.is_file() or digest(restored) != expected:
            raise ValueError(f"restored validation identity differs: {relative}")
    calibration_corpus = BenchmarkCorpus.load(corpus_root, partition="calibration")
    validation_corpus = BenchmarkCorpus.load(corpus_root, partition="validation")
    quarantine_corpus = BenchmarkCorpus.load(corpus_root, partition="quarantine")
    if (len(calibration_corpus.cases), len(validation_corpus.cases)) != (44, 28):
        raise ValueError("objective partition sizes differ from the v2 split")
    if len(quarantine_corpus.cases) != 4:
        raise ValueError("quarantine does not contain exactly four cases")
    freeze_path = control / "frozen-gauge-manifest.json"
    freeze = load(freeze_path)
    history = load(control / "calibration-history.json")
    partition = load(control / "partition-manifest.json")
    contract = load(control / "scoring-contract.json")
    phase = load(state / "phase.json")
    ledger = load(state / "calibration-ledger.json")
    attempt = load(state / "validation-attempt.json")
    freeze_sha256 = digest(freeze_path)
    if phase["phase"] != "frozen" or not phase["validation_attempted"]:
        raise ValueError("one-shot validation phase marker is incomplete")
    if attempt["status"] != "complete" or attempt["freeze_sha256"] != freeze_sha256:
        raise ValueError("validation attempt marker differs from the frozen gauge")
    if freeze_sha256 != recorded_result["freeze"]["manifest_sha256"]:
        raise ValueError("frozen-gauge identity differs from the recorded validation")
    if freeze["post_freeze_tuning_permitted"] or freeze["mcp_access_changes"]:
        raise ValueError("freeze does not preserve the no-tuning/no-MCP-change boundary")
    if ledger["model_calls_reserved"] != 220:
        raise ValueError("v2 calibration accounting differs from the frozen history")
    calibration_paths = (
        calibration / "baseline-decomposed-v2",
        calibration / "iteration-01-epistemic-root-cause-v3",
        calibration / "terminal-epistemic-root-cause-v3",
    )
    iterations = history["v2_iterations"]
    if len(iterations) != len(calibration_paths):
        raise ValueError("calibration history does not identify every v2 iteration")
    calibration_case_ids = list(partition["calibration"]["case_ids"])
    verified_calibration = [
        verify_experiment(
            path=path,
            corpus=calibration_corpus,
            identity=entry,
            partition="calibration",
            case_ids=calibration_case_ids,
            contract=contract,
        )
        for path, entry in zip(calibration_paths, iterations, strict=True)
    ]
    validation_identity = {
        "design": recorded_result["freeze"]["design"],
        "manifest_sha256": recorded_result["validation_attempt"]["manifest_sha256"],
        "score_sha256": recorded_result["validation_attempt"]["score_sha256"],
    }
    verified_validation = verify_experiment(
        path=validation_path,
        corpus=validation_corpus,
        identity=validation_identity,
        partition="validation",
        case_ids=sorted(validation_corpus.by_id),
        contract=contract,
    )
    validation_score = load(validation_path / "score.json")
    if validation_score["metrics"] != recorded_result["metrics"]:
        raise ValueError("recorded validation metrics differ from the preserved score")
    if validation_score["all_thresholds_passed"] or attempt["all_thresholds_passed"]:
        raise ValueError("negative validation result was not preserved")
    if attempt["score_sha256"] != validation_identity["score_sha256"]:
        raise ValueError("attempt marker score identity differs")
    summary = {
        "result": "PASS",
        "meaning": "complete frozen calibration and one-shot held-out evidence integrity",
        "benchmark_version": validation_corpus.benchmark_version,
        "calibration_cases": len(calibration_corpus.cases),
        "validation_cases": len(validation_corpus.cases),
        "validation_files_physically_present_and_hash_verified": True,
        "validation_attempted_exactly_once": True,
        "quarantine_cases": len(quarantine_corpus.cases),
        "freeze_sha256": freeze_sha256,
        "frozen_design": freeze["design"],
        "post_freeze_tuning": False,
        "calibration": verified_calibration,
        "validation": verified_validation,
        "validation_metrics": validation_score["metrics"],
        "validation_failed_thresholds": recorded_result["failed_thresholds"],
        "fresh_live_transfer_attempted": False,
        "final_architectural_disposition": recorded_result[
            "final_architectural_disposition"
        ],
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "experiment-evidence-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
