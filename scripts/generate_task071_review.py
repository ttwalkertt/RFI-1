#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-071 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
TICKET = (
    ROOT
    / "tasks/TASK-071-retained-truth-access-and-transcript-investigation-vertical-slice.md"
)
PACKAGE = ROOT / ".artifacts/review/TASK-071"
ZIP_PATH = ROOT / ".artifacts/review/TASK-071-review.zip"
VALIDATION = ROOT / ".artifacts/task071-validation"
LIVE_STATE = ROOT / ".artifacts/task071-live-eval"
TRACES = LIVE_STATE / "traces"
REPORTS = LIVE_STATE / "reports"
REPORT_PATH = ROOT / ".artifacts/review/TASK-071-review-report.json"
EXPECTED_OPERATOR_FILES = {"pull-results.txt", "pull_stx.py"}


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
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def review_tree_is_commit_exact() -> bool:
    """Permit only two known pre-existing operator scratch files outside task scope."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    lines = [line for line in result.stdout.splitlines() if line]
    unexpected = [
        line for line in lines
        if not (line.startswith("?? ") and line[3:] in EXPECTED_OPERATOR_FILES)
    ]
    if unexpected:
        raise RuntimeError(
            "review generation found task changes outside the committed range: "
            + ", ".join(unexpected)
        )
    return bool(lines)


def generate(base: str | None) -> int:
    """Validate the committed task range and assemble its review package."""
    base_ref = base or "origin/main"
    dirty_only_for_operator_files = review_tree_is_commit_exact()
    outcomes = [
        run(
            "research-report-generation",
            [
                ".venv/bin/python",
                "scripts/task071_emit_reports.py",
                "--traces",
                str(TRACES),
                "--reports",
                str(REPORTS),
            ],
        ),
        run(
            "retained-corpus-and-traces",
            [
                ".venv/bin/python",
                "scripts/task071_review_evidence.py",
                "--state",
                str(LIVE_STATE),
                "--traces",
                str(TRACES),
                "--reports",
                str(REPORTS),
                "--output",
                str(VALIDATION),
            ],
        ),
        run("focused-regressions", ["make", "task071-test"]),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-071 validations failed")
    copied = [
        (
            "task-ticket.md",
            TICKET,
        ),
        ("completion/architectural-review.md", ROOT / "docs/TASK-071-review.md"),
        (
            "completion/retained-truth-catalog.md",
            ROOT / "docs/TASK-071-retained-truth-catalog.md",
        ),
        (
            "completion/vertical-slice.md",
            ROOT / "docs/transcript-investigation-vertical-slice.md",
        ),
        (
            "completion/architectural-decision.md",
            ROOT / "docs/decisions/0027-retained-truth-transcript-investigation-boundary.md",
        ),
        ("evidence/task071-tests.py", ROOT / "tests/test_task071.py"),
        ("evidence/research-contracts.py", ROOT / "src/rfi/research/contracts.py"),
        ("evidence/research-report-writer.py", ROOT / "src/rfi/research/reporting.py"),
        ("evidence/transcript-access.py", ROOT / "src/rfi/research/access.py"),
        ("evidence/closed-record-adjudication.py", ROOT / "src/rfi/research/adjudication.py"),
        ("evidence/investigation-harness.py", ROOT / "src/rfi/research/harness.py"),
        ("evidence/openai-adapter.py", ROOT / "src/rfi/research/openai.py"),
        ("evidence/headless-operator.py", ROOT / "scripts/task071_investigate.py"),
        ("evidence/report-emitter.py", ROOT / "scripts/task071_emit_reports.py"),
        ("evidence/review-evidence.py", ROOT / "scripts/task071_review_evidence.py"),
        ("evaluation/retained-corpus.json", VALIDATION / "retained-corpus.json"),
        ("evaluation/access-probes.json", VALIDATION / "access-probes.json"),
        (
            "evaluation/vertical-slice-evaluation.json",
            VALIDATION / "vertical-slice-evaluation.json",
        ),
        *(
            (f"evaluation/traces/{case}.json", TRACES / f"{case}.json")
            for case in ("sentiment", "demand", "technology", "chronology", "insufficient")
        ),
        *(
            (f"evaluation/reports/{case}.json", REPORTS / f"{case}.json")
            for case in ("sentiment", "demand", "technology", "chronology", "insufficient")
        ),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "retained-corpus-and-traces",
                "research-report-generation",
                "focused-regressions",
                "committed-diff-check",
                "full-validation",
            )
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-071",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
        allow_dirty=dirty_only_for_operator_files,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-071")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {
        **report,
        "zip": str(ZIP_PATH),
        "sha256": digest,
        "excluded_preexisting_operator_files": sorted(EXPECTED_OPERATOR_FILES),
    }
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    """Generate or verify one TASK-071 package."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    arguments = parser.parse_args()
    if arguments.verify:
        print(json.dumps(
            verify_package(arguments.verify, expected_task_id="TASK-071"), indent=2
        ))
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
