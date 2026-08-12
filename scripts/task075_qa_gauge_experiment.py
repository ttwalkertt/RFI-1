#!/usr/bin/env python3
"""Prepare, calibrate, freeze, and once-only validate the TASK-075 QA gauge."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rfi.qa_gauge.benchmark import (
    BenchmarkCorpus,
    prepare_control_manifests,
    prepare_v2_control_manifests,
    sha256,
)
from rfi.qa_gauge.contracts import GaugeReview, gauge_output_schema, parse_gauge_review
from rfi.qa_gauge.prompts import DESIGN_BASELINE, prompt_for_design
from rfi.qa_gauge.scoring import score_partition

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks/rfi_qa_candidates"
V2_CORPUS = ROOT / "benchmarks/rfi_qa_candidates_v2"
DEFAULT_CONTROL = ROOT / "experiments/task075"
DEFAULT_STATE = ROOT / ".artifacts/task075-control"
SCORING = DEFAULT_CONTROL / "scoring-contract.json"
CONFIG = DEFAULT_CONTROL / "optimization-config.json"
PREREGISTRATION_COMMIT = "045ff69"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _phase_path(state: Path) -> Path:
    return state / "phase.json"


def _phase(state: Path) -> dict[str, Any]:
    path = _phase_path(state)
    if not path.exists():
        raise ValueError("TASK-075 controls are not prepared")
    return _json(path)


def _load_partition(control: Path) -> dict[str, Any]:
    partition = _json(control / "partition-manifest.json")
    if not partition.get("disjoint") or not partition.get("objective_population_exhausted"):
        raise ValueError("invalid calibration/validation partition manifest")
    return partition


def _assert_frozen_inputs(control: Path, corpus: Path) -> None:
    freeze = _json(control / "corpus-freeze-manifest.json")
    if sha256(control / "scoring-contract.json") != freeze["scoring_contract_sha256"]:
        raise ValueError("scoring contract changed after partition")
    if sha256(control / "optimization-config.json") != freeze["optimization_config_sha256"]:
        raise ValueError("optimization configuration changed after partition")
    file_section = freeze.get("visible_files", freeze.get("corpus_files", {}))
    for name, identity in file_section.items():
        path = corpus / name
        if sha256(path) != identity["sha256"] or path.stat().st_size != identity["bytes"]:
            raise ValueError(f"frozen benchmark input changed: {name}")


def _assert_restored_validation(control: Path, corpus: Path) -> None:
    freeze = _json(control / "corpus-freeze-manifest.json")
    held_out = freeze.get("held_out_files")
    if not held_out:
        return
    for relative, identity in held_out.items():
        path = corpus / relative
        if not path.exists():
            raise ValueError(
                "held-out validation files have not been restored by the human operator"
            )
        if sha256(path) != identity["sha256"]:
            raise ValueError(f"restored held-out digest mismatch: {relative}")


def prepare(args: argparse.Namespace) -> int:
    state = args.state.resolve()
    control = args.control.resolve()
    state.mkdir(parents=True, exist_ok=True)
    if _phase_path(state).exists():
        raise ValueError("TASK-075 preparation already occurred")
    subprocess.run(
        [str(ROOT / ".venv/bin/python"), "benchmarks/rfi_qa_candidates/validate_candidates.py"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        check=True,
    )
    result = prepare_control_manifests(
        corpus_root=args.corpus,
        scoring_path=control / "scoring-contract.json",
        config_path=control / "optimization-config.json",
        output=control,
        preregistration_commit=PREREGISTRATION_COMMIT,
    )
    _write_json(
        _phase_path(state),
        {
            "phase": "calibration",
            "prepared_at_utc": datetime.now(UTC).isoformat(),
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "corpus_freeze_sha256": sha256(control / "corpus-freeze-manifest.json"),
            "partition_sha256": sha256(control / "partition-manifest.json"),
            "validation_attempted": False,
        },
    )
    _write_json(state / "calibration-ledger.json", {"model_calls_reserved": 0, "iterations": []})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def prepare_v2(args: argparse.Namespace) -> int:
    """Adopt benchmark v2 while preserving the original trajectory as provenance."""
    state = args.state.resolve()
    control = args.control.resolve()
    corpus = args.corpus.resolve()
    state.mkdir(parents=True, exist_ok=True)
    if _phase_path(state).exists():
        raise ValueError("TASK-075 v2 preparation already occurred")
    subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(corpus / "validate_candidates.py"), "--visible"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        check=True,
    )
    result = prepare_v2_control_manifests(
        corpus_root=corpus,
        scoring_path=control / "scoring-contract.json",
        config_path=control / "optimization-config.json",
        output=control,
        authoring_commit="ac2837034078ec101ea7e2a582916268b88663fb",
    )
    previous_ledger_path = DEFAULT_STATE / "calibration-ledger.json"
    previous = _json(previous_ledger_path)
    if int(previous["model_calls_reserved"]) != 80:
        raise ValueError("preserved v1 calibration budget does not equal the recorded 80 calls")
    ledger = {
        "budget_version": "task075.rbf-optimization.v1",
        "maximum_calibration_model_calls": 240,
        "model_calls_reserved": 0,
        "model_calls_scheduled_total": 0,
        "iterations": [],
        "prior_v1_trajectory": {
            "model_calls_reserved": 80,
            "model_calls_scheduled_total": int(
                previous.get("model_calls_scheduled_total", 80)
            ),
            "iterations": previous["iterations"],
        },
        "benchmark_v2_resumption": {
            "retained_design": "task075.decomposed-gauge-v2",
            "prior_v1_calls_preserved_as_provenance": 80,
            "v2_calls_remaining": 240,
            "baseline_v2_calls_preregistered": 44,
            "full_feedback_iteration_calls_preregistered": 44,
            "terminal_v2_calls_preregistered": 132,
            "planned_v2_calls": 220,
            "unallocated_contingency_calls": 20,
            "decision_source": "experiments/task075/benchmark-v2-resumption.json",
        },
    }
    _write_json(state / "calibration-ledger.json", ledger)
    _write_json(
        _phase_path(state),
        {
            "phase": "calibration",
            "prepared_at_utc": datetime.now(UTC).isoformat(),
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "benchmark_authoring_commit": "ac2837034078ec101ea7e2a582916268b88663fb",
            "benchmark_version": "rfi-qa-independent-v2.0.0",
            "corpus_freeze_sha256": sha256(control / "corpus-freeze-manifest.json"),
            "partition_sha256": sha256(control / "partition-manifest.json"),
            "validation_attempted": False,
            "held_out_files_present": False,
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _codex_version() -> str:
    return subprocess.run(
        ["codex", "--version"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    ).stdout.strip().splitlines()[-1]


def _run_one(
    *,
    case_id: str,
    repeat: int,
    design: str,
    corpus: BenchmarkCorpus,
    output: Path,
    codex_version: str,
    transport_retry_limit: int,
) -> tuple[str, int, GaugeReview | None, dict[str, Any]]:
    payload = corpus.reviewer_payload(case_id)
    forbidden = {"reference_qa", "adjudicability", "pair_id", "title"}
    serialized_payload = json.dumps(payload, sort_keys=True)
    if any(f'"{field}"' in serialized_payload for field in forbidden):
        raise ValueError("reviewer payload contains a withheld benchmark field")
    allowed_locators = corpus.allowed_locators(case_id)
    prompt = prompt_for_design(design, payload)
    schema = gauge_output_schema(str(payload["evaluation_id"]), allowed_locators)
    run_root = output / "runs" / case_id / f"repeat-{repeat:02d}"
    prompt_path = run_root / "prompt.txt"
    schema_path = run_root / "schema.json"
    events_path = run_root / "events.jsonl"
    result_path = run_root / "output.json"
    stderr_path = run_root / "stderr.txt"
    for path in (prompt_path, schema_path, events_path, result_path, stderr_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    _write_json(schema_path, schema)
    base_command = [
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
    ]
    attempts: list[dict[str, Any]] = []
    review: GaugeReview | None = None
    invalid_reason: str | None = None
    with tempfile.TemporaryDirectory(prefix=f"task075-{case_id}-{repeat}-") as workspace:
        command = [*base_command, "--cd", workspace, prompt]
        for attempt in range(transport_retry_limit + 1):
            started = datetime.now(UTC)
            try:
                with events_path.open("a", encoding="utf-8") as events:
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        env=os.environ,
                        text=True,
                        stdout=events,
                        stderr=subprocess.PIPE,
                        timeout=180,
                        check=False,
                    )
                exit_code: int | None = completed.returncode
                stderr = completed.stderr
            except subprocess.TimeoutExpired:
                exit_code = None
                stderr = "Codex execution exceeded the 180-second transport timeout.\n"
            ended = datetime.now(UTC)
            stderr_path.write_text(stderr, encoding="utf-8")
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "started_at_utc": started.isoformat(),
                    "ended_at_utc": ended.isoformat(),
                    "duration_seconds": round((ended - started).total_seconds(), 3),
                    "exit_code": exit_code,
                }
            )
            if exit_code == 0 and result_path.exists():
                break
            invalid_reason = f"transport/runtime failure after attempt {attempt + 1}"
    if attempts[-1]["exit_code"] == 0 and result_path.exists():
        try:
            result_payload = _json(result_path)
            review = parse_gauge_review(
                result_payload,
                evaluation_id=str(payload["evaluation_id"]),
                allowed_locators=allowed_locators,
            )
            invalid_reason = None
        except (json.JSONDecodeError, ValueError) as exc:
            invalid_reason = str(exc)
    record = {
        "case_id": case_id,
        "repeat": repeat,
        "design": design,
        "fresh_context": True,
        "reviewer_withheld_fields": sorted(forbidden),
        "runtime_identity": {
            "codex_version": codex_version,
            "model": "Codex CLI default; no override",
            "user_configuration_loaded": False,
            "rules_loaded": False,
            "ephemeral": True,
            "sandbox": "read-only",
        },
        "command": base_command
        + ["--cd", "<FRESH TEMPORARY DIRECTORY>", "<PROMPT STORED SEPARATELY>"],
        "attempts": attempts,
        "prompt": str(prompt_path.relative_to(output)),
        "prompt_sha256": sha256(prompt_path),
        "schema": str(schema_path.relative_to(output)),
        "schema_sha256": sha256(schema_path),
        "events": str(events_path.relative_to(output)),
        "events_sha256": sha256(events_path),
        "output": str(result_path.relative_to(output)) if result_path.exists() else None,
        "output_sha256": sha256(result_path) if result_path.exists() else None,
        "stderr": str(stderr_path.relative_to(output)),
        "invalid_reason": invalid_reason,
    }
    _write_json(run_root / "record.json", record)
    return case_id, repeat, review, record


def _reserve_calibration_calls(
    *, state: Path, iteration: str, calls: int, design: str, reason: str, attribution: str
) -> None:
    ledger_path = state / "calibration-ledger.json"
    ledger = _json(ledger_path)
    config = _json(DEFAULT_CONTROL / "optimization-config.json")
    updated = int(ledger["model_calls_reserved"]) + calls
    maximum = int(config["optimization_budget"]["maximum_calibration_model_calls"])
    if updated > maximum:
        raise ValueError(f"calibration model-call budget exceeded: {updated}>{maximum}")
    ledger["model_calls_reserved"] = updated
    ledger["iterations"].append(
        {
            "iteration": iteration,
            "design": design,
            "calls_reserved": calls,
            "change_reason": reason,
            "failure_attribution": attribution,
            "reserved_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    _write_json(ledger_path, ledger)


def _partition_case_ids(
    *, partition: dict[str, Any], partition_name: str, corpus: BenchmarkCorpus
) -> list[str]:
    recorded = partition[partition_name].get("case_ids")
    if recorded is not None:
        case_ids = list(recorded)
        if set(case_ids) != set(corpus.by_id):
            raise ValueError(f"{partition_name} case IDs differ from the frozen manifest")
        return case_ids
    return sorted(corpus.by_id)


def _run_partition(args: argparse.Namespace, partition_name: str) -> int:
    state = args.state.resolve()
    control = args.control.resolve()
    corpus_root = args.corpus.resolve()
    phase = _phase(state)
    _assert_frozen_inputs(control, corpus_root)
    if partition_name == "calibration" and phase["phase"] != "calibration":
        raise ValueError("calibration is prohibited after the QA design freeze")
    if partition_name == "validation":
        if phase["phase"] != "frozen":
            raise ValueError("held-out validation is protected until freeze")
        assert_frozen_gauge(control, args.freeze.resolve())
        _assert_restored_validation(control, corpus_root)
        marker = state / "validation-attempt.json"
        if marker.exists():
            raise ValueError("held-out validation has already been attempted")
        _write_json(
            marker,
            {
                "started_at_utc": datetime.now(UTC).isoformat(),
                "freeze_sha256": sha256(args.freeze.resolve()),
                "status": "started; a second attempt is prohibited even if this attempt is invalid",
            },
        )
        phase["validation_attempted"] = True
        _write_json(_phase_path(state), phase)
    config = _json(control / "optimization-config.json")
    repeats = int(args.repeats)
    if partition_name == "validation" and repeats != int(
        config["optimization_budget"]["terminal_runs_per_case"]
    ):
        raise ValueError("validation must use the preregistered terminal repeat count")
    if partition_name == "calibration":
        _reserve_calibration_calls(
            state=state,
            iteration=args.iteration,
            calls=len(_load_partition(control)["calibration"]["case_ids"]) * repeats,
            design=args.design,
            reason=args.change_reason,
            attribution=args.failure_attribution,
        )
    partition = _load_partition(control)
    corpus = BenchmarkCorpus.load(corpus_root, partition=partition_name)
    case_ids = _partition_case_ids(
        partition=partition, partition_name=partition_name, corpus=corpus
    )
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("evaluation output directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    codex_version = _codex_version()
    jobs = [(case_id, repeat) for case_id in case_ids for repeat in range(1, repeats + 1)]
    reviews: dict[str, dict[int, GaugeReview]] = defaultdict(dict)
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=int(config["runtime"]["concurrency"])
    ) as executor:
        futures = [
            executor.submit(
                _run_one,
                case_id=case_id,
                repeat=repeat,
                design=args.design,
                corpus=corpus,
                output=output,
                codex_version=codex_version,
                transport_retry_limit=int(config["runtime"]["transport_retry_limit"]),
            )
            for case_id, repeat in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            case_id, repeat, review, record = future.result()
            records.append(record)
            if review is not None:
                reviews[case_id][repeat] = review
    reviews_by_case = {
        case_id: tuple(by_repeat[index] for index in sorted(by_repeat))
        for case_id, by_repeat in reviews.items()
    }
    cases = [corpus.by_id[case_id] for case_id in case_ids]
    contract = _json(control / "scoring-contract.json")
    score = score_partition(
        cases=cases,
        reviews_by_case=reviews_by_case,
        contract=contract,
        required_runs=repeats,
    )
    manifest = {
        "experiment_version": "task075.qa-gauge-evaluation.v1",
        "partition": partition_name,
        "benchmark_version": corpus.benchmark_version,
        "iteration": args.iteration,
        "design": args.design,
        "change_reason": args.change_reason,
        "failure_attribution": args.failure_attribution,
        "repeat_count": repeats,
        "case_count": len(case_ids),
        "model_call_count": len(jobs),
        "codex_version": codex_version,
        "model": "Codex CLI default; no override",
        "scoring_contract_sha256": sha256(control / "scoring-contract.json"),
        "optimization_config_sha256": sha256(control / "optimization-config.json"),
        "partition_manifest_sha256": sha256(control / "partition-manifest.json"),
        "corpus_freeze_manifest_sha256": sha256(control / "corpus-freeze-manifest.json"),
        "records": sorted(records, key=lambda item: (item["case_id"], item["repeat"])),
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "score.json", score)
    print(
        json.dumps(
            {
                "partition": partition_name,
                "iteration": args.iteration,
                "design": args.design,
                "case_count": len(case_ids),
                "model_call_count": len(jobs),
                "metrics": score["metrics"],
                "all_thresholds_passed": score["all_thresholds_passed"],
                "invalid_cases": score["invalid_cases"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if partition_name == "validation":
        marker = _json(state / "validation-attempt.json")
        marker["completed_at_utc"] = datetime.now(UTC).isoformat()
        marker["output"] = str(output)
        marker["score_sha256"] = sha256(output / "score.json")
        marker["all_thresholds_passed"] = score["all_thresholds_passed"]
        marker["status"] = "complete"
        _write_json(state / "validation-attempt.json", marker)
    return 0


def finalize_interrupted(args: argparse.Namespace) -> int:
    """Score preserved completed outputs after a runner-level interruption, without reruns."""
    state = args.state.resolve()
    control = args.control.resolve()
    corpus_root = args.corpus.resolve()
    if _phase(state)["phase"] != "calibration":
        raise ValueError("interrupted calibration may be finalized only before freeze")
    _assert_frozen_inputs(control, corpus_root)
    output = args.output.resolve()
    if (output / "score.json").exists() or (output / "manifest.json").exists():
        raise ValueError("interrupted output was already finalized")
    partition = _load_partition(control)
    case_ids = list(partition["calibration"]["case_ids"])
    corpus = BenchmarkCorpus.load(corpus_root)
    reviews: dict[str, dict[int, GaugeReview]] = defaultdict(dict)
    records: list[dict[str, Any]] = []
    for case_id in case_ids:
        payload = corpus.reviewer_payload(case_id)
        allowed_locators = corpus.allowed_locators(case_id)
        for repeat in range(1, int(args.repeats) + 1):
            run_root = output / "runs" / case_id / f"repeat-{repeat:02d}"
            result_path = run_root / "output.json"
            record_path = run_root / "record.json"
            if result_path.exists():
                try:
                    reviews[case_id][repeat] = parse_gauge_review(
                        _json(result_path),
                        evaluation_id=str(payload["evaluation_id"]),
                        allowed_locators=allowed_locators,
                    )
                except ValueError:
                    pass
            if record_path.exists():
                records.append(_json(record_path))
            else:
                record = {
                    "case_id": case_id,
                    "repeat": repeat,
                    "design": args.design,
                    "fresh_context": True,
                    "output": (
                        str(result_path.relative_to(output)) if result_path.exists() else None
                    ),
                    "output_sha256": sha256(result_path) if result_path.exists() else None,
                    "invalid_reason": (
                        "runner interrupted while this Codex context was stalled; no rerun "
                        "permitted for baseline recovery"
                    ),
                    "recovered_without_rerun": True,
                }
                _write_json(record_path, record)
                records.append(record)
    reviews_by_case = {
        case_id: tuple(by_repeat[index] for index in sorted(by_repeat))
        for case_id, by_repeat in reviews.items()
    }
    score = score_partition(
        cases=[corpus.by_id[case_id] for case_id in case_ids],
        reviews_by_case=reviews_by_case,
        contract=_json(control / "scoring-contract.json"),
        required_runs=int(args.repeats),
    )
    manifest = {
        "experiment_version": "task075.qa-gauge-evaluation.v1",
        "partition": "calibration",
        "iteration": args.iteration,
        "design": args.design,
        "change_reason": args.change_reason,
        "failure_attribution": args.failure_attribution,
        "repeat_count": int(args.repeats),
        "case_count": len(case_ids),
        "model_call_count": len(case_ids) * int(args.repeats),
        "completed_review_count": sum(len(value) for value in reviews.values()),
        "recovered_after_runner_timeout": True,
        "rerun_count": 0,
        "scoring_contract_sha256": sha256(control / "scoring-contract.json"),
        "optimization_config_sha256": sha256(control / "optimization-config.json"),
        "partition_manifest_sha256": sha256(control / "partition-manifest.json"),
        "corpus_freeze_manifest_sha256": sha256(control / "corpus-freeze-manifest.json"),
        "records": sorted(records, key=lambda item: (item["case_id"], item["repeat"])),
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "score.json", score)
    print(
        json.dumps(
            {
                "completed_reviews": manifest["completed_review_count"],
                "invalid_cases": score["invalid_cases"],
                "metrics": score["metrics"],
                "all_thresholds_passed": score["all_thresholds_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _implementation_files(control: Path) -> list[Path]:
    provenance = sorted((control / "provenance/v1").glob("*.json"))
    return sorted((ROOT / "src/rfi/qa_gauge").glob("*.py")) + [
        ROOT / "scripts/task075_qa_gauge_experiment.py",
        control / "scoring-contract.json",
        control / "optimization-config.json",
        control / "benchmark-v2-resumption.json",
        control / "corpus-freeze-manifest.json",
        control / "quarantine-manifest.json",
        control / "partition-manifest.json",
    ] + provenance


def freeze_gauge(args: argparse.Namespace) -> int:
    state = args.state.resolve()
    control = args.control.resolve()
    phase = _phase(state)
    if phase["phase"] != "calibration":
        raise ValueError("QA gauge may be frozen exactly once")
    calibration = args.calibration.resolve()
    manifest = _json(calibration / "manifest.json")
    score = _json(calibration / "score.json")
    config = _json(control / "optimization-config.json")
    if manifest["partition"] != "calibration":
        raise ValueError("freeze requires calibration evidence")
    if int(manifest["repeat_count"]) != int(
        config["optimization_budget"]["terminal_runs_per_case"]
    ):
        raise ValueError("freeze requires the terminal three-run calibration assessment")
    if args.termination_reason == "success" and not score["all_thresholds_passed"]:
        raise ValueError("success freeze requires every calibration threshold")
    paths = _implementation_files(control)
    freeze = {
        "manifest_version": "task075.frozen-gauge.v1",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "design": manifest["design"],
        "termination_reason": args.termination_reason,
        "calibration_manifest": str(calibration / "manifest.json"),
        "calibration_manifest_sha256": sha256(calibration / "manifest.json"),
        "calibration_score": str(calibration / "score.json"),
        "calibration_score_sha256": sha256(calibration / "score.json"),
        "calibration_all_thresholds_passed": score["all_thresholds_passed"],
        "files": {
            str(path.relative_to(ROOT)): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in paths
        },
        "codex_version": manifest["codex_version"],
        "model": manifest["model"],
        "python": subprocess.run(
            [str(ROOT / ".venv/bin/python"), "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        ).stdout.strip(),
        "jsonschema": subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "-c",
                "import importlib.metadata; "
                "print(importlib.metadata.version('jsonschema'))",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        ).stdout.strip(),
        "mcp_access_changes": [],
        "mcp_access_disposition": (
            "No MCP was used: benchmark fixture authority and exact records are supplied "
            "through the general evidence-input contract."
        ),
        "post_freeze_tuning_permitted": False,
        "held_out_validation_attempt_limit": 1,
    }
    _write_json(args.freeze.resolve(), freeze)
    phase["phase"] = "frozen"
    phase["frozen_gauge_sha256"] = sha256(args.freeze.resolve())
    phase["frozen_at_utc"] = freeze["frozen_at_utc"]
    _write_json(_phase_path(state), phase)
    print(json.dumps(freeze, indent=2, sort_keys=True))
    return 0


def assert_frozen_gauge(control: Path, freeze_path: Path) -> None:
    freeze = _json(freeze_path)
    if freeze["manifest_version"] != "task075.frozen-gauge.v1":
        raise ValueError("unknown frozen-gauge manifest")
    expected_paths = {str(path.relative_to(ROOT)) for path in _implementation_files(control)}
    if set(freeze["files"]) != expected_paths:
        raise ValueError("frozen-gauge file inventory differs from current implementation")
    for relative, identity in freeze["files"].items():
        path = ROOT / relative
        if sha256(path) != identity["sha256"] or path.stat().st_size != identity["bytes"]:
            raise ValueError(f"post-freeze mutation detected: {relative}")


def verify_controls(args: argparse.Namespace) -> int:
    control = args.control.resolve()
    corpus = args.corpus.resolve()
    _assert_frozen_inputs(control, corpus)
    partition = _load_partition(control)
    quarantine = _json(control / "quarantine-manifest.json")
    if len(quarantine["cases"]) != 4:
        raise ValueError("quarantine does not contain exactly four cases")
    calibration = set(partition["calibration"]["case_ids"])
    validation_ids = partition["validation"].get("case_ids")
    if validation_ids is None:
        if len(calibration) != 44 or int(partition["validation"]["case_count"]) != 28:
            raise ValueError("benchmark v2 partition size failed")
        validation_count = int(partition["validation"]["case_count"])
    else:
        validation = set(validation_ids)
        if calibration.intersection(validation) or len(calibration) != 40 or len(validation) != 22:
            raise ValueError("partition disjointness or size failed")
        validation_count = len(validation)
    if args.freeze:
        assert_frozen_gauge(control, args.freeze.resolve())
    result = {
        "controls_valid": True,
        "objective_cases": len(calibration) + validation_count,
        "calibration_cases": len(calibration),
        "validation_cases": validation_count,
        "quarantined_cases": len(quarantine["cases"]),
        "freeze_valid": bool(args.freeze),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    value.add_argument("--control", type=Path, default=DEFAULT_CONTROL)
    value.add_argument("--state", type=Path, default=DEFAULT_STATE)
    subparsers = value.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    subparsers.add_parser("prepare-v2")
    for name in ("run-calibration", "run-validation"):
        run = subparsers.add_parser(name)
        run.add_argument("--output", type=Path, required=True)
        run.add_argument("--iteration", required=True)
        run.add_argument("--design", default=DESIGN_BASELINE)
        run.add_argument("--repeats", type=int, required=True)
        run.add_argument("--change-reason", required=True)
        run.add_argument("--failure-attribution", required=True)
        if name == "run-validation":
            run.add_argument("--freeze", type=Path, required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--calibration", type=Path, required=True)
    freeze.add_argument("--freeze", type=Path, required=True)
    freeze.add_argument(
        "--termination-reason", choices=("success", "budget", "stall"), required=True
    )
    verify = subparsers.add_parser("verify-controls")
    verify.add_argument("--freeze", type=Path)
    finalize = subparsers.add_parser("finalize-interrupted")
    finalize.add_argument("--output", type=Path, required=True)
    finalize.add_argument("--iteration", required=True)
    finalize.add_argument("--design", default=DESIGN_BASELINE)
    finalize.add_argument("--repeats", type=int, required=True)
    finalize.add_argument("--change-reason", required=True)
    finalize.add_argument("--failure-attribution", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "prepare":
        return prepare(args)
    if args.command == "prepare-v2":
        return prepare_v2(args)
    if args.command == "run-calibration":
        return _run_partition(args, "calibration")
    if args.command == "run-validation":
        return _run_partition(args, "validation")
    if args.command == "freeze":
        return freeze_gauge(args)
    if args.command == "verify-controls":
        return verify_controls(args)
    if args.command == "finalize-interrupted":
        return finalize_interrupted(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
