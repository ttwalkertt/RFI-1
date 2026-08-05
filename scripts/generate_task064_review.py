#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-064 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-064"
ZIP_PATH = ROOT / ".artifacts/review/TASK-064-review.zip"
VALIDATION = ROOT / ".artifacts/task064-validation"


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
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


def generate(base: str | None) -> int:
    outcomes = [
        run("focused", ["make", "task064-test"]),
        run(
            "transcript-regressions",
            [
                ".venv/bin/python", "-m", "unittest",
                "tests.test_task059", "tests.test_task060", "tests.test_task061",
                "tests.test_task062", "tests.test_task063", "-v",
            ],
        ),
        run(
            "deterministic-replay-1",
            [
                ".venv/bin/python", "-m", "unittest",
                "tests.test_task064.ProviderOrchestrationTests."
                "test_fixture_replay_is_byte_for_byte_deterministic", "-v",
            ],
        ),
        run(
            "deterministic-replay-2",
            [
                ".venv/bin/python", "-m", "unittest",
                "tests.test_task064.ProviderOrchestrationTests."
                "test_fixture_replay_is_byte_for_byte_deterministic", "-v",
            ],
        ),
        run(
            "architecture-and-dependencies",
            [".venv/bin/python", "scripts/task064_architecture_check.py"],
        ),
        run(
            "bounded-live",
            [
                ".venv/bin/python", "scripts/task064_live_validation.py",
                "--output", str(VALIDATION / "live-validation.json"),
            ],
        ),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-064 validations failed")
    names = tuple(str(item["name"]) for item in outcomes)
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-064-Dedicated-StockAnalysis-Transcript-Provider-Adapter.md",
        ),
        ("completion/architectural-review.md", ROOT / "docs/TASK-064-review.md"),
        ("evidence/task064-tests.py", ROOT / "tests/test_task064.py"),
        (
            "evidence/provider-registry.py",
            ROOT / "src/rfi/acquisition/providers/__init__.py",
        ),
        (
            "evidence/stockanalysis-provider.py",
            ROOT / "src/rfi/acquisition/providers/stockanalysis.py",
        ),
        ("evidence/provider-neutral-contracts.py", ROOT / "src/rfi/acquisition/contracts.py"),
        ("evidence/orchestrator.py", ROOT / "src/rfi/discovery.py"),
        (
            "evidence/firm-config-schema.json",
            ROOT / "src/rfi/resources/firm-config-v1.schema.json",
        ),
        (
            "evidence/oracle-archive.html",
            ROOT / "fixtures/transcripts/stockanalysis-orcl-archive.html",
        ),
        (
            "evidence/oracle-transcript.html",
            ROOT / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html",
        ),
        (
            "evidence/capture-manifest.json",
            ROOT / "fixtures/transcripts/stockanalysis-capture-manifest.json",
        ),
        *((f"validation/{name}.txt", VALIDATION / f"{name}.txt") for name in names),
        ("validation/live-validation.json", VALIDATION / "live-validation.json"),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-064",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-064")
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
            verify_package(args.verify, expected_task_id="TASK-064"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
