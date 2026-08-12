#!/usr/bin/env python3
"""Generate or verify the commit-aware TASK-075 frozen-calibration review package."""

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
VALIDATION = ROOT / ".artifacts/task075-validation"
EVALUATION = ROOT / ".artifacts/task075-evaluation"
CORPUS = ROOT / "benchmarks/rfi_qa_candidates_v2"
CONTROL = ROOT / "experiments/task075"
STATE = ROOT / ".artifacts/task075-v2-control"
V2_CALIBRATION = ROOT / ".artifacts/task075-v2-calibration"
V1_CONTROL = ROOT / ".artifacts/task075-control"
V1_CALIBRATION = ROOT / ".artifacts/task075-calibration"
EXPECTED_OPERATOR_FILES = {"pull-results.txt", "pull_stx.py"}


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


def generate(base: str | None) -> int:
    """Verify the committed freeze checkpoint and assemble its review package."""
    base_ref = base or "origin/main"
    dirty_only_for_operator_files = review_tree_is_commit_exact()
    outcomes = [
        run(
            "experiment-evidence",
            [
                ".venv/bin/python",
                "scripts/task075_review_evidence.py",
                "--corpus",
                str(CORPUS),
                "--control",
                str(CONTROL),
                "--state",
                str(STATE),
                "--calibration",
                str(V2_CALIBRATION),
                "--output",
                str(EVALUATION),
            ],
        ),
        run(
            "visible-benchmark-validator",
            [
                ".venv/bin/python",
                "benchmarks/rfi_qa_candidates_v2/validate_candidates.py",
                "--visible",
            ],
        ),
        run(
            "frozen-controls",
            [
                ".venv/bin/python",
                "scripts/task075_qa_gauge_experiment.py",
                "--corpus",
                str(CORPUS),
                "--state",
                str(STATE),
                "verify-controls",
                "--freeze",
                str(CONTROL / "frozen-gauge-manifest.json"),
            ],
        ),
        run("focused-regressions", ["make", "task075-test"]),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-075 validations failed")
    copied = [
        ("task-ticket.md", TICKET),
        ("completion/architectural-review.md", ROOT / "docs/TASK-075-review.md"),
        (
            "completion/qa-gauge-evaluation.md",
            ROOT / "docs/task075-qa-gauge-evaluation.md",
        ),
        (
            "architecture/rfi-mcp-surface-design.md",
            ROOT / "docs/design/rfi_mcp_surface_design.md",
        ),
        ("architecture/current-state.md", ROOT / "docs/current-state.md"),
        ("architecture/TASKS.md", ROOT / "TASKS.md"),
        ("implementation/Makefile", ROOT / "Makefile"),
        ("evidence/task075-tests.py", ROOT / "tests/test_task075.py"),
        (
            "evidence/qa-gauge-experiment-runner.py",
            ROOT / "scripts/task075_qa_gauge_experiment.py",
        ),
        (
            "evidence/experiment-evidence-verifier.py",
            ROOT / "scripts/task075_review_evidence.py",
        ),
        (
            "evidence/review-package-generator.py",
            ROOT / "scripts/generate_task075_review.py",
        ),
        (
            "evaluation/experiment-evidence-summary.json",
            EVALUATION / "experiment-evidence-summary.json",
        ),
        *tree_members(CORPUS, "benchmark/v2-visible"),
        *tree_members(CONTROL, "controls"),
        *tree_members(ROOT / "src/rfi/qa_gauge", "implementation/qa-gauge"),
        *tree_members(V1_CONTROL, "provenance/v1-control"),
        *tree_members(V1_CALIBRATION, "provenance/v1-calibration"),
        *tree_members(STATE, "experiment/v2-state"),
        *tree_members(V2_CALIBRATION, "experiment/v2-calibration"),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "experiment-evidence",
                "visible-benchmark-validator",
                "frozen-controls",
                "focused-regressions",
                "committed-diff-check",
                "full-validation",
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
        "checkpoint": "frozen calibration; held-out validation not attempted",
        "excluded_preexisting_operator_files": sorted(EXPECTED_OPERATOR_FILES),
        "held_out_validation_included": False,
        "post_freeze_tuning": False,
    }
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
        print(
            json.dumps(
                verify_package(arguments.verify, expected_task_id="TASK-075"),
                indent=2,
            )
        )
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
