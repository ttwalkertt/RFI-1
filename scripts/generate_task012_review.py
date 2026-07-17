#!/usr/bin/env python3
"""Generate the independently reviewable TASK-012 evidence package."""

from __future__ import annotations

import hashlib
import json
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-012"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip"
ZIP_HASH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip.sha256"
RFI = ROOT / ".venv/bin/rfi"
PYTHON = Path(sys.executable)


def write(name: str, content: str) -> None:
    """Write one review artifact and create its parent directory."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(name: str, command: list[str]) -> dict[str, Any]:
    """Run and capture one validation command."""
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
    """Run a read-only Git query."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def changed_files(base: str) -> list[str]:
    """Return tracked and untracked task files in deterministic order."""
    tracked = git("diff", "--name-only", base, "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def complete_patch(base: str) -> str:
    """Return one cumulative patch including untracked task files."""
    parts = [git("diff", "--binary", base, "--", ".")]
    for relative in git("ls-files", "--others", "--exclude-standard").splitlines():
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"cannot render untracked patch: {relative}")
        parts.append(result.stdout)
    return "\n".join(parts)


def walkthrough() -> dict[str, Any]:
    """Capture first-run, repeat-use, startup, API, and clean-stop behavior."""
    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "state"
        commands = [
            ("init-fresh", [str(RFI), "init", "--state", str(state)]),
            ("init-repeat", [str(RFI), "init", "--state", str(state)]),
            ("seed-fresh", [str(RFI), "seed", "--state", str(state)]),
            ("seed-repeat", [str(RFI), "seed", "--state", str(state)]),
        ]
        results = [run(name, command) for name, command in commands]
        process = subprocess.Popen(
            [str(RFI), "admin", "--state", str(state), "--port", "0"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if process.stdout is None:
            raise RuntimeError("admin startup output was not captured")
        startup = [process.stdout.readline() for _ in range(4)]
        url_line = next((line for line in startup if line.startswith("Local URL: ")), "")
        if not url_line:
            process.terminate()
            raise RuntimeError("admin did not report its local URL")
        url = url_line.removeprefix("Local URL: ").strip()
        with urllib.request.urlopen(url + "api/concepts", timeout=3) as response:
            concepts = json.load(response)
        with urllib.request.urlopen(url + "api/firms", timeout=3) as response:
            firms = json.load(response)
        process.send_signal(signal.SIGINT)
        stopped = process.communicate(timeout=5)[0]
        startup_output = "".join(startup) + stopped
        write("walkthrough/admin-startup-and-stop.txt", startup_output)
        write(
            "walkthrough/catalog-availability.json",
            json.dumps(
                {
                    "concept_count": len(concepts["items"]),
                    "firm_count": len(firms["items"]),
                    "concept_ids": [item["concept_id"] for item in concepts["items"]],
                    "firm_ids": [item["firm_id"] for item in firms["items"]],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        return {
            "commands": results,
            "admin_exit_code": process.returncode,
            "concept_count": len(concepts["items"]),
            "firm_count": len(firms["items"]),
            "clean_stop": "admin console stopped" in startup_output,
        }


def package_zip(metadata: dict[str, Any]) -> None:
    """Manifest, archive, and read back all review evidence."""
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
    manifest = json.dumps({**metadata, "files": records}, indent=2, sort_keys=True)
    write("manifest.json", manifest + "\n")
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("review ZIP integrity failed")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_HASH.write_text(f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Capture TASK-012 evidence, run full validation, and create the review package."""
    if not RFI.is_file():
        raise RuntimeError("installed .venv/bin/rfi is missing; install the repository first")
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    base = git("merge-base", "main", "HEAD").strip()
    help_results = [
        run("installed-help", [str(RFI), "--help"]),
        run("module-help", [str(PYTHON), "-m", "rfi", "--help"]),
        run("admin-help", [str(RFI), "admin", "--help"]),
        run("init-help", [str(RFI), "init", "--help"]),
        run("seed-help", [str(RFI), "seed", "--help"]),
    ]
    flow = walkthrough()
    with tempfile.TemporaryDirectory() as failure_temporary:
        failure_root = Path(failure_temporary)
        missing = run(
            "missing-state",
            [str(RFI), "admin", "--state", str(failure_root / "missing")],
        )
        invalid_state = failure_root / "invalid-port"
        invalid_init = run(
            "invalid-port-init",
            [str(RFI), "init", "--state", str(invalid_state)],
        )
        invalid = run(
            "invalid-port",
            [str(RFI), "admin", "--state", str(invalid_state), "--port", "70000"],
        )
    validations = [
        run("focused", [str(PYTHON), "-m", "unittest", "tests.test_task012", "-v"]),
        run("full", ["make", "validate"]),
    ]
    changed = changed_files(base)
    write("changed-files.txt", "\n".join(changed) + "\n")
    write("task.patch", complete_patch(base))
    write(
        "operator-workflows.md",
        "# Operator workflows\n\nFirst run: `rfi init`, optional explicit `rfi seed`, then "
        "`rfi admin`. Repeat use: `rfi admin` with the same state path. Help, lifecycle output, "
        "seed counts, live catalog responses, and Ctrl-C shutdown are captured in this package.\n",
    )
    write(
        "known-limitations.md",
        "# Known limitations\n\nThe foreground server is local, unauthenticated, and "
        "single-operator "
        "oriented. There is no daemon, browser launch, migration, deployment packaging, or "
        "automatic seed refresh. Editable installation requires a Python build backend.\n",
    )
    failures = [
        item["name"]
        for item in [*help_results, *flow["commands"], *validations]
        if item["exit_code"] != 0
    ]
    if invalid_init["exit_code"] != 0 or missing["exit_code"] == 0 or invalid["exit_code"] == 0:
        failures.append("failure-behavior")
    if flow["admin_exit_code"] != 0 or not flow["clean_stop"]:
        failures.append("admin-clean-stop")
    metadata = {
        "task": TASK_ID,
        "base": base,
        "head": git("rev-parse", "HEAD").strip(),
        "branch": git("branch", "--show-current").strip(),
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "walkthrough": flow,
        "validations": validations,
    }
    package_zip(metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    print(f"package: {PACKAGE}\nzip: {ZIP_PATH}\nchecksum: {ZIP_HASH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
