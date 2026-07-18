#!/usr/bin/env python3
"""Generate the complete independently reviewable TASK-015 evidence package."""

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
TASK_ID = "TASK-015"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip"
ZIP_HASH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
RFI = ROOT / ".venv/bin/rfi"
UI_EVIDENCE = ROOT / ".artifacts/task015-ui-evidence"


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(name: str, command: list[str]) -> dict[str, Any]:
    """Run and capture one reproducible validation command."""
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
    """Return all tracked and untracked task files in deterministic order."""
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


def cli_evidence() -> dict[str, Any]:
    """Create configured state and exercise real installed CLI selection forms."""
    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "state"
        init = run("cli-init", [str(RFI), "init", "--state", str(state)])
        seed = run("cli-seed", [str(RFI), "seed", "--state", str(state)])
        setup_code = (
            "from pathlib import Path;"
            "from rfi.source_profiles import *;"
            f"root=Path({str(state)!r});"
            "t=load_canonical_template();"
            "r=SourceProfileRepository.open(root/'source-profiles',t);"
            "items=tuple(SourceProfileItem(a.artifact_id,a.artifact_id=='press_release',"
            "(RetrievalCandidate('feed',1,url='https://example.test/feed'),) "
            "if a.artifact_id=='press_release' else ()) for a in t.artifacts);"
            "r.publish(SourceProfileDraft('seagate',items),None)"
        )
        setup = run("cli-profile-setup", [str(PYTHON), "-c", setup_code])
        single = run(
            "cli-pull-single",
            [str(RFI), "pull", "--state", str(state), "--firm", "seagate"],
        )
        all_configured = run(
            "cli-pull-all-configured",
            [str(RFI), "pull", "--state", str(state), "--all-configured"],
        )
    return {
        "init": init["exit_code"],
        "seed": seed["exit_code"],
        "profile_setup": setup["exit_code"],
        "single": single["exit_code"],
        "all_configured": all_configured["exit_code"],
    }


def archive(metadata: dict[str, Any]) -> None:
    """Create and independently verify a hashed review ZIP."""
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
    write("manifest.json", json.dumps({**metadata, "files": records}, indent=2) + "\n")
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                output.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    with zipfile.ZipFile(ZIP_PATH) as opened:
        if opened.testzip() is not None:
            raise RuntimeError("TASK-015 review ZIP integrity failed")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_HASH.write_text(f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Run required validation and assemble the complete review package."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    results = [
        run(
            "focused-tests",
            [str(PYTHON), "-m", "unittest", "tests.test_task015", "-v"],
        ),
        run(
            "workflow-proof",
            [str(PYTHON), "scripts/task015_pull_workflow.py", "fixture-proof"],
        ),
        run("git-diff-check", ["git", "diff", "--check"]),
    ]
    cli = cli_evidence()
    results.append(run("make-validate", ["make", "validate"]))
    failures = [item["name"] for item in results if item["exit_code"] != 0]
    if any(value != 0 for value in cli.values()):
        failures.append("cli-evidence")
    if not UI_EVIDENCE.is_dir():
        failures.append("live-ui-evidence")
    files = changed_files()
    write("repository/status.txt", git("status", "--short", "--branch"))
    write("repository/changed-files.json", json.dumps(files, indent=2) + "\n")
    write("repository/complete.patch", complete_patch())
    for source, destination in (
        (ROOT / "docs/pull-workflow.md", PACKAGE / "architecture-and-operations.md"),
        (ROOT / "tasks/TASK-015-pull-workflow.md", PACKAGE / "task-ticket.md"),
    ):
        shutil.copy2(source, destination)
    if UI_EVIDENCE.is_dir():
        shutil.copytree(UI_EVIDENCE, PACKAGE / "ui")
    summary = {
        "task": TASK_ID,
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "commands": results,
        "cli_evidence": cli,
        "gui_evidence": UI_EVIDENCE.is_dir(),
        "rest_evidence": "focused-tests",
        "changed_file_count": len(files),
        "changed_files": files,
    }
    write("verification-summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write(
        "README.md",
        "# TASK-015 review package\n\n"
        "Contains the complete patch and inventory, updated task ticket, architecture and "
        "operations guide, focused workflow/interface tests, deterministic workflow proof, "
        "real CLI evidence, REST evidence, live GUI evidence, full validation output, and "
        "repository status.\n",
    )
    archive(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"review package: {PACKAGE.relative_to(ROOT)}")
    print(f"review archive: {ZIP_PATH.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
