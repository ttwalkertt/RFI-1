#!/usr/bin/env python3
"""Generate or independently verify the TASK-050 review package."""

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
PACKAGE = ROOT / ".artifacts/review/TASK-050"
ZIP_PATH = ROOT / ".artifacts/review/TASK-050-review.zip"


def run_validation(name: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command, cwd=ROOT, env={**os.environ, "PYTHONPATH": "src"}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800, check=False,
    )
    target = ROOT / ".artifacts/task050-validation" / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def generate(base: str | None) -> int:
    validation_root = ROOT / ".artifacts/task050-validation"
    validation_root.mkdir(parents=True, exist_ok=True)
    outcomes = [
        run_validation(
            "focused-review-package",
            [sys.executable, "-m", "unittest", "tests.test_review_package", "-v"],
        ),
        run_validation("diff-check", ["git", "diff", "--check"]),
        run_validation("full-validation", ["make", "validate"]),
    ]
    (validation_root / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more review-package validations failed")
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-050 - Make Review Package Generation Commit-Aware.md",
        ),
        ("completion/repository-review.md", ROOT / "docs/TASK-050-review.md"),
        ("evidence/review-package-tests.py", ROOT / "tests/test_review_package.py"),
        ("validation/focused-review-package.txt", validation_root / "focused-review-package.txt"),
        ("validation/diff-check.txt", validation_root / "diff-check.txt"),
        ("validation/full-validation.txt", validation_root / "full-validation.txt"),
        ("validation/results.json", validation_root / "results.json"),
    ]
    build_package(
        root=ROOT, task_id="TASK-050", package=PACKAGE, zip_path=ZIP_PATH,
        copied_members=copied, base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-050")
    integrity = ZIP_PATH.with_suffix(".zip.integrity.txt")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    integrity.write_text(
        f"ZIP integrity: PASS\n{json.dumps(report, sort_keys=True)}\nsha256: {digest}\n",
        encoding="utf-8",
    )
    print(json.dumps({**report, "zip": str(ZIP_PATH), "sha256": digest}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify", type=Path, help="verify an existing package without regeneration"
    )
    parser.add_argument(
        "--base", help="explicit review base ref (default: origin's default branch)"
    )
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_package(args.verify, expected_task_id="TASK-050"), indent=2))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
