#!/usr/bin/env python3
"""Verify the frozen TASK-075 V3 pre-verification evidence checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from rfi.qa_gauge import BenchmarkCorpus, GaugeReview, parse_gauge_review, score_partition
from rfi.qa_gauge.prompts import prompt_for_design

PromptRenderer = Callable[[str, dict[str, Any]], str]
CANDIDATE_DESIGN = "task075.causal-admission-gauge-v4"
CANDIDATE_SOURCE_SHA256 = (
    "478d077444d17ef15d1071bbce6aeac133b2ce1e0f1e5bbf55fc3f0bd2ff2b3a"
)


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


def candidate_renderer(path: Path) -> PromptRenderer:
    """Load the rejected candidate renderer preserved from its implementation commit."""
    if digest(path) != CANDIDATE_SOURCE_SHA256:
        raise ValueError("rejected candidate prompt source differs from commit 52040de")
    namespace: dict[str, Any] = {"__name__": "task075_candidate_prompts"}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    renderer = namespace.get("prompt_for_design")
    if not callable(renderer):
        raise ValueError("candidate prompt source lacks prompt_for_design")
    return renderer


def verify_record(
    *,
    experiment: Path,
    record: dict[str, Any],
    corpus: BenchmarkCorpus,
    renderer: PromptRenderer,
) -> tuple[dict[str, int], GaugeReview | None]:
    """Verify one preserved judgment record and its reference-free prompt."""
    for field in ("prompt", "schema", "events", "stderr"):
        path = experiment / str(record[field])
        if not path.is_file():
            raise ValueError(f"missing {field}: {path}")
        digest_field = f"{field}_sha256"
        if digest_field in record and digest(path) != record[digest_field]:
            raise ValueError(f"changed {field}: {path}")
    case_id = str(record["case_id"])
    expected_prompt = renderer(str(record["design"]), corpus.reviewer_payload(case_id))
    prompt_path = experiment / str(record["prompt"])
    if prompt_path.read_text(encoding="utf-8") != expected_prompt:
        raise ValueError(f"prompt projection changed: {case_id}/{record['repeat']}")
    review: GaugeReview | None = None
    output_name = record.get("output")
    if output_name:
        output_path = experiment / str(output_name)
        if digest(output_path) != record["output_sha256"]:
            raise ValueError(f"changed output: {output_path}")
        projected = corpus.reviewer_payload(case_id)
        review = parse_gauge_review(
            load(output_path),
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
    renderer: PromptRenderer,
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
    expected_records = len(case_ids) * int(manifest["repeat_count"])
    if len(manifest["records"]) != expected_records:
        raise ValueError(f"logical record count differs: {path}")
    totals = {"attempts": 0, "timeouts": 0, "threads": 0, "invalid": 0, "retried": 0}
    reviews: dict[str, dict[int, GaugeReview]] = defaultdict(dict)
    seen: set[tuple[str, int]] = set()
    for record in manifest["records"]:
        key = (str(record["case_id"]), int(record["repeat"]))
        if key in seen:
            raise ValueError(f"duplicate judgment record: {key}")
        seen.add(key)
        counts, review = verify_record(
            experiment=path,
            record=record,
            corpus=corpus,
            renderer=renderer,
        )
        for field, value in counts.items():
            totals[field] += value
        if review is not None:
            reviews[key[0]][key[1]] = review
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
    if json.loads(json.dumps(reconstructed)) != score:
        raise ValueError(f"deterministic rescore differs from preserved score: {path}")
    if score["metrics"] != identity["metrics"]:
        raise ValueError(f"history metrics differ from preserved score: {path}")
    return {
        "iteration": manifest["iteration"],
        "partition": partition,
        "design": manifest["design"],
        "logical_judgments": manifest["model_call_count"],
        "transport_invocations": totals["attempts"],
        "retried_judgments": totals["retried"],
        "timed_out_invocations": totals["timeouts"],
        "thread_started_events": totals["threads"],
        "invalid_judgments": totals["invalid"],
        "all_thresholds_passed": score["all_thresholds_passed"],
        "metrics": score["metrics"],
        "manifest_sha256": digest(manifest_path),
        "score_sha256": digest(score_path),
    }


def verify_frozen_files(root: Path, freeze: dict[str, Any]) -> None:
    """Verify every file named by the immutable frozen-gauge inventory."""
    for relative, identity in freeze["files"].items():
        path = root / relative
        if not path.is_file() or digest(path) != identity["sha256"]:
            raise ValueError(f"frozen gauge file differs: {relative}")
        if path.stat().st_size != identity["bytes"]:
            raise ValueError(f"frozen gauge file size differs: {relative}")


def main() -> int:
    """Verify V3 controls, trajectory, regression, freeze, and held-out absence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--v2-corpus", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--regression", type=Path, required=True)
    parser.add_argument("--candidate-prompts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    corpus_root = arguments.corpus.resolve()
    v2_root = arguments.v2_corpus.resolve()
    control = arguments.control.resolve()
    state = arguments.state.resolve()
    calibration = arguments.calibration.resolve()
    regression = arguments.regression.resolve()

    held_out_paths = (
        corpus_root / "verification/cases.jsonl",
        corpus_root / "verification/fixtures.json",
    )
    if any(path.exists() for path in held_out_paths):
        raise ValueError("V3 held-out verification content is present before human restoration")
    calibration_corpus = BenchmarkCorpus.load(corpus_root, partition="calibration")
    quarantine_corpus = BenchmarkCorpus.load(corpus_root, partition="quarantine")
    v2_regression_corpus = BenchmarkCorpus.load(v2_root, partition="validation")
    if len(calibration_corpus.cases) != 80 or len(quarantine_corpus.cases) != 6:
        raise ValueError("V3 visible population differs from the frozen split")
    if len(v2_regression_corpus.cases) != 28:
        raise ValueError("known V2 regression population differs from 28 cases")

    freeze_path = control / "frozen-gauge-manifest.json"
    freeze = load(freeze_path)
    history = load(control / "calibration-history.json")
    corpus_freeze = load(control / "corpus-freeze-manifest.json")
    partition = load(control / "partition-manifest.json")
    contract = load(control / "scoring-contract.json")
    phase = load(state / "phase.json")
    ledger = load(state / "calibration-ledger.json")
    freeze_sha256 = digest(freeze_path)
    if phase["phase"] != "frozen" or phase["held_out_attempted"]:
        raise ValueError("V3 phase is not a pristine frozen pre-verification checkpoint")
    if phase["held_out_files_present"] or (state / "held-out-attempt.json").exists():
        raise ValueError("held-out attempt state exists before authorized verification")
    if phase["frozen_gauge_sha256"] != freeze_sha256:
        raise ValueError("phase marker does not identify the frozen gauge")
    if freeze["post_freeze_tuning_permitted"] or freeze["mcp_access_changes"]:
        raise ValueError("freeze does not preserve the no-tuning/no-MCP-change boundary")
    if freeze["calibration_all_thresholds_passed"]:
        raise ValueError("negative terminal calibration result was not preserved")
    verify_frozen_files(root, freeze)
    if ledger["model_calls_reserved"] != 400 or ledger["maximum_calibration_model_calls"] != 400:
        raise ValueError("V3 calibration accounting differs from preregistration")
    if len(ledger["iterations"]) != 3:
        raise ValueError("V3 ledger does not preserve every planned assessment")
    if partition["verification"]["case_ids"] is not None:
        raise ValueError("held-out case identities leaked into the V3 control manifest")
    if not partition["verification"]["physically_absent"]:
        raise ValueError("partition manifest does not require physical held-out absence")
    if history["verification"] is not None:
        raise ValueError("history contains a held-out result before restoration")
    if history["optimization_termination"]["held_out_verification_observed"]:
        raise ValueError("history says held-out truth was observed")
    for relative, identity in corpus_freeze["visible_files"].items():
        path = corpus_root / relative
        if not path.is_file() or digest(path) != identity["sha256"]:
            raise ValueError(f"visible benchmark file differs: {relative}")
    for relative, identity in corpus_freeze["held_out_files"].items():
        if identity["sha256"] not in {
            "8184454d4cfbec057b41fc2d460fc8cf1eb9a1174200be8ca9cc3f10d166a257",
            "a637f1dd86aebee72d435acf112f9a0014573ba99bcfc0fffa5d0703c8fd0b94",
        }:
            raise ValueError(f"held-out hash commitment differs: {relative}")

    rejected_renderer = candidate_renderer(arguments.candidate_prompts.resolve())
    calibration_case_ids = list(partition["calibration"]["case_ids"])
    v3_paths = [calibration / entry["iteration"] for entry in history["v3_iterations"]]
    verified_calibration = []
    for path, identity in zip(v3_paths, history["v3_iterations"], strict=True):
        renderer = (
            rejected_renderer
            if identity["design"] == CANDIDATE_DESIGN
            else prompt_for_design
        )
        verified_calibration.append(
            verify_experiment(
                path=path,
                corpus=calibration_corpus,
                identity=identity,
                partition="calibration",
                case_ids=calibration_case_ids,
                contract=contract,
                renderer=renderer,
            )
        )
    regression_identity = history["v2_regressions"][0]
    verified_regression = verify_experiment(
        path=regression,
        corpus=v2_regression_corpus,
        identity=regression_identity,
        partition="v2-known-regression",
        case_ids=sorted(v2_regression_corpus.by_id),
        contract=contract,
        renderer=prompt_for_design,
    )
    candidate = history["v3_iterations"][1]
    consequences = candidate["predicted_consequence_assessment"]
    if any(
        (
            consequences["unsupported_findings_decrease"],
            consequences["class_attribution_improves"],
            consequences["indeterminate_handling_preserved_or_improved"],
            consequences["matched_pair_discrimination_improves"],
        )
    ):
        raise ValueError("candidate-quality rejection rationale differs from the observed metrics")
    if history["terminal_selection"]["runtime_characteristics_used_for_selection"]:
        raise ValueError("runtime characteristics improperly influenced candidate selection")

    summary = {
        "result": "PASS",
        "meaning": (
            "frozen V3 calibration/regression evidence integrity before held-out restoration"
        ),
        "benchmark_version": calibration_corpus.benchmark_version,
        "calibration_cases": len(calibration_corpus.cases),
        "verification_cases_committed": 40,
        "verification_files_physically_absent": True,
        "verification_attempted": False,
        "quarantine_cases": len(quarantine_corpus.cases),
        "calibration_model_judgments_reserved": ledger["model_calls_reserved"],
        "freeze_sha256": freeze_sha256,
        "frozen_design": freeze["design"],
        "post_freeze_tuning": False,
        "mcp_access_changes": freeze["mcp_access_changes"],
        "candidate_selection_basis": "gauge quality; runtime and prompt length secondary only",
        "candidate_predicted_consequences": consequences,
        "calibration": verified_calibration,
        "terminal_calibration_passed": False,
        "v2_known_regression": verified_regression,
        "material_v2_regression": regression_identity["comparison_to_prior_v2_measurement"][
            "material_regression"
        ],
        "architectural_disposition": history["architectural_disposition"],
        "next_required_action": (
            "Human operator restores exact V3 verification files and confirms preregistered "
            "hashes; then run the frozen gauge exactly once."
        ),
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "experiment-evidence-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
