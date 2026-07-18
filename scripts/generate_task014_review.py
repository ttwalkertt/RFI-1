#!/usr/bin/env python3
"""Generate an independently reviewable TASK-014 evidence package."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-014"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip"
ZIP_HASH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
RFI = ROOT / ".venv/bin/rfi"
UI_EVIDENCE = ROOT / ".artifacts/task014-ui-evidence"


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(name: str, command: list[str]) -> dict[str, Any]:
    """Run and capture a reproducible verification command."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    write(
        f"validation/{name}.txt",
        f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def git(*arguments: str) -> str:
    """Run one read-only Git query."""
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def changed_files() -> list[str]:
    """Return tracked and untracked task files in deterministic order."""
    tracked = git("diff", "--name-only", "main", "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set((*tracked, *untracked)))


def complete_patch() -> str:
    """Render the cumulative task patch, including untracked files."""
    parts = [git("diff", "--binary", "main", "--", ".")]
    for relative in git("ls-files", "--others", "--exclude-standard").splitlines():
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"cannot render untracked patch: {relative}")
        parts.append(result.stdout)
    return "\n".join(parts)


def parity() -> dict[str, Any]:
    """Capture installed executable and module lifecycle parity on independent state roots."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installed = run(
            "installed-init",
            [str(RFI), "init", "--state", str(root / "installed")],
        )
        module = run(
            "module-init",
            [str(PYTHON), "-m", "rfi", "init", "--state", str(root / "module")],
        )
        installed_help = run("installed-help", [str(RFI), "--help"])
        module_help = run("module-help", [str(PYTHON), "-m", "rfi", "--help"])
    return {
        "init_exit_codes_match": installed["exit_code"] == module["exit_code"] == 0,
        "help_exit_codes_match": installed_help["exit_code"]
        == module_help["exit_code"]
        == 0,
    }


def archive(metadata: dict[str, Any]) -> None:
    """Create a hashed deterministic review archive and verify it can be read back."""
    records = []
    for path in sorted(PACKAGE.rglob("*")):
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(PACKAGE).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size": path.stat().st_size,
                }
            )
    write(
        "manifest.json",
        json.dumps({**metadata, "files": records}, indent=2, sort_keys=True) + "\n",
    )
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                output.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    with zipfile.ZipFile(ZIP_PATH) as opened:
        if opened.testzip() is not None:
            raise RuntimeError("TASK-014 review ZIP integrity failed")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_HASH.write_text(f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Run all required validation and assemble the durable review package."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    results = [
        run(
            "focused-tests",
            [str(PYTHON), "-m", "unittest", "tests.test_task014", "-v"],
        ),
        run(
            "fixture-proof",
            [str(PYTHON), "scripts/task014_source_profiles.py", "fixture-proof"],
        ),
        run("git-diff-check", ["git", "diff", "--check"]),
    ]
    parity_result = parity()
    results.append(run("make-validate", ["make", "validate"]))
    failures = [item["name"] for item in results if item["exit_code"] != 0]
    if not all(parity_result.values()):
        failures.append("cli-parity")
    if not UI_EVIDENCE.is_dir():
        failures.append("live-ui-evidence")
    status = git("status", "--short", "--branch")
    files = changed_files()
    write("repository/status.txt", status)
    write("repository/changed-files.json", json.dumps(files, indent=2) + "\n")
    write("repository/complete.patch", complete_patch())
    shutil.copy2(
        ROOT / "src/rfi/resources/source-profile-template.yaml",
        PACKAGE / "canonical-source-profile-template.yaml",
    )
    shutil.copy2(
        ROOT / "docs/firm-source-profiles-and-acquisition-template.md",
        PACKAGE / "architecture-and-operations.md",
    )
    shutil.copy2(
        ROOT / "tasks/TASK-014-firm-source-profiles-and-acquisition-template.md",
        PACKAGE / "task-ticket.md",
    )
    if UI_EVIDENCE.is_dir():
        shutil.copytree(UI_EVIDENCE, PACKAGE / "ui")
        ui_walkthrough = json.loads(
            (UI_EVIDENCE / "live-ui-walkthrough.json").read_text(encoding="utf-8")
        )
    else:
        ui_walkthrough = None
    summary = {
        "task": TASK_ID,
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "commands": results,
        "cli_parity": parity_result,
        "live_ui_walkthrough": ui_walkthrough,
        "changed_file_count": len(files),
        "changed_files": files,
    }
    write("verification-summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write(
        "README.md",
        "# TASK-014 review package\n\n"
        "This package contains the canonical application-data template, task ticket, architecture "
        f"documentation, complete cumulative patch, repository status, {len(files)}-file changed "
        "inventory, focused test output, "
        "deterministic aggregate proof, CLI parity evidence, rendered live-UI walkthrough JSON "
        "and screenshots, explicit `git diff --check`, and complete `make validate` output.\n",
    )
    archive(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"review package: {PACKAGE.relative_to(ROOT)}")
    print(f"review archive: {ZIP_PATH.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
