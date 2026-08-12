#!/usr/bin/env python3
"""Generate or verify the commit-aware TASK-075 frozen pre-verification package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "tasks/TASK-075-establish-qa-gauge-capability-through-rbf-optimization-v2.md"
PACKAGE = ROOT / ".artifacts/review/TASK-075"
ZIP_PATH = ROOT / ".artifacts/review/TASK-075-review.zip"
REPORT_PATH = ROOT / ".artifacts/review/TASK-075-review-report.json"
VALIDATION = ROOT / ".artifacts/task075-v3-validation"
EVALUATION = ROOT / ".artifacts/task075-v3-evaluation"
V3_CORPUS = ROOT / "benchmarks/rfi_qa_candidates_v3"
V2_CORPUS = ROOT / "benchmarks/rfi_qa_candidates_v2"
V3_CONTROL = ROOT / "experiments/task075/v3"
ALL_CONTROL = ROOT / "experiments/task075"
V3_STATE = ROOT / ".artifacts/task075-v3-control"
V3_CALIBRATION = ROOT / ".artifacts/task075-v3-calibration"
V3_REGRESSION = ROOT / ".artifacts/task075-v3-regression/v2-final-selected-design"
V2_STATE = ROOT / ".artifacts/task075-v2-control"
V2_CALIBRATION = ROOT / ".artifacts/task075-v2-calibration"
V2_VALIDATION = ROOT / ".artifacts/task075-v2-validation"
V1_STATE = ROOT / ".artifacts/task075-control"
V1_CALIBRATION = ROOT / ".artifacts/task075-calibration"
CANDIDATE_COMMIT = "52040de"
CANDIDATE_PATH = "src/rfi/qa_gauge/prompts.py"
CANDIDATE_SHA256 = "478d077444d17ef15d1071bbce6aeac133b2ce1e0f1e5bbf55fc3f0bd2ff2b3a"
EXPECTED_OPERATOR_FILES = {"pull-results.txt", "pull_stx.py"}
EXPECTED_FROZEN_FORMAT_FAILURES = {
    "src/rfi/qa_gauge/benchmark.py:45: line exceeds 100 characters",
    "src/rfi/qa_gauge/benchmark.py:617: line exceeds 100 characters",
}


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
    """Run and preserve one review validation transcript."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    target = VALIDATION / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def preserve_candidate_source() -> Path:
    """Preserve the rejected material candidate implementation from its commit."""
    result = subprocess.run(
        ["git", "show", f"{CANDIDATE_COMMIT}:{CANDIDATE_PATH}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if hashlib.sha256(result.stdout).hexdigest() != CANDIDATE_SHA256:
        raise RuntimeError("candidate source identity differs from the recorded commit")
    target = EVALUATION / "rejected-causal-admission-v4-prompts.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.stdout)
    return target


def review_tree_is_commit_exact() -> bool:
    """Permit only the two known operator scratch files outside the commit."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    lines = [line for line in result.stdout.splitlines() if line]
    unexpected = [
        line
        for line in lines
        if not (line.startswith("?? ") and line[3:] in EXPECTED_OPERATOR_FILES)
    ]
    if unexpected:
        raise RuntimeError(
            "review generation found task changes outside the committed range: "
            + ", ".join(unexpected)
        )
    return bool(lines)


def tree_members(root: Path, prefix: str) -> list[tuple[str, Path]]:
    """Return all preserved files below one package prefix."""
    if not root.is_dir():
        raise RuntimeError(f"required evidence directory is missing: {root}")
    return [
        (f"{prefix}/{path.relative_to(root).as_posix()}", path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def full_validation_has_only_frozen_format_debt() -> bool:
    """Recognize only the two freeze-locked line-length failures."""
    transcript = (VALIDATION / "full-validation.txt").read_text(encoding="utf-8")
    observed = {
        line.strip()
        for line in transcript.splitlines()
        if "line exceeds 100 characters" in line
    }
    return observed == EXPECTED_FROZEN_FORMAT_FAILURES and "exit_code: 2" in transcript


def generate(base: str | None) -> int:
    """Verify and package the frozen negative calibration checkpoint."""
    base_ref = base or "origin/main"
    dirty_only_for_operator_files = review_tree_is_commit_exact()
    candidate_source = preserve_candidate_source()
    outcomes = [
        run(
            "experiment-evidence",
            [
                ".venv/bin/python",
                "scripts/task075_review_evidence.py",
                "--root",
                str(ROOT),
                "--corpus",
                str(V3_CORPUS),
                "--v2-corpus",
                str(V2_CORPUS),
                "--control",
                str(V3_CONTROL),
                "--state",
                str(V3_STATE),
                "--calibration",
                str(V3_CALIBRATION),
                "--regression",
                str(V3_REGRESSION),
                "--candidate-prompts",
                str(candidate_source),
                "--output",
                str(EVALUATION),
            ],
        ),
        run(
            "visible-benchmark-validator",
            [
                ".venv/bin/python",
                "benchmarks/rfi_qa_candidates_v3/validate_candidates.py",
                "--visible",
            ],
        ),
        run(
            "frozen-controls",
            [
                ".venv/bin/python",
                "scripts/task075_qa_gauge_experiment.py",
                "--corpus",
                str(V3_CORPUS),
                "--control",
                str(V3_CONTROL),
                "--state",
                str(V3_STATE),
                "verify-controls",
                "--freeze",
                str(V3_CONTROL / "frozen-gauge-manifest.json"),
            ],
        ),
        run("focused-regressions", ["make", "task075-test"]),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        run("full-validation", ["make", "validate"], timeout=3600),
        run(
            "remaining-validation-after-frozen-format",
            [
                "make",
                "typecheck",
                "import-check",
                "docs-check",
                "baseline-check",
                "build",
            ],
        ),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    unexpected_failures = [
        item
        for item in outcomes
        if item["exit_code"] and item["name"] != "full-validation"
    ]
    if unexpected_failures:
        raise RuntimeError("one or more TASK-075 validations failed")
    full_validation = next(item for item in outcomes if item["name"] == "full-validation")
    if full_validation["exit_code"] and not full_validation_has_only_frozen_format_debt():
        raise RuntimeError("full validation failed for reasons beyond frozen formatting debt")
    copied = [
        ("task-ticket.md", TICKET),
        ("completion/architectural-review.md", ROOT / "docs/TASK-075-review.md"),
        ("completion/qa-gauge-evaluation.md", ROOT / "docs/task075-qa-gauge-evaluation.md"),
        ("architecture/rfi-mcp-surface-design.md", ROOT / "docs/design/rfi_mcp_surface_design.md"),
        ("architecture/current-state.md", ROOT / "docs/current-state.md"),
        ("architecture/design-baseline.json", ROOT / "docs/design-baseline.json"),
        ("architecture/TASKS.md", ROOT / "TASKS.md"),
        ("implementation/Makefile", ROOT / "Makefile"),
        ("evidence/task075-tests.py", ROOT / "tests/test_task075.py"),
        ("evidence/qa-gauge-experiment-runner.py", ROOT / "scripts/task075_qa_gauge_experiment.py"),
        ("evidence/experiment-evidence-verifier.py", ROOT / "scripts/task075_review_evidence.py"),
        ("evidence/review-package-generator.py", ROOT / "scripts/generate_task075_review.py"),
        (
            "evaluation/experiment-evidence-summary.json",
            EVALUATION / "experiment-evidence-summary.json",
        ),
        ("evaluation/rejected-causal-admission-v4-prompts.py", candidate_source),
        *tree_members(V3_CORPUS, "benchmark/v3-visible"),
        *tree_members(V2_CORPUS, "benchmark/v2-known-regression"),
        *tree_members(ALL_CONTROL, "controls"),
        *tree_members(ROOT / "src/rfi/qa_gauge", "implementation/qa-gauge"),
        *tree_members(V1_STATE, "provenance/v1-state"),
        *tree_members(V1_CALIBRATION, "provenance/v1-calibration"),
        *tree_members(V2_STATE, "provenance/v2-state"),
        *tree_members(V2_CALIBRATION, "provenance/v2-calibration"),
        *tree_members(V2_VALIDATION, "provenance/v2-held-out-validation"),
        *tree_members(V3_STATE, "experiment/v3-state"),
        *tree_members(V3_CALIBRATION, "experiment/v3-calibration"),
        *tree_members(V3_REGRESSION, "experiment/v2-known-regression-final"),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "experiment-evidence",
                "visible-benchmark-validator",
                "frozen-controls",
                "focused-regressions",
                "committed-diff-check",
                "full-validation",
                "remaining-validation-after-frozen-format",
            )
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-075",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
        allow_dirty=dirty_only_for_operator_files,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-075")
    zip_digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{zip_digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {
        **report,
        "zip": str(ZIP_PATH),
        "sha256": zip_digest,
        "checkpoint": "frozen V3 negative calibration; awaiting held-out restoration",
        "excluded_preexisting_operator_files": sorted(EXPECTED_OPERATOR_FILES),
        "held_out_validation_included": False,
        "held_out_validation_attempted": False,
        "held_out_files_physically_absent": True,
        "terminal_calibration_passed": False,
        "material_v2_regression": True,
        "full_validation_passed": False,
        "full_validation_limitation": (
            "The format check reports two pre-freeze overlong lines in the immutable QA "
            "benchmark loader; all other focused and full validation stages passed."
        ),
        "fresh_live_transfer_attempted": False,
        "post_freeze_tuning": False,
    }
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    """Dispatch package generation or standalone verification."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    arguments = parser.parse_args()
    if arguments.verify:
        print(json.dumps(verify_package(arguments.verify, expected_task_id="TASK-075"), indent=2))
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
