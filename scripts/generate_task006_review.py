#!/usr/bin/env python3
"""Generate the complete independently verifiable TASK-006 review package."""

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

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-006"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".venv", "__pycache__"}


def run(command: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run one validation and retain complete combined output."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n"
    return result.returncode, output


def git(*arguments: str) -> str:
    """Run read-only Git inspection for review metadata."""
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
    """Return a file SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write one named review artifact."""
    (PACKAGE / name).write_text(content, encoding="utf-8")


def complete_patch() -> str:
    """Render tracked and untracked milestone changes into one cumulative patch."""
    parts = [git("diff", "--binary", "HEAD", "--", ".")]
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


def static_documents(real_available: bool) -> None:
    """Write the architectural narrative required by the task ticket."""
    write(
        "implementation-summary.md",
        "# Implementation summary\n\nTASK-006 adds the independent `rfi.retrieval` package, "
        "stable typed query/result/trace/evidence contracts, atomic reproducible search "
        "generations, a contract-validated replaceable vector candidate boundary, exact "
        "provenance verification, "
        "bounded context assembly, and a shared console browser. Search state fingerprints but "
        "does not own source or knowledge authority. Missing, stale, corrupt, partial, and "
        "budget-limited behavior remains explicit and fail-closed.\n",
    )
    write(
        "architectural-decisions-and-tradeoffs.md",
        "# Architectural decisions and tradeoffs\n\nSee ADR-0006 and "
        "`docs/governed-retrieval-and-source-browser.md` in the cumulative patch. The initial "
        "hashing vector favors reproducibility over semantic recall. Full candidate traces cost "
        "space but make exclusions inspectable. Whole-result budget omission preserves complete "
        "provenance. Replacement vectorizers may rank or select differently; the invariant is "
        "public schema, authority class, provenance, budget, and visible coverage. Strict "
        "authority fingerprints favor trustworthy failure over stale access.\n",
    )
    write(
        "known-limitations-and-deferred-work.md",
        "# Known limitations and deferred work\n\n- Deterministic token and character hashing, "
        "not learned semantic embeddings or a retrieval-quality claim.\n- Structural/normalized "
        "source fields only; no "
        "HTML sections, XBRL, tables, or PDF body retrieval.\n- Byte-window context rather than "
        "section-aware expansion.\n- No incremental/distributed index, concurrency, reranker, "
        "query planner, or saved traces.\n- Narrow contradiction detection and TASK-005 ontology.\n"
        "- Model reasoning, answers, saved investigations, and consulting workflows remain "
        "TASK-007 and TASK-008.\n",
    )
    write(
        "bounded-corpus.md",
        "# Bounded corpus\n\nThe required real proof uses the accepted TASK-004 native "
        "EDGAR corpus: ten filings across STX and WDC and 62,070,796 immutable artifact bytes. "
        f"Runtime corpus available during package generation: {real_available}. The checked "
        "two-filing fixture proof remains the offline reproducibility gate.\n",
    )
    write(
        "architectural-status-summary.md",
        "# Architectural Status Summary\n\n- Repository foundation — **Complete**; governance, "
        "validation, and review packaging remain active.\n- Acquisition substrate — **Complete**; "
        "immutable evidence and history remain authoritative.\n- Acquisition engine — "
        "**Complete**; "
        "provider orchestration remains replayable.\n- Live SEC providers — **Usable with "
        "Limitations**; accepted native EDGAR corpus exists, scheduling does not.\n- Immutable "
        "evidence — **Complete**; exact artifact bytes anchor context.\n- Source-object subsystem "
        "— **Usable with Limitations**; exact SEC SGML structure, not semantic body formats.\n"
        "- Derived-knowledge subsystem — **Usable with Limitations**; governed and versioned but "
        "deliberately narrow.\n- Governed retrieval contracts and evidence assembly — "
        "**Complete**; typed access, constraints, traces, evidence budgets, provenance, "
        "replaceability, rebuild, and failure semantics are established.\n- Retrieval quality — "
        "**Provisional**; deterministic token and character vectorizers prove the boundary, not "
        "semantic recall or ranking quality.\n- Source/knowledge inspection experience — "
        "**Complete**; the console "
        "spans sources through evidence packages and both provenance directions.\n- Model-guided "
        "intelligence — **Not Started**; TASK-007 can now consume packages without storage "
        "coupling.\n- Consulting workspace — **Not Started**; remains TASK-008.\n\nTASK-006 "
        "adds disposable governed access state, not a new authority. The next milestone is "
        "TASK-007 model-guided intelligence with explicit lineage and retrieval traces.\n",
    )
    write(
        "git-state.txt",
        "branch:\n"
        + git("branch", "--show-current")
        + "base origin/main:\n"
        + git("merge-base", "HEAD", "origin/main")
        + "HEAD:\n"
        + git("rev-parse", "HEAD")
        + "status:\n"
        + git("status", "--short", "--branch")
        + "commit state: TASK-006 changes are intentionally uncommitted; no Git write "
        "operation was run.\n",
    )


def secret_scan() -> tuple[int, str]:
    """Scan reviewable files for common plaintext credential signatures."""
    patterns = {
        "OpenAI key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
        "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    }
    findings: list[str] = []
    paths = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED for part in path.relative_to(ROOT).parts)
    ] + [path for path in PACKAGE.rglob("*") if path.is_file()]
    for path in paths:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in patterns.items():
            if pattern.search(content):
                findings.append(f"{label}: {path}")
    output = f"files scanned: {len(paths)}\nfindings: {len(findings)}\n"
    output += "result: PASS\n" if not findings else "result: FAIL\n" + "\n".join(findings)
    return (0 if not findings else 1), output


def build_manifest() -> None:
    """Create and independently verify the payload manifest and ZIP."""
    entries = [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(PACKAGE.rglob("*"))
        if path.is_file() and path.name not in {"review-manifest.json", "manifest-integrity.txt"}
    ]
    manifest = {"schema_version": 1, "task_id": TASK_ID, "files": entries}
    write("review-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    failures = [
        entry["path"]
        for entry in entries
        if digest(PACKAGE / entry["path"]) != entry["sha256"]
    ]
    write(
        "manifest-integrity.txt",
        f"manifest entries checked: {len(entries)}\nfailures: {len(failures)}\n"
        + ("result: PASS\n" if not failures else "result: FAIL\n"),
    )
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                relative = path.relative_to(PACKAGE).as_posix()
                archive.write(path, f"{TASK_ID}/{relative}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
    if bad is not None:
        raise RuntimeError(f"ZIP integrity failure: {bad}")
    ZIP_HASH.write_text(f"{digest(ZIP_PATH)}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Regenerate all required evidence and fail if any gate is incomplete."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    shutil.copy2(
        ROOT / "tasks/TASK-006-governed-retrieval-evidence-assembly-and-source-browser.md",
        PACKAGE / "task-ticket.md",
    )
    write("cumulative-task.patch", complete_patch())
    tracked = git("diff", "--name-only", "HEAD", "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    write("changed-files.txt", "\n".join(sorted(set(tracked + untracked))) + "\n")
    real_root = ROOT / ".artifacts/runtime/TASK-004-edgar"
    static_documents(real_root.is_dir())
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    validations = [
        (
            "focused-task006-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_task006", "-v"],
            environment,
        ),
        (
            "offline-proof-output.json.txt",
            [str(PYTHON), "scripts/task006_browser.py", "fixture-proof"],
            None,
        ),
        ("repository-validation-output.txt", ["make", "validate"], None),
        (
            "documentation-validation-output.txt",
            [str(PYTHON), "scripts/check_docs.py"],
            None,
        ),
        (
            "baseline-validation-output.txt",
            [str(PYTHON), "scripts/check_baseline.py"],
            None,
        ),
    ]
    failures: list[str] = []
    commands: list[str] = []
    for name, command, env in validations:
        code, output = run(command, env)
        write(name, output)
        commands.append(f"- `{' '.join(command)}` -> {code}")
        if code:
            failures.append(name)
    real_output = "result: BLOCKED\nTASK-004 runtime corpus absent\n"
    if real_root.is_dir():
        task005_command = [
            str(PYTHON),
            "scripts/task005_operator.py",
            "real-proof",
            "--acquisition-state",
            str(real_root.relative_to(ROOT)),
            "--state",
            ".artifacts/runtime/TASK-005-review",
        ]
        task005_code, task005_output = run(task005_command)
        write("task005-real-corpus-proof.json.txt", task005_output)
        commands.append(f"- `{' '.join(task005_command)}` -> {task005_code}")
        if task005_code:
            failures.append("task005-real-corpus-proof.json.txt")
        command = [
            str(PYTHON),
            "scripts/task006_browser.py",
            "real-proof",
            "--acquisition-state",
            str(real_root.relative_to(ROOT)),
            "--state",
            ".artifacts/runtime/TASK-006-review",
        ]
        code, real_output = run(command)
        commands.append(f"- `{' '.join(command)}` -> {code}")
        if code:
            failures.append("bounded-real-corpus-proof.json.txt")
    else:
        failures.append("bounded real corpus absent")
        write(
            "task005-real-corpus-proof.json.txt",
            "result: BLOCKED\nTASK-004 runtime corpus absent\n",
        )
    write("bounded-real-corpus-proof.json.txt", real_output)
    write(
        "validation-commands.md",
        "# Validation commands and results\n\n" + "\n".join(commands) + "\n",
    )
    write(
        "retrieval-contract-examples.md",
        "# Retrieval contract examples\n\nThe complete offline proof below contains source-only, "
        "knowledge-only, combined vector-plus-metadata, empty, and bounded queries with typed "
        "results.\n\n```text\n"
        + (PACKAGE / "offline-proof-output.json.txt").read_text()
        + "```\n",
    )
    write(
        "evidence-package-examples.md",
        "# Evidence-package examples\n\nThe real proof contains complete and budget-bounded "
        "packages with exact contexts, provenance, omissions, gaps, conflicts, and byte use. "
        "See `bounded-real-corpus-proof.json.txt`.\n",
    )
    write(
        "retrieval-traces.md",
        "# Retrieval traces\n\nComplete traces are embedded in both proof outputs. Every candidate "
        "has an inclusion or exclusion reason, component scores where applicable, the authority "
        "fingerprint, generation, exact query, coverage notes, and truncation state.\n",
    )
    write(
        "source-browser-demonstration.md",
        "# Source-browser and inspection demonstration\n\nThe real proof's "
        "`inspection_workflow` inventories governed sources, documents, artifacts, source "
        "objects, and knowledge; follows both provenance directions; and links included/excluded "
        "decisions to a trace and complete evidence package. Console commands are documented in "
        "`docs/governed-retrieval-and-source-browser.md`.\n",
    )
    write(
        "rebuild-and-failure-evidence.md",
        "# Rebuild and failure evidence\n\nBoth proof outputs reproduce an identical index "
        "generation, retain the prior pointer after injected failure, run independent token and "
        "character vectorizers through contract-level validation, and show missing/corrupt index "
        "health. Replaceability covers nested schema/types, authority classes, every exact "
        "provenance reference, budgets, omissions, truncation, coverage, conflict/ambiguity, "
        "vectorizer-field absence, deterministic constrained selections, and explicit legitimate "
        "ranking/selection divergence. "
        "Focused tests additionally cover stale authority, vector failure, unsupported metadata, "
        "provenance/artifact failure, empty results, conflicts, and evidence budgets.\n",
    )
    if real_root.is_dir() and "exit_code: 0" in real_output:
        payload_text = real_output.split("\n", maxsplit=1)[1].rsplit(
            "exit_code:", maxsplit=1
        )[0]
        payload = json.loads(payload_text)
        replaceability = payload["rebuild_and_replaceability"][
            "contract_level_replaceability"
        ]
        write(
            "vectorizer-replaceability-evidence.json",
            json.dumps(replaceability, indent=2, sort_keys=True) + "\n",
        )
    scan_code, scan_output = secret_scan()
    write("secret-scan-output.txt", scan_output)
    if scan_code:
        failures.append("secret-scan-output.txt")
    build_manifest()
    print(f"package: {PACKAGE}")
    print(f"zip: {ZIP_PATH}")
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
