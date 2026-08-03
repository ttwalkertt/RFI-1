#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-062 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-062"
ZIP_PATH = ROOT / ".artifacts/review/TASK-062-review.zip"
VALIDATION = ROOT / ".artifacts/task062-validation"


def run(name: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=1800,
        check=False,
    )
    target = VALIDATION / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def generate(base: str | None) -> int:
    outcomes = [
        run("focused", ["make", "task062-test"]),
        run(
            "identity-engine-focused",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_engine.AdapterAndOrderingTests."
                "test_ambiguous_duplicate_candidate_fails_without_checkpoint",
                "tests.test_engine.AdapterAndOrderingTests."
                "test_pagination_and_duplicate_handling_with_equal_page_boundaries",
                "tests.test_task062.CandidateOccurrenceTests."
                "test_identity_is_allowlisted_and_occurrence_is_explicit",
                "tests.test_task062.CandidateOccurrenceTests."
                "test_changed_stable_identity_remains_fail_closed",
                "-v",
            ],
        ),
        run(
            "captured-topologies",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task062.CandidateOccurrenceTests."
                "test_captured_topologies_deduplicate_and_preserve_first_occurrence",
                "-v",
            ],
        ),
        run(
            "selector-and-diagnostic-compatibility",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task062.CandidateOccurrenceTests."
                "test_latest_and_first_in_range_selector_behavior_is_unchanged",
                "tests.test_task062.CandidateOccurrenceTests."
                "test_occurrence_diagnostics_retain_totals_with_bounded_samples",
                "-v",
            ],
        ),
        run("task057-regression", ["make", "task057-test"]),
        run("task058-regression", ["make", "task058-test"]),
        run("task059-regression", ["make", "task059-test"]),
        run("task060-regression", ["make", "task060-test"]),
        run("task061-regression", ["make", "task061-test"]),
        run(
            "repository-engine-regression",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_acquisition",
                "tests.test_engine",
                "-v",
            ],
        ),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-062 validations failed")
    names = tuple(str(item["name"]) for item in outcomes)
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-062-Separate-Candidate-Identity-from-Discovery-Occurrence.md",
        ),
        (
            "design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
            ROOT / "docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
        ),
        ("design/TASK-061-review.md", ROOT / "docs/TASK-061-review.md"),
        ("completion/repository-review.md", ROOT / "docs/TASK-062-review.md"),
        ("evidence/task062-tests.py", ROOT / "tests/test_task062.py"),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in names
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-062",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-062")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    print(json.dumps({**report, "zip": str(ZIP_PATH), "sha256": digest}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    args = parser.parse_args()
    if args.verify:
        print(
            json.dumps(
                verify_package(args.verify, expected_task_id="TASK-062"), indent=2
            )
        )
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
