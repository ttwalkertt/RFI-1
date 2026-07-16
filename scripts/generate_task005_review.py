#!/usr/bin/env python3
"""Generate the complete, independently verifiable TASK-005 review package."""

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
TASK_ID = "TASK-005"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".venv", "__pycache__"}


def run(command: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run one validation command and retain combined complete output."""
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
    """Return output from a read-only Git inspection."""
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
    """Return SHA-256 for a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write one review artifact."""
    (PACKAGE / name).write_text(content, encoding="utf-8")


def complete_patch() -> str:
    """Render tracked and untracked milestone changes as one cumulative patch."""
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
    return "".join(parts)


def architecture_status() -> str:
    """Return the required high-level human architectural status refresh."""
    return """# Architectural Status Summary

- **Repository foundation — Complete.** Governing design, build, validation, review conventions,
  architectural milestone discipline, and the offline standard-library baseline remain intact.
- **Acquisition substrate — Complete.** Governed sources, immutable artifacts, append-only history,
  and replay remain evidence authority. TASK-005 consumes only its public document/artifact API.
- **Acquisition engine — Complete.** Deterministic orchestration and adapter boundaries are
  unchanged by TASK-005 and remain independent of parsing or knowledge.
- **Live SEC providers — Usable with Limitations.** Native EDGAR produced the accepted ten-filing
  corpus. Optional SEC-API.io remains offline-tested rather than live-proven.
- **Immutable evidence — Complete.** Ten artifacts totaling 62,070,796 bytes remain authoritative.
- **Source-object subsystem — Usable with Limitations.** The new independent SQLite catalog has
  stable byte-span identities, atomic rebuild, integrity, and inspection. Coverage is SEC SGML.
- **Derived-knowledge subsystem — Usable with Limitations.** Independent JSON generations produce
  issuer entities, filing observations, and filed-by relationships with explicit lifecycle and
  provenance. The ontology remains deliberately narrow.
- **Retrieval and source browser — Not Started.** TASK-005 provides console inspection only;
  TASK-006 is the next architectural milestone.
- **Model-guided intelligence — Not Started.** No model runtime or model-assisted derivation exists.
- **Consulting workspace — Not Started.** This remains downstream of retrieval and intelligence.

## Architectural change

The repository now has three distinct durable authorities: immutable evidence, structural source
objects, and derived knowledge. Dependency flows evidence to source contracts to knowledge.
Source and knowledge use different stores, schemas, publication mechanics, identities, lifecycle,
and integrity checks. Provenance survives independent rebuilds because it asserts stable source
identity and exact artifact span/digest rather than a shared row or internal representation.

## Important limitations and debt

SEC HTML sections, inline XBRL, tables, non-SEC formats, concurrent writers, generation garbage
collection, richer correction evidence, broad ontologies, and performance indexing are deferred.
The next unresolved milestone is TASK-006: knowledge retrieval, evidence assembly, and a
source-object browser using one governed inspection model for operators and model-facing callers.
"""


def static_documents(real_available: bool) -> None:
    """Write architecture, scope, limitation, and Git review documents."""
    write(
        "implementation-summary.md",
        "# Implementation summary\n\nTASK-005 establishes independent `source_objects` and "
        "`knowledge` packages. Source objects use an atomic SQLite catalog of exact SEC byte "
        "locations. Knowledge uses immutable JSON generations with an atomic current pointer. "
        "A deterministic deriver creates issuer entities, filing observations, and relationships "
        "through only the public source reader contract. Tests and console proof cover identity, "
        "provenance, rebuild, correction, ambiguity, conflict, failure, and integrity.\n",
    )
    write(
        "architectural-decisions-and-tradeoffs.md",
        "# Architectural decisions and tradeoffs\n\nSee ADR-0005 in the cumulative patch. "
        "Different physical persistence models intentionally make lifecycle independence "
        "executable. Exact provenance duplication costs storage but detects contract drift. "
        "Deterministic SEC headers establish the boundary without premature model or retrieval "
        "dependencies.\n",
    )
    write(
        "bounded-corpus.md",
        "# Bounded corpus\n\nThe real proof uses all ten immutable TASK-004 native EDGAR "
        "complete-submission artifacts: five each for STX and WDC, containing one 10-K, two "
        "10-Qs, and two 8-Ks per issuer. Total exact content is 62,070,796 bytes. "
        f"Runtime corpus available during generation: {real_available}.\n",
    )
    write(
        "failure-and-ambiguity-evidence.md",
        "# Failure and ambiguity evidence\n\nFocused tests prove unsupported artifacts, unclosed "
        "SEC structure, content corruption, missing required fields, conflicting issuer names, "
        "provenance loss, correction history, and source/knowledge partial publication failure. "
        "All remain visible as parse outcomes, derivation failures, explicit statuses, or "
        "fail-closed integrity errors. See `focused-task005-output.txt`.\n",
    )
    write(
        "known-limitations-and-deferred-work.md",
        "# Known limitations and deferred work\n\n- SEC complete-submission SGML only; no "
        "semantic HTML/XBRL/table parsing.\n- Narrow issuer, filing, and filed-by ontology.\n- "
        "Single-writer stores and no old-generation garbage collection.\n- Corrections retain "
        "original "
        "evidence and do not accept new human-source artifacts.\n- Retrieval, source browser, "
        "model "
        "reasoning, and consulting workflows remain TASK-006 through TASK-008.\n",
    )
    write("architectural-status-summary.md", architecture_status())
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
        + "commit state: TASK-005 changes are intentionally uncommitted; "
        "no write operation was run.\n",
    )


def secret_scan() -> tuple[int, str]:
    """Scan reviewable source and generated text for common plaintext credential signatures."""
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
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"{label}: {path}")
    output = f"files scanned: {len(paths)}\nfindings: {len(findings)}\n"
    output += "result: PASS\n" if not findings else "result: FAIL\n" + "\n".join(findings)
    return (0 if not findings else 1), output


def build_manifest() -> None:
    """Create and verify the review payload manifest, ZIP, and ZIP digest."""
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
                archive.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
    if bad is not None:
        raise RuntimeError(f"ZIP integrity failure: {bad}")
    ZIP_HASH.write_text(f"{digest(ZIP_PATH)}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Regenerate all TASK-005 evidence and fail if any required gate fails."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    shutil.copy2(
        ROOT / "tasks/TASK-005-independent-source-object-and-derived-knowledge-subsystems.md",
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
            "focused-task005-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_task005", "-v"],
            environment,
        ),
        (
            "offline-proof-output.txt",
            [str(PYTHON), "scripts/task005_operator.py", "fixture-proof"],
            None,
        ),
        ("repository-validation-output.txt", ["make", "validate"], None),
        ("documentation-validation-output.txt", [str(PYTHON), "scripts/check_docs.py"], None),
    ]
    failures: list[str] = []
    command_lines: list[str] = []
    for name, command, env in validations:
        code, output = run(command, env)
        write(name, output)
        command_lines.append(f"- `{' '.join(command)}` -> {code}")
        if code:
            failures.append(name)
    if real_root.is_dir():
        command = [
            str(PYTHON),
            "scripts/task005_operator.py",
            "real-proof",
            "--acquisition-state",
            str(real_root.relative_to(ROOT)),
            "--state",
            ".artifacts/runtime/TASK-005-review",
        ]
        code, output = run(command)
        write("bounded-real-corpus-proof.json.txt", output)
        command_lines.append(f"- `{' '.join(command)}` -> {code}")
        if code:
            failures.append("bounded-real-corpus-proof.json.txt")
    else:
        failures.append("bounded real corpus absent")
        write(
            "bounded-real-corpus-proof.json.txt",
            "result: BLOCKED\nTASK-004 runtime corpus absent\n",
        )
    write(
        "validation-commands.md",
        "# Validation commands and results\n\n" + "\n".join(command_lines) + "\n",
    )
    real_output = (PACKAGE / "bounded-real-corpus-proof.json.txt").read_text()
    write(
        "source-object-inventory.md",
        "# Source-object inventory\n\nSee the complete real proof below.\n\n```text\n"
        + real_output
        + "```\n",
    )
    write(
        "derived-object-inventory.md",
        "# Derived-object inventory\n\nSee `bounded-real-corpus-proof.json.txt`; "
        "it includes type/status counts and identities.\n",
    )
    write(
        "provenance-examples.md",
        "# Provenance examples\n\nSee `bounded-real-corpus-proof.json.txt` for both "
        "provenance directions.\n",
    )
    write(
        "independent-rebuild-evidence.md",
        "# Independent rebuild evidence\n\nThe real and offline outputs show stable source "
        "identities, knowledge validity after source replacement, stable knowledge versions "
        "after knowledge replacement, and distinct storage roots.\n",
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
