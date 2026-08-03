#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-060 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-060"
ZIP_PATH = ROOT / ".artifacts/review/TASK-060-review.zip"
VALIDATION = ROOT / ".artifacts/task060-validation"


def run(name: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command, cwd=ROOT, env={**os.environ, "PYTHONPATH": "src"}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800, check=False,
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
        run("focused", ["make", "task060-test"]),
        run("task059-regression", ["make", "task059-test"]),
        run("task058-regression", ["make", "task058-test"]),
        run("transcript-regression", [
            ".venv/bin/python", "-m", "unittest", "tests.test_task057",
            "tests.test_task056", "tests.test_task053", "tests.test_task052",
            "tests.test_task048", "tests.test_task048a", "-v",
        ]),
        run("api-rest-regression", [
            ".venv/bin/python", "-m", "unittest", "tests.test_task015",
            "tests.test_task012", "-v",
        ]),
        run("manual-proof", ["make", "task060-proof"]),
        run("task059-proof", ["make", "task059-proof"]),
        run("task058-proof", ["make", "task058-proof"]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-060 validations failed")
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-060-Add-Seed-Injection-Transcript-Acquisition-API.md",
        ),
        (
            "design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
            ROOT / "docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md",
        ),
        ("completion/repository-review.md", ROOT / "docs/TASK-060-review.md"),
        ("evidence/task060-tests.py", ROOT / "tests/test_task060.py"),
        ("evidence/task060-seed-injection-proof.py", ROOT / "scripts/task060_seed_injection.py"),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "focused", "task059-regression", "task058-regression",
                "transcript-regression", "api-rest-regression", "manual-proof",
                "task059-proof", "task058-proof", "diff-check", "full-validation",
            )
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT, task_id="TASK-060", package=PACKAGE, zip_path=ZIP_PATH,
        copied_members=copied, base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-060")
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
            verify_package(args.verify, expected_task_id="TASK-060"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
