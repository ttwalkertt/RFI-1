#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-048 review package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts" / "review" / "TASK-048"
ZIP_PATH = PACKAGE.parent / "TASK-048-review.zip"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def write(relative: str, content: str) -> None:
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def run(name: str, command: list[str], live: bool = False) -> dict[str, Any]:
    environment = {**os.environ, "PYTHONPATH": "src"}
    environment.pop("RFI_SEC_USER_AGENT", None)
    environment.pop("SEC_API_IO_API_KEY", None)
    result = subprocess.run(
        command, cwd=ROOT, env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=1800, check=False,
    )
    destination = "live/live-acquisition.txt" if live else f"validation/{name}.txt"
    transcript = f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n"
    write(destination, transcript)
    return {
        "name": name, "command": command, "exit_code": result.returncode,
        "passed": result.returncode == 0,
    }


def complete_patch() -> str:
    base = "HEAD^" if not git("status", "--porcelain") else "HEAD"
    parts = [git("diff", "--binary", base, "--", ".")]
    for relative in git("ls-files", "--others", "--exclude-standard").splitlines():
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(result.stdout)
        parts.append(result.stdout)
    return "".join(parts)


def main() -> int:
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_PATH.with_suffix(".zip.sha256").unlink(missing_ok=True)
    ZIP_PATH.with_suffix(".zip.integrity.txt").unlink(missing_ok=True)

    base = "HEAD^" if not git("status", "--porcelain") else "HEAD"
    changed = sorted(set(
        git("diff", "--name-only", base, "--", ".").splitlines()
        + git("ls-files", "--others", "--exclude-standard").splitlines()
    ))
    validations = [
        run("focused-task048", [sys.executable, "-m", "unittest", "tests.test_task048", "-v"]),
        run("interval-regression", [sys.executable, "-m", "unittest", "tests.test_task047", "-v"]),
        run("acquisition-repository-schema-regression", [
            sys.executable, "-m", "unittest", "tests.test_acquisition", "tests.test_task021", "-v",
        ]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
        run(
            "live-acquisition",
            [sys.executable, "scripts/task048_earnings_transcripts.py", "live-proof"],
            True,
        ),
    ]
    for destination, source in {
        "task-ticket.md": ROOT / "tasks" / "TASK-048 — Acquire Earnings-Call Transcr.md",
        "architecture/contract.md": ROOT / "docs" / "date-delimited-acquisition-contract.md",
        "completion/repository-review.md": ROOT / "docs" / "TASK-048-review.md",
        "evidence/test_task048.py": ROOT / "tests" / "test_task048.py",
        "evidence/live-proof.py": ROOT / "scripts" / "task048_earnings_transcripts.py",
    }.items():
        target = PACKAGE / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    write("repository/git-status.txt", git("status", "--short", "--branch"))
    write("repository/branch.txt", git("branch", "--show-current"))
    write("repository/commit.txt", git("rev-parse", "HEAD"))
    write("repository/complete.patch", complete_patch())
    write("repository/changed-files.json", json.dumps({"files": changed}, indent=2) + "\n")
    write("validation/results.json", json.dumps(validations, indent=2) + "\n")
    if not all(item["passed"] for item in validations):
        raise RuntimeError("one or more review-package validations failed")

    members = sorted(
        path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*") if path.is_file()
    )
    checksums = {member: sha256(PACKAGE / member) for member in members}
    write("manifest.json", json.dumps({"task": "TASK-048", "members": checksums}, indent=2) + "\n")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE.parent))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
        zip_members = sorted(archive.namelist())
    expected = sorted(
        f"TASK-048/{path.relative_to(PACKAGE).as_posix()}"
        for path in PACKAGE.rglob("*") if path.is_file()
    )
    if bad_member is not None or zip_members != expected:
        raise RuntimeError("review package ZIP integrity failed")
    digest = sha256(ZIP_PATH)
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    ZIP_PATH.with_suffix(".zip.integrity.txt").write_text(
        f"ZIP integrity: PASS\nmembers: {len(expected)}\nsha256: {digest}\n", encoding="utf-8"
    )
    print(f"review package: {ZIP_PATH}")
    print(f"members: {len(expected)}")
    print(f"sha256: {digest}")
    print("ZIP integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
