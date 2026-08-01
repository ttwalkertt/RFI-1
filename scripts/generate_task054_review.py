#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-054 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-054"
ZIP_PATH = ROOT / ".artifacts/review/TASK-054-review.zip"
VALIDATION = ROOT / ".artifacts/task054-validation"


def run_validation(name: str, command: list[str]) -> dict[str, object]:
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
        run_validation("focused", ["make", "task054-test"]),
        run_validation("operator-proof", ["make", "task054-proof"]),
        run_validation("diff-check", ["git", "diff", "--check"]),
        run_validation("full-validation", ["make", "validate"]),
    ]
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-054 validations failed")
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-054-reload-externally-managed-firm-profiles.md",
        ),
        ("completion/repository-review.md", ROOT / "docs/TASK-054-review.md"),
        ("evidence/task054-tests.py", ROOT / "tests/test_task054.py"),
        ("evidence/operator-proof.py", ROOT / "scripts/task054_reload_firm_profiles.py"),
        ("validation/focused.txt", VALIDATION / "focused.txt"),
        ("validation/operator-proof.txt", VALIDATION / "operator-proof.txt"),
        ("validation/diff-check.txt", VALIDATION / "diff-check.txt"),
        ("validation/full-validation.txt", VALIDATION / "full-validation.txt"),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-054",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-054")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    ZIP_PATH.with_suffix(".zip.integrity.txt").write_text(
        f"ZIP integrity: PASS\n{json.dumps(report, sort_keys=True)}\nsha256: {digest}\n",
        encoding="utf-8",
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
            verify_package(args.verify, expected_task_id="TASK-054"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
