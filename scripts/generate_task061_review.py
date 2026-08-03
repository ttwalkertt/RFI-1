#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-061 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-061"
ZIP_PATH = ROOT / ".artifacts/review/TASK-061-review.zip"
VALIDATION = ROOT / ".artifacts/task061-validation"


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
        run(
            "checkpoint-replay-focused",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task060.TranscriptSeedAcquisitionTests."
                "test_oracle_archive_injected_and_learned_replay_are_mutation_free",
                "tests.test_task060.TranscriptSeedAcquisitionTests."
                "test_checkpoint_replay_is_observable_no_change_for_both_selectors",
                "tests.test_task060.TranscriptSeedAcquisitionTests."
                "test_newer_validated_artifact_advances_after_checkpoint_replay_repair",
                "tests.test_task060.TranscriptSeedAcquisitionTests."
                "test_partial_checkpoint_replay_cannot_claim_no_change",
                "tests.test_task060.TranscriptSeedAcquisitionTests."
                "test_same_position_different_checkpoint_cursor_remains_a_conflict",
                "tests.test_task061.TranscriptLearningInspectionTests."
                "test_injected_acquisition_is_visible_through_learning_endpoint",
                "-v",
            ],
        ),
        run("focused", ["make", "task061-test"]),
        run("task059-regression", ["make", "task059-test"]),
        run("task060-regression", ["make", "task060-test"]),
        run(
            "repository-regression",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_acquisition",
                "tests.test_engine",
                "-v",
            ],
        ),
        run(
            "transcript-regression",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task057",
                "tests.test_task056",
                "tests.test_task053",
                "tests.test_task052",
                "tests.test_task048",
                "tests.test_task048a",
                "-v",
            ],
        ),
        run(
            "admin-api-regression",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task009",
                "tests.test_task012",
                "tests.test_task015",
                "-v",
            ],
        ),
        run(
            "injected-acquisition-integration",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task061.TranscriptLearningInspectionTests."
                "test_injected_acquisition_is_visible_through_learning_endpoint",
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
        raise RuntimeError("one or more TASK-061 validations failed")
    names = (
        "checkpoint-replay-focused",
        "focused",
        "task059-regression",
        "task060-regression",
        "repository-regression",
        "transcript-regression",
        "admin-api-regression",
        "injected-acquisition-integration",
        "diff-check",
        "full-validation",
    )
    copied = [
        ("task-ticket.md", ROOT / "tasks/TASK-061-Add-Transcript-Learning-Inspection-API.md"),
        (
            "design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
            ROOT / "docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
        ),
        ("design/TASK-060-review.md", ROOT / "docs/TASK-060-review.md"),
        ("completion/repository-review.md", ROOT / "docs/TASK-061-review.md"),
        ("evidence/task060-tests.py", ROOT / "tests/test_task060.py"),
        ("evidence/task061-tests.py", ROOT / "tests/test_task061.py"),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in names
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-061",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-061")
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
                verify_package(args.verify, expected_task_id="TASK-061"), indent=2
            )
        )
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
