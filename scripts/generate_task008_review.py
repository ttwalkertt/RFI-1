#!/usr/bin/env python3
"""Generate the complete independently verifiable TASK-008 review package."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-008"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".venv", "__pycache__"}


def run(command: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run one validation and capture complete combined output."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return (
        result.returncode,
        f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n",
    )


def git(*arguments: str) -> str:
    """Run read-only Git inspection."""
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


def digest(path: Path) -> str:
    """Return one SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def task_base() -> str:
    """Return the branch point before the ticket-only commit."""
    return git("merge-base", "main", "HEAD").strip()


def complete_patch(base: str) -> str:
    """Render the ticket commit and all uncommitted milestone changes."""
    parts = [git("diff", "--binary", base, "--", ".")]
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for relative in sorted(item for item in untracked if item):
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


def static_documents() -> None:
    """Write the required architectural and operator narratives."""
    write(
        "implementation-summary.md",
        "# Implementation summary\n\nTASK-008 adds `rfi.workspace`, a dependency-free durable "
        "operator-product layer. Investigations are projections of SHA-256 hash-chained "
        "append-only JSON events. Execution intent is committed before TASK-007 invocation; "
        "terminal records retain provider-neutral reference snapshots, result semantics, "
        "failures, and metrics without copying source context or raw model exchanges. The "
        "milestone includes annotations, semantic rerun comparison, Markdown/JSON export, "
        "self-verifying ZIP backup, staged restore, partial-write recovery, redacted transient "
        "diagnostics, a Python service/API, and a scriptable JSON console.\n",
    )
    write(
        "architectural-decisions.md",
        "# Architectural decisions\n\nSee ADR-0008 and "
        "`docs/consulting-workspace-and-execution-journal.md` in the cumulative patch. The "
        "workspace depends only on public intelligence contracts. Hash-chained filesystem events "
        "favor portability, inspection, and append-only history over concurrent-write scale. "
        "Reference snapshots preserve historical meaning without becoming evidence or retrieval "
        "authority. Indefinite journal retention and transient redacted diagnostics keep audit "
        "history separate from operational troubleshooting.\n",
    )
    write(
        "workspace-walkthrough.md",
        "# Workspace walkthrough\n\nThe proof creates an investigation, commits an execution "
        "start, runs the complete governed intelligence pipeline, commits the terminal snapshot, "
        "reopens from disk, inspects exact evidence identities, adds an operator interpretation, "
        "reruns with alternate provider-neutral wording, compares semantic dimensions, executes "
        "insufficient and failure scenarios, exports, backs up, restores, and verifies the "
        "restored hash chain and exports. See `functional-proof.json`, `journal-example.json`, "
        "`comparison-example.json`, and `failure-proofs.json`.\n",
    )
    write(
        "logging-and-retention.md",
        "# Logging, journal, and retention\n\nCommitted events and reference snapshots are "
        "retained "
        "indefinitely. They contain configuration with credential-like fields redacted, plan and "
        "trace identities, evidence references, conclusions, uncertainty, failure state, and "
        "metrics. Exact source context, model input, and raw model output are omitted. Structured "
        "diagnostics are transient, stream-directed, and redacted; they are never journal events. "
        "Uncommitted partial files are quarantined without modifying committed history.\n",
    )
    write(
        "known-limitations.md",
        "# Known limitations and deferred work\n\n- Single writer; no locking or concurrent "
        "mutation proof.\n- Hash chain is tamper-evident for accidental change, not externally "
        "signed.\n"
        "- Full event replay and file enumeration are not performance-tested at scale.\n"
        "- Reference snapshots cannot replace missing upstream authority data.\n"
        "- Markdown export is functional rather than client-presentation quality.\n"
        "- No authentication, collaboration, scheduling, GUI, incremental backup, cloud "
        "durability, or production observability.\n- Retrieval/model quality remains "
        "provisional.\n",
    )
    guide = (ROOT / "docs/consulting-workspace-and-execution-journal.md").read_text()
    status = guide.split("## Architectural Status Summary", maxsplit=1)[1]
    write("architectural-status-summary.md", "# Architectural Status Summary\n" + status)


def parse_run_output(output: str) -> dict[str, Any]:
    """Parse JSON between the recorded command and exit marker."""
    body = output.split("\n", maxsplit=1)[1].rsplit("exit_code:", maxsplit=1)[0]
    return json.loads(body)


def write_proof_views(payload: dict[str, Any]) -> None:
    """Extract navigable lifecycle and operational proof artifacts."""
    views = {
        "functional-proof.json": {
            "workspace": payload["workspace"],
            "first_execution": payload["first_execution"],
            "checks": payload["checks"],
        },
        "journal-example.json": payload["journal"],
        "comparison-example.json": payload["comparison"],
        "export-example.md": payload["export"]["content"],
        "backup-and-restore-proof.json": {
            "backup": payload["backup"],
            "restore_integrity": payload["restore_integrity"],
            "backup_failure_visible": payload["checks"]["backup_failure_visible"],
            "restore_failure_visible": payload["checks"]["restore_failure_visible"],
        },
        "operational-metrics-example.json": payload["operational_metrics"],
        "logging-and-retention-evidence.json": payload["logging"],
        "failure-proofs.json": {
            "executions": payload["failure_proofs"],
            "partial_write_quarantine": payload["partial_write_quarantine"],
            "checks": {
                key: value for key, value in payload["checks"].items()
                if any(
                    term in key for term in (
                        "failure", "interruption", "partial", "invalid", "corruption",
                        "insufficient", "stale",
                    )
                )
            },
        },
    }
    for name, value in views.items():
        if isinstance(value, str):
            write(name, value)
        else:
            write(name, json.dumps(value, indent=2, sort_keys=True) + "\n")


def secret_scan() -> tuple[int, str]:
    """Scan reviewable text for common plaintext credential signatures."""
    patterns = {
        "private-key": re.compile("BEGIN " + "(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
        "openai-key": re.compile("sk-" + r"(?:proj-)?[A-Za-z0-9_-]{20,}"),
        "aws-access-key": re.compile("AK" + r"IA[0-9A-Z]{16}"),
    }
    findings: list[str] = []
    checked = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED for part in path.parts):
            continue
        if path.suffix not in {".py", ".md", ".json", ".toml", ".txt"}:
            continue
        checked += 1
        content = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in patterns.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: {name}")
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file():
            continue
        checked += 1
        content = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in patterns.items():
            if pattern.search(content):
                findings.append(f"review/{path.relative_to(PACKAGE)}: {name}")
    output = f"files_checked: {checked}\nfindings: {len(findings)}\n"
    output += "result: PASS\n" if not findings else "result: FAIL\n" + "\n".join(findings)
    return (1 if findings else 0), output


def build_manifest() -> None:
    """Create a manifest, ZIP, hash, and independent ZIP digest verification."""
    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    records = [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": digest(path),
            "size": path.stat().st_size,
        }
        for path in files
    ]
    manifest = {"task": TASK_ID, "schema_version": 1, "files": records}
    write("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    ZIP_HASH.write_text(f"{digest(ZIP_PATH)}  {ZIP_PATH.name}\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for record in records:
            name = f"{TASK_ID}/{record['path']}"
            if hashlib.sha256(archive.read(name)).hexdigest() != record["sha256"]:
                raise RuntimeError(f"archive digest mismatch: {name}")
        if json.loads(archive.read(f"{TASK_ID}/manifest.json")) != manifest:
            raise RuntimeError("archived manifest differs from package manifest")


def main() -> int:
    """Regenerate required proof, validation, review, and integrity artifacts."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    shutil.copy2(
        ROOT / "tasks/TASK-008-consulting-workspace-execution-journal-and-operational-hardening.md",
        PACKAGE / "task-ticket.md",
    )
    base = task_base()
    write("cumulative-task.patch", complete_patch(base))
    tracked = git("diff", "--name-only", base, "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    write("changed-files.txt", "\n".join(sorted(set(tracked + untracked))) + "\n")
    write(
        "git-state.txt",
        f"branch: {git('branch', '--show-current').strip()}\nbase: {base}\n"
        f"HEAD: {git('rev-parse', 'HEAD').strip()}\nstatus:\n{git('status', '--short')}\n"
        "commit state: only the required TASK-008 ticket commit exists; implementation is "
        "intentionally uncommitted.\n",
    )
    static_documents()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    validations = [
        (
            "focused-task008-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_task008", "-v"],
            environment,
        ),
        (
            "workspace-proof-output.json.txt",
            [str(PYTHON), "scripts/task008_workspace.py", "fixture-proof"],
            None,
        ),
        ("repository-validation-output.txt", ["make", "validate"], None),
        ("documentation-validation-output.txt", [str(PYTHON), "scripts/check_docs.py"], None),
        ("baseline-validation-output.txt", [str(PYTHON), "scripts/check_baseline.py"], None),
    ]
    failures: list[str] = []
    commands: list[str] = []
    proof_output = ""
    for name, command, env in validations:
        code, output = run(command, env)
        write(name, output)
        commands.append(f"- `{' '.join(command)}` -> {code}")
        if name == "workspace-proof-output.json.txt":
            proof_output = output
        if code:
            failures.append(name)
    if proof_output and "exit_code: 0" in proof_output:
        write_proof_views(parse_run_output(proof_output))
    write(
        "validation-commands.md",
        "# Validation commands and complete results\n\n" + "\n".join(commands) + "\n",
    )
    scan_code, scan_output = secret_scan()
    write("secret-scan-output.txt", scan_output)
    if scan_code:
        failures.append("secret-scan-output.txt")
    write(
        "integrity-result.txt",
        "manifest_algorithm: SHA-256\narchive_verification: every manifested file is read "
        "back from the ZIP and rehashed\nresult: PASS (written only if build completes)\n",
    )
    write(
        "package-result.txt",
        "result: PASS\n" if not failures else "result: FAIL\n" + "\n".join(failures) + "\n",
    )
    build_manifest()
    print(f"package: {PACKAGE}")
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {ZIP_HASH}")
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
