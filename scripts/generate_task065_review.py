#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-065 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-065"
ZIP_PATH = ROOT / ".artifacts/review/TASK-065-review.zip"
VALIDATION = ROOT / ".artifacts/task065-validation"


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
        run("focused", ["make", "task065-test"]),
        run("operator-proof", ["make", "task065-proof"]),
        run(
            "architecture",
            [".venv/bin/python", "scripts/task065_architecture_check.py"],
        ),
        run("help", [".venv/bin/python", "-m", "unittest", "tests.test_task027", "-v"]),
        run("documentation", ["make", "docs-check"]),
        run("task060-regression", ["make", "task060-test"]),
        run("task061-regression", ["make", "task061-test"]),
        run("task063-regression", ["make", "task063-test"]),
        run("task064-regression", ["make", "task064-test"]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-065 validations failed")
    names = tuple(str(item["name"]) for item in outcomes)
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-065-Require-Explicit-Transcript-Provider-for-Seed-Injection.md",
        ),
        ("completion/architectural-review.md", ROOT / "docs/TASK-065-review.md"),
        ("evidence/task065-tests.py", ROOT / "tests/test_task065.py"),
        (
            "evidence/task065-explicit-provider-proof.py",
            ROOT / "scripts/task065_explicit_provider.py",
        ),
        (
            "evidence/task065-architecture-check.py",
            ROOT / "scripts/task065_architecture_check.py",
        ),
        ("evidence/provider-registry.py", ROOT / "src/rfi/acquisition/providers/__init__.py"),
        ("evidence/transcript-adapter.py", ROOT / "src/rfi/discovery.py"),
        ("evidence/pull-workflow.py", ROOT / "src/rfi/pull/workflow.py"),
        ("evidence/http-adapter.py", ROOT / "src/rfi/admin/server.py"),
        ("evidence/acquisition-repository.py", ROOT / "src/rfi/acquisition/repository.py"),
        ("evidence/repository-schema.py", ROOT / "src/rfi/storage/sqlite.py"),
        ("evidence/task061-learning-tests.py", ROOT / "tests/test_task061.py"),
        *((f"validation/{name}.txt", VALIDATION / f"{name}.txt") for name in names),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-065",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-065")
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
            verify_package(args.verify, expected_task_id="TASK-065"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
