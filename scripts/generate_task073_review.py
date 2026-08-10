#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-073 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "tasks/TASK-073-implement-evaluate-minimal-read-only-rfi-mcp-transcript-surface.md"
PACKAGE = ROOT / ".artifacts/review/TASK-073"
ZIP_PATH = ROOT / ".artifacts/review/TASK-073-review.zip"
REPORT_PATH = ROOT / ".artifacts/review/TASK-073-review-report.json"
VALIDATION = ROOT / ".artifacts/task073-validation"
EXPERIMENT = ROOT / ".artifacts/task073-experiment"
STARTUP_FAILURE = ROOT / ".artifacts/task073-experiment-startup-failure"
TASK071 = ROOT / ".artifacts/task071-live-eval"
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


def experiment_members(root: Path, prefix: str) -> list[tuple[str, Path]]:
    """Return every preserved experiment file under one package prefix."""
    if not root.is_dir():
        return []
    return [
        (f"{prefix}/{path.relative_to(root).as_posix()}", path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def generate(base: str | None) -> int:
    """Validate the committed implementation and assemble the review package."""
    base_ref = base or "origin/main"
    dirty_only_for_operator_files = review_tree_is_commit_exact()
    outcomes = [
        run(
            "experiment-evidence",
            [
                ".venv/bin/python",
                "scripts/task073_review_evidence.py",
                "--state",
                str(TASK071),
                "--experiment",
                str(EXPERIMENT),
                "--task071",
                str(TASK071),
                "--output",
                str(VALIDATION),
            ],
        ),
        run("focused-regressions", ["make", "task073-test"]),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-073 validations failed")
    copied = [
        ("task-ticket.md", TICKET),
        ("completion/architectural-review.md", ROOT / "docs/TASK-073-review.md"),
        (
            "completion/codex-work-evaluation.md",
            ROOT / "docs/task073-codex-work-evaluation.md",
        ),
        (
            "design/TASK-072-mcp-surface-design.md",
            ROOT / "docs/rfi_mcp_surface_design.md",
        ),
        (
            "design/ADR-0028.md",
            ROOT / "docs/decisions/0028-agent-legible-rfi-mcp-boundary.md",
        ),
        ("implementation/artifact-contracts.py", ROOT / "src/rfi/artifacts/contracts.py"),
        ("implementation/artifact-service.py", ROOT / "src/rfi/artifacts/service.py"),
        ("implementation/mcp-contracts.py", ROOT / "src/rfi/mcp/contracts.py"),
        ("implementation/mcp-dictionary.py", ROOT / "src/rfi/mcp/dictionary.py"),
        ("implementation/mcp-access.py", ROOT / "src/rfi/mcp/access.py"),
        ("implementation/mcp-surface.py", ROOT / "src/rfi/mcp/surface.py"),
        ("implementation/mcp-server.py", ROOT / "src/rfi/mcp/server.py"),
        ("evidence/task073-tests.py", ROOT / "tests/test_task073.py"),
        (
            "evidence/codex-work-experiment-runner.py",
            ROOT / "scripts/task073_codex_work_experiment.py",
        ),
        (
            "evidence/experiment-evidence-verifier.py",
            ROOT / "scripts/task073_review_evidence.py",
        ),
        (
            "evaluation/experiment-evidence-summary.json",
            VALIDATION / "experiment-evidence-summary.json",
        ),
        ("evaluation/corpus-inventory.json", VALIDATION / "corpus-inventory.json"),
        ("comparison/task071-corpus.json", TASK071 / "corpus.json"),
        *(
            (f"comparison/task071-traces/{case}.json", TASK071 / "traces" / f"{case}.json")
            for case in CASES
        ),
        *(
            (f"comparison/task071-reports/{case}.json", TASK071 / "reports" / f"{case}.json")
            for case in CASES
        ),
        *experiment_members(EXPERIMENT, "experiment"),
        *experiment_members(STARTUP_FAILURE, "negative-control/startup-failure"),
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
        task_id="TASK-073",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
        allow_dirty=dirty_only_for_operator_files,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-073")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {
        **report,
        "zip": str(ZIP_PATH),
        "sha256": digest,
        "excluded_preexisting_operator_files": sorted(EXPECTED_OPERATOR_FILES),
        "independent_analysis_reference_available": False,
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
                verify_package(arguments.verify, expected_task_id="TASK-073"), indent=2
            )
        )
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
