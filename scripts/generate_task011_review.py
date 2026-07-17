#!/usr/bin/env python3
"""Generate the independently reviewable TASK-011 evidence package."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-011"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
ZIP_READBACK = REVIEW_ROOT / f"{TASK_ID}-review.zip.readback.json"
BROWSER_EVIDENCE = ROOT / ".artifacts/review-input/TASK-011/browser"
SOURCE_ARCHIVE = ROOT / ".artifacts/build/rfi-1-source.zip"
EXCLUDED = {".artifacts", ".git", ".venv", "__pycache__"}


def digest(path: Path) -> str:
    """Return one file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    """Run one read-only Git command."""
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


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(name: str, command: list[str]) -> dict[str, object]:
    """Run and retain one repeatable validation."""
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


def task_base() -> str:
    """Return the branch point used for cumulative provenance."""
    return git("merge-base", "main", "HEAD").strip()


def changed_files(base: str) -> list[str]:
    """Return tracked and untracked task files, excluding ignored generated evidence."""
    tracked = git("diff", "--name-only", base, "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def complete_patch(base: str) -> str:
    """Render tracked and untracked task changes as one cumulative patch."""
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


def secret_scan() -> tuple[int, str]:
    """Scan reviewable source text for common plaintext credential signatures."""
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
        if path.suffix not in {".py", ".md", ".json", ".toml", ".txt", ".html"}:
            continue
        checked += 1
        content = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in patterns.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: {name}")
    output = f"files_checked: {checked}\nfindings: {len(findings)}\n"
    output += "result: PASS\n" if not findings else "result: FAIL\n"
    if findings:
        output += "\n".join(findings) + "\n"
    return (1 if findings else 0), output


def copy_browser_evidence() -> dict[str, Any]:
    """Require and copy evidence created through the real browser surface."""
    proof_path = BROWSER_EVIDENCE / "browser-proof.json"
    if not proof_path.is_file():
        raise RuntimeError(f"missing browser proof: {proof_path}")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    required = {
        "seeded_browse_and_search",
        "typed_create_and_edit",
        "help_keyboard",
        "help_click",
        "identifier_conflict",
        "draft_preserved_after_failure",
        "revision_preview",
        "unsaved_change_warning",
        "immutable_save_and_history",
        "restart_persistence",
        "narrow_window",
        "relationship_graph_deferred",
    }
    missing = sorted(name for name in required if proof.get("checks", {}).get(name) is not True)
    if missing:
        raise RuntimeError(f"browser proof is incomplete: {missing}")
    destination = PACKAGE / "browser"
    shutil.copytree(BROWSER_EVIDENCE, destination)
    if len(list(destination.glob("*.png"))) < 5:
        raise RuntimeError("browser proof requires at least five screenshots")
    return proof


def contract_examples(proof: dict[str, Any]) -> None:
    """Write review-friendly public contract, seed, persistence, and failure evidence."""
    write(
        "contracts/target-firm-examples.json",
        json.dumps(
            {
                "seeded_firms": proof["seeded_firms"],
                "created_and_revised": proof["created_and_revised"],
                "stable_reference": proof["integration_reference"],
                "relationship_field_absent": "relationships" not in proof["created_and_revised"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    write(
        "evidence/validation-failure.json",
        json.dumps({"identifier_conflict": proof["conflict"]}, indent=2, sort_keys=True)
        + "\n",
    )
    write(
        "evidence/persistence-proof.json",
        json.dumps(
            {
                "restart_persistence": proof["checks"]["restart_persistence"],
                "immutable_revision": proof["checks"]["immutable_revision"],
                "integrity": proof["checks"]["integrity"],
                "record": proof["created_and_revised"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def summaries(files: list[str]) -> None:
    """Write the required human-oriented review summaries."""
    write(
        "implementation-summary.md",
        """# TASK-011 implementation summary

TASK-011 creates a separate immutable identity-and-recognition authority, public service, and stable
reference; seeds Seagate, Western Digital, and Toshiba; and adds a Target Firms browser/editor to
the existing admin console. Relationship fields were removed from contracts, persistence, service
payloads, seeds, and GUI controls. The GUI reuses TASK-010's typed list/detail/edit/validate/
preview/save pattern, central field help, dirty-state protection, failure preservation, and
local-only HTTP boundary.

The package's `contracts/`, `evidence/`, `browser/`, and `validation/` directories contain exact
contract examples, seed data, conflict and restart proof, real browser evidence, and command output.
""",
    )
    write(
        "architecture-summary.md",
        """# TASK-011 architecture summary

`rfi.firms` owns who a consulting target is and how it can be recognized. `FirmRepository` owns
immutable revision persistence; `FirmService` is the application boundary; the admin adapter owns
HTTP only. Evidence remains what was published, concepts/observations remain what was defined or
asserted, and workspaces/intelligence remain how research is used.

Future layers use `FirmReference(firm_id, optional firm_revision_id)` and do not import firm
persistence. Business and corporate-network relationships are explicitly excluded and belong in a
future evidence-backed graph with provenance, validity, confidence, and source support. See
ADR-0011 and the subsystem guide for decisions, tradeoffs, extension points, and known limitations.

## Architectural Status Summary

- Target-firm authority: **Complete for local consulting use**.
- Recognition model: **Usable with limitations**; not a security master or final hierarchy.
- Firm browser/editor: **Complete for TASK-011** and aligned with TASK-010 conventions.
- Seeded HDD consulting proof: **Complete** for Seagate, Western Digital, and Toshiba.
- Source/knowledge integration: **Identity boundary complete; attachment not started**.
- Next milestone: firm-scoped acquisition policy and inspectable source coverage.
""",
    )
    changed = "\n".join(f"- `{item}`" for item in files)
    write("changed-files.md", f"# Changed files\n\n{changed}\n")
    write(
        "integration-readiness-and-limitations.md",
        """# Integration readiness, limitations, and follow-on

Stable `firm_id` references are ready for acquisition policies, source/document associations,
observations, workspaces, and question context without direct persistence coupling. Exact revision
pins are available when historical recognition semantics matter.

Known limitations: exact identifier/domain normalization, no relationship graph or corporate-action
policy, no automatic discovery, proof seed data without live refresh, no firm/source join
repository yet, and a local unauthenticated single-user console.

Recommended follow-on: attach governed source acquisition policies and source coverage to
`FirmReference`; build business and corporate-network edges only in a separate evidence-backed
relationship graph whose assertions retain source support, validity, provenance, and confidence.
""",
    )


def file_records(excluded_names: set[str] | None = None) -> list[dict[str, object]]:
    """Describe package files for independent digest verification."""
    excluded_names = excluded_names or set()
    return [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": digest(path),
            "size": path.stat().st_size,
        }
        for path in sorted(PACKAGE.rglob("*"))
        if path.is_file() and path.name not in excluded_names
    ]


def write_zip() -> None:
    """Create the review ZIP from current package contents."""
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")


def verify_zip(records: list[dict[str, object]]) -> dict[str, object]:
    """Read every manifested file from the ZIP and verify its digest."""
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"corrupt ZIP member: {bad_member}")
        for record in records:
            member = f"{TASK_ID}/{record['path']}"
            if hashlib.sha256(archive.read(member)).hexdigest() != record["sha256"]:
                raise RuntimeError(f"archive digest mismatch: {member}")
        members = len(archive.namelist())
    return {
        "algorithm": "SHA-256",
        "archive_crc": "PASS",
        "manifested_entries_verified": len(records),
        "members": members,
        "result": "PASS",
    }


def finalize(metadata: dict[str, Any]) -> None:
    """Create a manifested archive, read it back, and write external checksums."""
    records = file_records({"manifest.json", "integrity-readback.json"})
    write(
        "manifest.json",
        json.dumps({**metadata, "schema_version": 1, "files": records}, indent=2, sort_keys=True)
        + "\n",
    )
    manifest = {
        "path": "manifest.json",
        "sha256": digest(PACKAGE / "manifest.json"),
        "size": (PACKAGE / "manifest.json").stat().st_size,
    }
    verified = [*records, manifest]
    write_zip()
    readback = verify_zip(verified)
    write("integrity-readback.json", json.dumps(readback, indent=2, sort_keys=True) + "\n")
    write_zip()
    final = verify_zip(verified)
    final.update({"archive": ZIP_PATH.name, "sha256": digest(ZIP_PATH)})
    ZIP_HASH.write_text(f"{final['sha256']}  {ZIP_PATH.name}\n", encoding="utf-8")
    ZIP_READBACK.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    """Regenerate complete TASK-011 evidence and fail if any proof is absent."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    python = str(Path(sys.executable))
    base = task_base()
    files = changed_files(base)
    write("provenance/cumulative-task.patch", complete_patch(base))
    write("provenance/changed-files.txt", "\n".join(files) + "\n")
    write(
        "provenance/git-state.txt",
        f"branch: {git('branch', '--show-current').strip()}\nbase: {base}\n"
        f"HEAD: {git('rev-parse', 'HEAD').strip()}\nstatus:\n{git('status', '--short')}\n",
    )
    summaries(files)
    (PACKAGE / "documents").mkdir()
    for source in (
        "docs/target-firm-catalog-and-admin-editor.md",
        "docs/decisions/0011-immutable-target-firm-identity-authority.md",
        "tasks/TASK-011-target-firm-catalog-browser-and-admin-editor.md",
    ):
        shutil.copy2(ROOT / source, PACKAGE / "documents" / Path(source).name)
    browser = copy_browser_evidence()
    results = [
        run("task011-proof", [python, "scripts/task011_firms.py", "fixture-proof"]),
        run("task011-tests", [python, "-m", "unittest", "tests.test_task011", "-v"]),
        run("full-validation", ["make", "validate"]),
    ]
    proof_output = subprocess.run(
        [python, "scripts/task011_firms.py", "fixture-proof"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout
    proof = json.loads(proof_output)
    contract_examples(proof)
    if not SOURCE_ARCHIVE.is_file():
        raise RuntimeError("full validation did not produce the source archive")
    (PACKAGE / "source").mkdir()
    shutil.copy2(SOURCE_ARCHIVE, PACKAGE / "source/rfi-1-source.zip")
    scan_code, scan_output = secret_scan()
    write("validation/secret-scan.txt", scan_output)
    failures = [str(item["name"]) for item in results if item["exit_code"] != 0]
    if scan_code:
        failures.append("secret-scan")
    metadata = {
        "task": TASK_ID,
        "result": "PASS" if not failures else "FAIL",
        "base": base,
        "changed_files": files,
        "validations": results,
        "browser_checks": browser["checks"],
        "failures": failures,
    }
    finalize(metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    print(f"package: {PACKAGE}\nzip: {ZIP_PATH}\nchecksum: {ZIP_HASH}\nreadback: {ZIP_READBACK}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
