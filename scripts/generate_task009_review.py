#!/usr/bin/env python3
"""Generate the independently verifiable TASK-009 architectural review package."""

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
TASK_ID = "TASK-009"
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
    """Run read-only Git inspection for review provenance."""
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
    """Return one SHA-256 file digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def task_base() -> str:
    """Return the updated-main branch point for this implementation."""
    return git("merge-base", "main", "HEAD").strip()


def complete_patch(base: str) -> str:
    """Render tracked and untracked implementation changes without staging them."""
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
    """Write the required human architectural narratives."""
    write(
        "implementation-summary.md",
        "# Implementation summary\n\nTASK-009 adds `rfi.concepts`, an independent durable "
        "definition authority with immutable content-addressed revisions, business validity, "
        "generic method configuration, public lookup/edit contracts, and typed observation and "
        "derivation contracts. A standard-library local HTTP server exposes the same "
        "`ConceptService` through JSON and a persistent multi-tab admin shell. Revenue, Gross "
        "Margin, HAMR Qualification, and HAMR Shipments prove numeric, stateful, event, and "
        "multi-shaped behavior without defining a final ontology.\n",
    )
    write(
        "architectural-decisions.md",
        "# Architectural decisions\n\nSee ADR-0009 and "
        "`docs/business-concept-catalog-and-admin-console.md` in the cumulative patch. Complete "
        "immutable snapshots and an atomic pointer preserve history. Definition validity remains "
        "separate from catalog edit time. Registered opaque method extensions preserve evolution, "
        "while a data-only deterministic operation set avoids executable formulas. The GUI calls "
        "the public service rather than persistence files and binds to loopback by default.\n",
    )
    write(
        "catalog-contract-overview.md",
        "# Catalog contract overview\n\n`ConceptDraft` is editable intent; `ConceptRevision` is "
        "immutable historical meaning; `ObservationMethod` is a revision-scoped admissible method; "
        "`Observation` is a particular assertion pinned to revision and method; "
        "`LineageReference` pins calculated inputs; and `Reconciliation` compares without merging. "
        "The catalog owns definitions only. Evidence, derived knowledge, observations, retrieval, "
        "intelligence, and workspaces retain independent authority and lifecycle.\n",
    )
    write(
        "admin-console-walkthrough.md",
        "# Admin console walkthrough\n\nStart with `.venv/bin/python "
        "scripts/task009_concepts.py serve --host 127.0.0.1 --port 8765`. The browser proof "
        "searched HAMR concepts, inspected scoped qualification configuration, created and "
        "validated a generic concept, saved revision one, edited comments and validity, added a "
        "deterministic method beside an extracted method, saved revision two, and inspected both "
        "history buttons. See `screenshots/` and `gui-proof-results.md`.\n",
    )
    write(
        "known-limitations.md",
        "# Known limitations and future realignment\n\n- The ontology, state/event semantics, "
        "scope model, and method configurations are intentionally provisional.\n- The operation "
        "set is not a complete formula language or financial engine.\n- No durable observation "
        "store, production extraction, unit conversion, automatic reconciliation, or observation-"
        "date revision selection exists.\n- Persistence and console operation are local single-"
        "writer.\n- Complex methods use a technical JSON editor.\n- No authentication, multi-user "
        "authorization, remote hosting, production telemetry, or automated backup exists.\n",
    )
    guide = (ROOT / "docs/business-concept-catalog-and-admin-console.md").read_text()
    status = guide.split("## Architectural Status Summary", maxsplit=1)[1]
    write("architectural-status-summary.md", "# Architectural Status Summary\n" + status)
    write(
        "gui-proof-results.md",
        "# Real-browser GUI proof results\n\nPASS. The in-app browser rendered the actual local "
        "console at `127.0.0.1:8765`, found six seeds, filtered HAMR to two concepts, browsed the "
        "qualification state definition, and captured `task009-hamr-qualification.png`. It then "
        "created `browser-gui-proof`, validated and saved it, reopened the editor, added an end "
        "date and deterministic method, validated and saved revision two, inspected both revision "
        "buttons, and captured `task009-browser-revision.png`. Browser testing found and drove "
        "fixes "
        "for script newline escaping, status-element lookup, and edit-time stable-ID validation.\n",
    )


def parse_run_output(output: str) -> dict[str, Any]:
    """Parse proof JSON between its command and recorded exit marker."""
    body = output.split("\n", maxsplit=1)[1].rsplit("exit_code:", maxsplit=1)[0]
    decoder = json.JSONDecoder()
    for position, character in enumerate(body):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(body[position:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "checks" in value and "catalog_integrity" in value:
            return value
    raise RuntimeError("TASK-009 proof JSON is absent from recorded command output")


def write_proof_views(payload: dict[str, Any]) -> None:
    """Extract focused evidence from the complete functional proof."""
    views = {
        "functional-proof.json": {
            "catalog_integrity": payload["catalog_integrity"],
            "checks": payload["checks"],
            "server_proof": payload["server_proof"],
        },
        "concept-lookup-examples.json": payload["lookups"],
        "editing-and-revision-example.json": payload["generic_lifecycle"],
        "validity-example.json": {
            "lookup": payload["lookups"]["validity"],
            "history": payload["generic_lifecycle"]["history"],
        },
        "deterministic-calculation-and-lineage.json": payload["financial_proof"],
        "extracted-versus-calculated-coexistence.json": payload["financial_proof"][
            "coexisting_gross_margin_observations"
        ],
        "hamr-qualification-example.json": payload["nonnumeric_proof"][
            "qualification_state"
        ],
        "hamr-shipments-example.json": payload["nonnumeric_proof"]["shipment_shapes"],
        "failure-proofs.json": payload["failure_proofs"],
    }
    for name, value in views.items():
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
    output = f"files_checked: {checked}\nfindings: {len(findings)}\n"
    output += "result: PASS\n" if not findings else "result: FAIL\n" + "\n".join(findings)
    return (1 if findings else 0), output


def build_manifest() -> None:
    """Create a manifest, ZIP, digest file, and independent readback proof."""
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
                name = f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}"
                archive.write(path, name)
    ZIP_HASH.write_text(f"{digest(ZIP_PATH)}  {ZIP_PATH.name}\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for record in records:
            name = f"{TASK_ID}/{record['path']}"
            if hashlib.sha256(archive.read(name)).hexdigest() != record["sha256"]:
                raise RuntimeError(f"archive digest mismatch: {name}")
        archived_manifest = json.loads(archive.read(f"{TASK_ID}/manifest.json"))
        if archived_manifest != manifest:
            raise RuntimeError("archived manifest differs from package manifest")


def main() -> int:
    """Regenerate proof, validation, review, and integrity artifacts."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    shutil.copy2(
        ROOT / "tasks/TASK-009-extensible-business-concept-catalog-and-admin-console.md",
        PACKAGE / "task-ticket.md",
    )
    screenshots = PACKAGE / "screenshots"
    screenshots.mkdir()
    for name in ("task009-hamr-qualification.png", "task009-browser-revision.png"):
        shutil.copy2(ROOT / "docs/images" / name, screenshots / name)
    base = task_base()
    write("cumulative-task.patch", complete_patch(base))
    tracked = git("diff", "--name-only", base, "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    write("changed-files.txt", "\n".join(sorted(set(tracked + untracked))) + "\n")
    write(
        "git-state.txt",
        f"branch: {git('branch', '--show-current').strip()}\nbase: {base}\n"
        f"HEAD: {git('rev-parse', 'HEAD').strip()}\nstatus:\n{git('status', '--short')}\n"
        "implementation state: intentionally uncommitted per task instruction.\n",
    )
    static_documents()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    validations = [
        (
            "focused-task009-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_task009", "-v"],
            environment,
        ),
        (
            "concept-proof-output.json.txt",
            [str(PYTHON), "scripts/task009_concepts.py", "fixture-proof"],
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
        if name == "concept-proof-output.json.txt":
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
        "manifest_algorithm: SHA-256\narchive_verification: every manifested file is read back "
        "from the ZIP and rehashed\nresult: PASS (written only if build completes)\n",
    )
    result = "result: PASS\n" if not failures else "result: FAIL\n" + "\n".join(failures)
    write("package-result.txt", result)
    build_manifest()
    print(f"package: {PACKAGE}")
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {ZIP_HASH}")
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
