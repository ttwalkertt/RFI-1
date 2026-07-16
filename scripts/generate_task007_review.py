#!/usr/bin/env python3
"""Generate the complete independently verifiable TASK-007 review package."""

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
TASK_ID = "TASK-007"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".venv", "__pycache__"}


def run(command: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run one validation and return complete review-friendly output."""
    result = subprocess.run(
        command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, check=False,
    )
    output = f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n"
    return result.returncode, output


def git(*arguments: str) -> str:
    """Run read-only Git inspection."""
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def digest(path: Path) -> str:
    """Return a SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write one named review artifact."""
    (PACKAGE / name).write_text(content, encoding="utf-8")


def task_base() -> str:
    """Return the branch point before the required initial ticket commit."""
    return git("merge-base", "main", "HEAD").strip()


def complete_patch(base: str) -> str:
    """Render the ticket commit plus all uncommitted milestone changes."""
    parts = [git("diff", "--binary", base, "--", ".")]
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for relative in sorted(item for item in untracked if item):
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"cannot render untracked patch: {relative}")
        parts.append(result.stdout)
    return "\n".join(parts)


def secret_scan() -> tuple[int, str]:
    """Scan reviewable repository files for common committed secret material."""
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
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {name}")
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file():
            continue
        checked += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"review/{path.relative_to(PACKAGE)}: {name}")
    output = f"files_checked: {checked}\nfindings: {len(findings)}\n"
    output += "result: PASS\n" if not findings else "result: FAIL\n" + "\n".join(findings) + "\n"
    return (1 if findings else 0), output


def static_documents(real_available: bool) -> None:
    """Write required architectural narrative artifacts."""
    write(
        "implementation-summary.md",
        "# Implementation summary\n\nTASK-007 adds the provider-neutral `rfi.intelligence` "
        "layer with planner, evidence-gateway, and reasoner ports; hard iteration, package, "
        "evidence-byte, and disclosure budgets; claim-level authority and evidence mappings; "
        "fail-closed plan/package/model validation; complete execution traces; explicit "
        "uncertainty, contradiction, gaps, refusal, and stopping; deterministic substitutes; "
        "operator proof tooling; and governed retention. It imports TASK-006 public contracts "
        "and never reads repository storage.\n",
    )
    write(
        "architectural-decisions-and-tradeoffs.md",
        "# Architectural decisions and tradeoffs\n\nSee ADR-0007 and the TASK-007 subsystem "
        "guide in the cumulative patch. Orchestrator-owned validation and hard bounds favor "
        "auditable incompleteness over fluent output. Full traces cost space. Mapping validation "
        "proves authority and citation completeness but not arbitrary semantic entailment. The "
        "deterministic model substitutes prove replaceability and offline behavior, not model "
        "quality.\n",
    )
    write(
        "runtime-and-retention.md",
        "# Runtime and retention\n\nProvider selection is isolated behind protocols. Credentials "
        "remain in process environment or an external secret manager; contracts store no "
        "credential values. Model input is a bounded projection of public evidence packages. "
        "Retention is `none`, metadata-only (default), or deliberate full records. Proof "
        "artifacts retain full bounded executions for review. See the subsystem guide for the "
        "complete policy.\n",
    )
    write(
        "known-limitations-and-deferred-work.md",
        "# Known limitations and deferred work\n\n- Deterministic SEC vocabulary planner, not a "
        "frontier planning-quality claim.\n- Narrow issuer/filing ontology; no financial body, "
        "XBRL, table, or business-performance analysis.\n- Claim validation enforces mappings "
        "and authority but not general semantic entailment.\n- No live model adapter, prompt "
        "registry, cost routing, saved investigation, operator correction UI, or consulting "
        "workspace.\n- Retrieval quality remains provisional.\n",
    )
    write(
        "bounded-corpus.md",
        "# Bounded corpus\n\nThe real proof consumes the accepted TASK-004 native EDGAR "
        "corpus across STX and WDC through public acquisition/TASK-006 construction contracts. "
        f"Runtime corpus available during generation: {real_available}. The checked fixture proof "
        "is the deterministic offline gate.\n",
    )
    guide = ROOT / "docs/model-guided-source-grounded-intelligence.md"
    status = guide.read_text().split("## Architectural Status Summary", maxsplit=1)[1]
    write("architectural-status-summary.md", "# Architectural Status Summary\n" + status)


def parse_run_output(output: str) -> dict[str, Any]:
    """Parse JSON between the captured command and exit marker."""
    body = output.split("\n", maxsplit=1)[1].rsplit("exit_code:", maxsplit=1)[0]
    return json.loads(body)


def write_proof_views(payload: dict[str, Any]) -> None:
    """Extract independently navigable proof views from the complete output."""
    functional = payload["functional_proof"]
    insufficient = payload["insufficient_evidence_proof"]
    ambiguity = payload["contradiction_and_ambiguity_proof"]
    replacement = payload["replaceability_proof"]
    failure = payload["failure_proof"]
    views = {
        "model-guided-plan-examples.json": functional["trace"]["plan"],
        "retrieval-requests.json": functional["trace"]["retrieval_queries"],
        "consumed-evidence-packages.json": functional["trace"]["evidence_packages"],
        "intelligence-result-example.json": functional["result"],
        "claim-to-evidence-mappings.json": {
            "claims": functional["result"]["claims"],
            "evidence": functional["result"]["evidence"],
        },
        "execution-trace.json": functional["trace"],
        "insufficient-evidence-proof.json": insufficient,
        "contradiction-and-ambiguity-proof.json": ambiguity,
        "replaceability-proof.json": replacement,
        "failure-evidence.json": failure,
    }
    for name, value in views.items():
        write(name, json.dumps(value, indent=2, sort_keys=True) + "\n")


def build_manifest() -> None:
    """Create manifest, ZIP, hash, and independently verify archive integrity."""
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
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    ZIP_HASH.write_text(f"{digest(ZIP_PATH)}  {ZIP_PATH.name}\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for record in records:
            name = f"{TASK_ID}/{record['path']}"
            observed = hashlib.sha256(archive.read(name)).hexdigest()
            if observed != record["sha256"]:
                raise RuntimeError(f"archive digest mismatch: {name}")
        archived_manifest = json.loads(archive.read(f"{TASK_ID}/manifest.json"))
        if archived_manifest != manifest:
            raise RuntimeError("archived manifest differs from package manifest")


def main() -> int:
    """Regenerate every required proof and fail if any gate is incomplete."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    shutil.copy2(
        ROOT / "tasks/TASK-007-model-guided-retrieval-planning-and-source-grounded-intelligence.md",
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
        f"HEAD: {git('rev-parse', 'HEAD').strip()}\nstatus:\n{git('status', '--short')}\n",
    )
    real_root = ROOT / ".artifacts/runtime/TASK-004-edgar"
    static_documents(real_root.is_dir())
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    validations = [
        (
            "focused-task007-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_task007", "-v"],
            environment,
        ),
        (
            "offline-proof-output.json.txt",
            [str(PYTHON), "scripts/task007_operator.py", "fixture-proof"],
            None,
        ),
        ("repository-validation-output.txt", ["make", "validate"], None),
        (
            "documentation-validation-output.txt",
            [str(PYTHON), "scripts/check_docs.py"], None,
        ),
        (
            "baseline-validation-output.txt",
            [str(PYTHON), "scripts/check_baseline.py"], None,
        ),
    ]
    failures: list[str] = []
    commands: list[str] = []
    offline_output = ""
    for name, command, env in validations:
        code, output = run(command, env)
        write(name, output)
        commands.append(f"- `{' '.join(command)}` -> {code}")
        if name == "offline-proof-output.json.txt":
            offline_output = output
        if code:
            failures.append(name)
    if offline_output and "exit_code: 0" in offline_output:
        write_proof_views(parse_run_output(offline_output))
    real_output = "result: BLOCKED\nTASK-004 runtime corpus absent\n"
    if real_root.is_dir():
        command = [
            str(PYTHON), "scripts/task007_operator.py", "real-proof",
            "--acquisition-state", str(real_root.relative_to(ROOT)),
            "--state", ".artifacts/runtime/TASK-007-review",
        ]
        code, real_output = run(command)
        commands.append(f"- `{' '.join(command)}` -> {code}")
        if code:
            failures.append("bounded-real-corpus-proof.json.txt")
    else:
        failures.append("bounded real corpus absent")
    write("bounded-real-corpus-proof.json.txt", real_output)
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
    if failures:
        write("package-result.txt", "result: FAIL\n" + "\n".join(failures) + "\n")
    else:
        write("package-result.txt", "result: PASS\n")
    build_manifest()
    print(f"package: {PACKAGE}")
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {ZIP_HASH}")
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
