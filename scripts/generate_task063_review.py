#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-063 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-063"
ZIP_PATH = ROOT / ".artifacts/review/TASK-063-review.zip"
VALIDATION = ROOT / ".artifacts/task063-validation"


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
        run("focused", ["make", "task063-test"]),
        run(
            "resolver-focused",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task063.BoundedTranscriptResolutionTests."
                "test_direct_learned_pages_are_fetched_once_without_archive_crawl",
                "tests.test_task063.BoundedTranscriptResolutionTests."
                "test_listing_resolution_is_one_hop_and_never_submits_search",
                "tests.test_task063.BoundedTranscriptResolutionTests."
                "test_configured_fallback_reuses_learned_phase_budget",
                "tests.test_task063.BoundedTranscriptResolutionTests."
                "test_run_budget_cannot_reset_for_configured_fallback",
                "tests.test_task063.BoundedTranscriptResolutionTests."
                "test_unique_candidate_ceiling_is_shared_with_fallback",
                "-v",
            ],
        ),
        run(
            "captured-topologies",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task063.BoundedTranscriptResolutionTests."
                "test_captured_company_topologies_do_not_expand_shared_archives",
                "-v",
            ],
        ),
        run("task057-regression", ["make", "task057-test"]),
        run("task058-regression", ["make", "task058-test"]),
        run("task059-regression", ["make", "task059-test"]),
        run("task060-regression", ["make", "task060-test"]),
        run("task061-regression", ["make", "task061-test"]),
        run("task062-regression", ["make", "task062-test"]),
        run(
            "repository-engine-regression",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_acquisition",
                "tests.test_engine",
                "tests.test_task063",
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
        raise RuntimeError("one or more TASK-063 validations failed")
    names = tuple(str(item["name"]) for item in outcomes)
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-063-Bounded-Transcript-Resolution-Session.md",
        ),
        (
            "design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
            ROOT / "docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
        ),
        ("design/TASK-062-review.md", ROOT / "docs/TASK-062-review.md"),
        ("completion/repository-review.md", ROOT / "docs/TASK-063-review.md"),
        ("evidence/task063-tests.py", ROOT / "tests/test_task063.py"),
        *((f"validation/{name}.txt", VALIDATION / f"{name}.txt") for name in names),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-063",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-063")
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
        print(json.dumps(
            verify_package(args.verify, expected_task_id="TASK-063"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
