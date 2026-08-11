#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-074 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "tasks/TASK-074-independent-qa-single-bounded-repair-loop.md"
PACKAGE = ROOT / ".artifacts/review/TASK-074"
ZIP_PATH = ROOT / ".artifacts/review/TASK-074-review.zip"
REPORT_PATH = ROOT / ".artifacts/review/TASK-074-review-report.json"
VALIDATION = ROOT / ".artifacts/task074-validation"
EVALUATION = ROOT / ".artifacts/task074-evaluation"
EXPERIMENT = ROOT / ".artifacts/task074-experiment"
STARTUP_FAILURE = ROOT / ".artifacts/task074-experiment-startup-failure"
TASK073 = ROOT / ".artifacts/task073-experiment"
TASK071 = ROOT / ".artifacts/task071-live-eval"
ADJUDICATION = ROOT / "docs/task074-finding-adjudication.json"
EXPECTED_OPERATOR_FILES = {"pull-results.txt", "pull_stx.py"}
CASES = ("sentiment", "demand", "technology", "chronology", "insufficient")


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
    """Run and retain one validation transcript."""
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
    """Permit only known operator scratch files outside the committed task range."""
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
    """Return every preserved file under one package prefix."""
    if not root.is_dir():
        raise RuntimeError(f"required evidence directory is missing: {root}")
    return [
        (f"{prefix}/{path.relative_to(root).as_posix()}", path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def task071_comparison_members() -> list[tuple[str, Path]]:
    """Include only reproducible TASK-071 comparison work products, not live state."""
    members = [("comparison/task071/corpus.json", TASK071 / "corpus.json")]
    for case in CASES:
        members.extend(
            (
                (
                    f"comparison/task071/reports/{case}.json",
                    TASK071 / "reports" / f"{case}.json",
                ),
                (
                    f"comparison/task071/traces/{case}.json",
                    TASK071 / "traces" / f"{case}.json",
                ),
            )
        )
    return members


def generate(base: str | None) -> int:
    """Validate the committed implementation and assemble the review package."""
    base_ref = base or "origin/main"
    dirty_only_for_operator_files = review_tree_is_commit_exact()
    outcomes = [
        run(
            "experiment-evidence",
            [
                ".venv/bin/python",
                "scripts/task074_review_evidence.py",
                "--experiment",
                str(EXPERIMENT),
                "--source",
                str(TASK073),
                "--adjudication",
                str(ADJUDICATION),
                "--startup-failure",
                str(STARTUP_FAILURE),
                "--output",
                str(EVALUATION),
            ],
        ),
        run("focused-regressions", ["make", "task074-test"]),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-074 validations failed")
    copied = [
        ("task-ticket.md", TICKET),
        ("completion/architectural-review.md", ROOT / "docs/TASK-074-review.md"),
        (
            "completion/qa-repair-evaluation.md",
            ROOT / "docs/task074-qa-repair-evaluation.md",
        ),
        ("evaluation/finding-adjudication.json", ADJUDICATION),
        (
            "evaluation/experiment-evidence-summary.json",
            EVALUATION / "experiment-evidence-summary.json",
        ),
        (
            "evaluation/finding-resolution-matrix.json",
            EVALUATION / "finding-resolution-matrix.json",
        ),
        ("architecture/current-state.md", ROOT / "docs/current-state.md"),
        ("architecture/TASKS.md", ROOT / "TASKS.md"),
        ("implementation/contracts.py", ROOT / "src/rfi/investigation_qa/contracts.py"),
        (
            "implementation/orchestration.py",
            ROOT / "src/rfi/investigation_qa/orchestration.py",
        ),
        ("implementation/prompts.py", ROOT / "src/rfi/investigation_qa/prompts.py"),
        ("implementation/__init__.py", ROOT / "src/rfi/investigation_qa/__init__.py"),
        ("evidence/task074-tests.py", ROOT / "tests/test_task074.py"),
        (
            "evidence/qa-repair-experiment-runner.py",
            ROOT / "scripts/task074_qa_repair_experiment.py",
        ),
        (
            "evidence/experiment-evidence-verifier.py",
            ROOT / "scripts/task074_review_evidence.py",
        ),
        (
            "evidence/review-package-generator.py",
            ROOT / "scripts/generate_task074_review.py",
        ),
        *tree_members(TASK073, "fixed-input/task073-experiment"),
        *task071_comparison_members(),
        *tree_members(EXPERIMENT, "experiment"),
        *tree_members(STARTUP_FAILURE, "negative-control/startup-failure"),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "experiment-evidence",
                "focused-regressions",
                "committed-diff-check",
                "full-validation",
            )
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-074",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
        allow_dirty=dirty_only_for_operator_files,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-074")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {
        **report,
        "zip": str(ZIP_PATH),
        "sha256": digest,
        "excluded_preexisting_operator_files": sorted(EXPECTED_OPERATOR_FILES),
        "fixed_task073_investigations_rerun": False,
        "repair_cycle_limit": 1,
    }
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    arguments = parser.parse_args()
    if arguments.verify:
        print(
            json.dumps(
                verify_package(arguments.verify, expected_task_id="TASK-074"),
                indent=2,
            )
        )
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
