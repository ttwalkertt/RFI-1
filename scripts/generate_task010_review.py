#!/usr/bin/env python3
"""Generate the independently reviewable TASK-010 evidence package."""

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
TASK_ID = "TASK-010"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
ZIP_READBACK = REVIEW_ROOT / f"{TASK_ID}-review.zip.readback.json"
BROWSER_EVIDENCE = ROOT / ".artifacts/review-input/TASK-010/browser"
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
    """Write one UTF-8 package artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(name: str, command: list[str]) -> dict[str, object]:
    """Run and retain one independently repeatable validation."""
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
    """Return the branch point used for the complete review patch."""
    return git("merge-base", "main", "HEAD").strip()


def changed_files(base: str) -> list[str]:
    """Return tracked and untracked task files without generated artifacts."""
    tracked = git("diff", "--name-only", base, "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def complete_patch(base: str) -> str:
    """Render tracked and untracked changes as one cumulative binary-safe patch."""
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
    """Scan reviewable repository text for common plaintext credential signatures."""
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
    """Require and copy evidence created through the actual browser surface."""
    proof_path = BROWSER_EVIDENCE / "browser-proof.json"
    if not proof_path.is_file():
        raise RuntimeError(f"missing browser proof: {proof_path}")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    required_checks = {
        "typed_hamr_edit",
        "help_keyboard",
        "help_click",
        "inline_validation",
        "page_validation_summary",
        "draft_preserved_after_failure",
        "revision_preview",
        "unsaved_change_warning",
        "immutable_save_and_history",
        "restart_persistence",
        "narrow_window",
    }
    checks = proof.get("checks", {})
    missing = sorted(name for name in required_checks if checks.get(name) is not True)
    if missing:
        raise RuntimeError(f"browser proof is incomplete: {missing}")
    destination = PACKAGE / "browser"
    shutil.copytree(BROWSER_EVIDENCE, destination)
    screenshots = sorted(destination.glob("*.png"))
    if len(screenshots) < 6:
        raise RuntimeError("browser proof requires at least six screenshots")
    return proof


def file_records(excluded_names: set[str] | None = None) -> list[dict[str, object]]:
    """Describe package payload files for independent digest verification."""
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
    """Read every manifested payload back from the ZIP and verify its digest."""
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"corrupt ZIP member: {bad_member}")
        for record in records:
            member = f"{TASK_ID}/{record['path']}"
            archived = archive.read(member)
            if hashlib.sha256(archived).hexdigest() != record["sha256"]:
                raise RuntimeError(f"archive digest mismatch: {member}")
        members = archive.namelist()
    return {
        "algorithm": "SHA-256",
        "archive_crc": "PASS",
        "manifested_entries_verified": len(records),
        "members": len(members),
        "result": "PASS",
    }


def build_package_manifest(metadata: dict[str, Any]) -> dict[str, Any]:
    """Build, read back, and checksum the final package."""
    records = file_records({"manifest.json", "integrity-readback.json"})
    manifest = {
        **metadata,
        "schema_version": 2,
        "files": records,
    }
    write("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest_record = {
        "path": "manifest.json",
        "sha256": digest(PACKAGE / "manifest.json"),
        "size": (PACKAGE / "manifest.json").stat().st_size,
    }
    verified_records = [*records, manifest_record]
    write_zip()
    readback = verify_zip(verified_records)
    readback["self_exclusion"] = (
        "integrity-readback.json is excluded from its own digest set; all other payload files "
        "and manifest.json are verified"
    )
    write(
        "integrity-readback.json",
        json.dumps(readback, indent=2, sort_keys=True) + "\n",
    )
    write_zip()
    final_readback = verify_zip(verified_records)
    final_readback.update(
        {
            "archive": ZIP_PATH.name,
            "sha256": digest(ZIP_PATH),
            "integrity_readback_present": True,
        }
    )
    with zipfile.ZipFile(ZIP_PATH) as archive:
        archive.read(f"{TASK_ID}/integrity-readback.json")
    ZIP_HASH.write_text(
        f"{final_readback['sha256']}  {ZIP_PATH.name}\n",
        encoding="utf-8",
    )
    ZIP_READBACK.write_text(
        json.dumps(final_readback, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    """Regenerate review evidence and fail when any required proof is absent."""
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    python = str(Path(sys.executable))
    base = task_base()
    files = changed_files(base)
    write("provenance/cumulative-task.patch", complete_patch(base))
    write("provenance/changed-files.txt", "\n".join(files) + "\n")
    write(
        "provenance/git-state.txt",
        f"branch: {git('branch', '--show-current').strip()}\n"
        f"base: {base}\nHEAD: {git('rev-parse', 'HEAD').strip()}\n"
        f"status:\n{git('status', '--short')}\n",
    )
    (PACKAGE / "documents").mkdir()
    for source in (
        "docs/admin-console-schema-aware-editor.md",
        "docs/decisions/0010-schema-aware-admin-console-editor.md",
        "tasks/TASK-010-GUI_Editor_updates.md",
    ):
        shutil.copy2(ROOT / source, PACKAGE / "documents" / Path(source).name)
    browser_proof = copy_browser_evidence()
    results = [
        run("task010-proof", [python, "scripts/task010_admin_console.py", "fixture-proof"]),
        run("task010-tests", [python, "-m", "unittest", "tests.test_task010", "-v"]),
        run("full-tests", [python, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        run("lint", [python, "scripts/quality.py", "lint"]),
        run("format", [python, "scripts/quality.py", "format"]),
        run("typecheck", [python, "scripts/quality.py", "typecheck"]),
        run("docs", [python, "scripts/check_docs.py"]),
        run("baseline", [python, "scripts/check_baseline.py"]),
        run("source-archive", [python, "scripts/build_source_archive.py"]),
    ]
    if not SOURCE_ARCHIVE.is_file():
        raise RuntimeError("source archive command did not produce its declared output")
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
        "browser_checks": browser_proof["checks"],
        "failures": failures,
    }
    build_package_manifest(metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    print(f"package: {PACKAGE}")
    print(f"zip: {ZIP_PATH}")
    print(f"checksum: {ZIP_HASH}")
    print(f"readback: {ZIP_READBACK}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
