#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-070 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-070"
ZIP_PATH = ROOT / ".artifacts/review/TASK-070-review.zip"
VALIDATION = ROOT / ".artifacts/task070-validation"
REPORT_PATH = ROOT / ".artifacts/review/TASK-070-review-report.json"


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
    """Run and retain one deterministic validation transcript."""
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
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n"
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def generate(base: str | None) -> int:
    """Validate the committed task range and assemble its review package."""
    base_ref = base or "origin/main"
    outcomes = [
        run(
            "deterministic-evidence",
            [
                ".venv/bin/python",
                "scripts/task070_review_evidence.py",
                "--output",
                str(VALIDATION),
            ],
        ),
        run("focused-regressions", ["make", "task070-test"]),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-070 validations failed")
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-070-classify-management-transcripts.md",
        ),
        ("completion/architectural-review.md", ROOT / "docs/TASK-070-review.md"),
        ("evidence/task070-tests.py", ROOT / "tests/test_task070.py"),
        (
            "evidence/transcript-classification.py",
            ROOT / "src/rfi/acquisition/transcript_classification.py",
        ),
        ("evidence/acquisition-contracts.py", ROOT / "src/rfi/acquisition/contracts.py"),
        ("evidence/acquisition-engine.py", ROOT / "src/rfi/acquisition/engine.py"),
        ("evidence/acquisition-repository.py", ROOT / "src/rfi/acquisition/repository.py"),
        ("evidence/artifact-service.py", ROOT / "src/rfi/artifacts/service.py"),
        ("evidence/pull-workflow.py", ROOT / "src/rfi/pull/workflow.py"),
        (
            "evidence/deterministic-evidence.py",
            ROOT / "scripts/task070_review_evidence.py",
        ),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "deterministic-evidence",
                "focused-regressions",
                "committed-diff-check",
                "full-validation",
            )
        ),
        (
            "validation/classification-and-retention.json",
            VALIDATION / "classification-and-retention.json",
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-070",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-070")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n"
    )
    package_report = {**report, "zip": str(ZIP_PATH), "sha256": digest}
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    """Generate or verify one TASK-070 package."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    arguments = parser.parse_args()
    if arguments.verify:
        print(json.dumps(
            verify_package(arguments.verify, expected_task_id="TASK-070"), indent=2
        ))
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
