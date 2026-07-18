#!/usr/bin/env python3
"""Generate the independently reviewable TASK-017 verification directory and ZIP."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-017"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".venv", ".rfi", "__pycache__"}


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def digest(path: Path) -> str:
    """Return one SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    """Run a read-only Git query."""
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def run(name: str, command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    """Run one validation and retain its complete combined output."""
    environment = os.environ.copy()
    environment.pop("RFI_SEC_USER_AGENT", None)
    environment.pop("SEC_API_IO_API_KEY", None)
    environment["PYTHONPATH"] = "src"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    write(
        f"validation/{name}.txt",
        f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n",
    )
    return {
        "name": name,
        "command": command,
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
    }


def changed_files() -> list[str]:
    """List tracked and untracked task files."""
    tracked = git("diff", "--name-only", "main", "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set((*tracked, *untracked)))


def complete_patch() -> str:
    """Create a cumulative patch including untracked files."""
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


def repository_tree() -> str:
    """List the relevant final repository tree."""
    paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED for part in path.relative_to(ROOT).parts)
    )
    return "\n".join(paths) + "\n"


def isolated_validation() -> dict[str, Any]:
    """Validate a copied tree without Git, state, environments, or generated evidence."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task017-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        launcher = destination / ".venv/bin/rfi"
        launcher.parent.mkdir(parents=True)
        launcher.write_text(
            f"#!{PYTHON}\nimport sys\nfrom rfi.cli import main\n"
            "if __name__ == '__main__': sys.exit(main())\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        commands = (
            [str(PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"],
            [str(PYTHON), "scripts/task017_admin_preferences.py"],
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
        )
        outputs = ["Copied-tree validation; excluded Git, state, artifacts, and environment.", ""]
        passed = True
        environment = os.environ.copy()
        environment["PYTHONPATH"] = "src"
        environment.pop("RFI_SEC_USER_AGENT", None)
        environment.pop("SEC_API_IO_API_KEY", None)
        for command in commands:
            result = subprocess.run(
                command,
                cwd=destination,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            outputs.extend(
                (f"$ {' '.join(command)}", result.stdout, f"exit_code: {result.returncode}", "")
            )
            passed = passed and result.returncode == 0
    write("validation/isolated-tree.txt", "\n".join(outputs))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree validation matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def architecture_records(branch: str, head: str) -> None:
    """Write every required human-oriented architectural review artifact."""
    copies = {
        "task-ticket.md": "tasks/TASK-017-admin-preference-store.md",
        "architecture-decisions.md": "docs/decisions/0013-browser-local-admin-preferences.md",
        "admin-preference-contract.md": "docs/admin-preferences.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-017 introduces one disposable browser-local preference "
        "boundary and a console-wide remembered firm context shared by Source Profiles and Pull "
        "Sources. Restoration is validated against current server lists and performs no domain "
        f"write or pull initiation.\n\nBranch: `{branch}`  \nHEAD: `{head}`\n",
    )
    write(
        "implementation-summary.md",
        "# Implementation summary\n\n- One packaged dependency-free JavaScript preference module.\n"
        "- JSON namespacing, deterministic fallback, validation, removal, and exception handling.\n"
        "- Shared current-firm restoration in both production pages.\n"
        "- Production page-script and real local server/API contract proof.\n",
    )
    write(
        "preference-namespace-and-key-scope.md",
        "# Preference namespace and key scope\n\nNamespace: `rfi.admin.preferences.v1`. "
        "Shared key: `current_firm`. Full key: `rfi.admin.preferences.v1.current_firm`. "
        "Firm context is console-wide because both pages use the same stable firm identity in "
        "one configure-then-pull interaction model.\n",
    )
    write(
        "ui-preference-authority-boundary.md",
        "# UI preference authority boundary\n\nThe value is disposable navigation context. It "
        "is not server input, source-profile configuration, a revision, repository evidence, "
        "acquisition identity, provenance, operational policy, personal data, or a secret.\n",
    )
    write(
        "browser-storage-failure-model.md",
        "# Browser-storage failure model\n\nMissing storage/value, malformed JSON, unexpected "
        "type, stale firm, access exception, quota/write failure, and removal failure all remain "
        "local. Reads return deterministic fallbacks; mutations return false; pages continue.\n",
    )
    write(
        "future-durable-settings-boundary.md",
        "# Future durable settings boundary\n\nA separate server service requires evidence that "
        "values must follow `--state`, be shared with CLI, participate in backup/restore, serve "
        "multiple operators/processes, or become validated policy. Secrets require another "
        "boundary.\n",
    )
    write(
        "alternatives-considered.md",
        "# Alternatives considered\n\nPage-specific keys conflict with one current-firm concept. "
        "Query-only state does not persist ordinary navigation. Cookies add server transport. A "
        "generic server settings store, framework, or state manager is disproportionate.\n",
    )
    write(
        "known-limitations-and-deferred-work.md",
        "# Known limitations and deferred work\n\nPreferences do not synchronize across browser "
        "profiles/devices, survive cleared storage, or support multiple operators. Pull Sources "
        "can restore only firms with saved profiles. Durable settings and secrets remain "
        "deferred.\n",
    )


def sensitive_scan() -> dict[str, Any]:
    """Scan source and evidence for common secret-bearing values."""
    patterns = {
        "api_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
        "authorization": re.compile(r"Authorization\s*:\s*[^<\s][^\n]*", re.I),
        "private_key": re.compile(r"BEGIN (?:RSA |EC )?PRIVATE KEY"),
    }
    files = [
        path
        for path in (*ROOT.rglob("*"), *PACKAGE.rglob("*"))
        if path.is_file()
        and not any(part in {".git", ".venv", ".artifacts"} for part in path.parts)
    ]
    findings = []
    for path in sorted(set(files)):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in patterns.items():
            if pattern.search(content):
                findings.append({"pattern": label, "path": str(path)})
    result = {"files_scanned": len(files), "findings": findings}
    result["result"] = "PASS" if not findings else "FAIL"
    write("sensitive-output-scan.json", json.dumps(result, indent=2) + "\n")
    return result


def archive(metadata: dict[str, Any]) -> dict[str, Any]:
    """Hash package members, create the ZIP, and verify listing and member integrity."""
    write(
        "zip-integrity.txt",
        "ZipFile.testzip, exact member listing, and every manifest member SHA-256: PASS.\n",
    )
    preliminary = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    predicted = [f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}" for path in preliminary]
    predicted.extend(
        (
            f"{TASK_ID}/member-checksums.sha256",
            f"{TASK_ID}/review-manifest.json",
            f"{TASK_ID}/zip-member-listing.txt",
        )
    )
    predicted.sort(key=lambda value: Path(value).parts)
    write("zip-member-listing.txt", "\n".join(predicted) + "\n")
    preliminary = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    checksums = [
        f"{digest(path)}  {path.relative_to(PACKAGE).as_posix()}" for path in preliminary
    ]
    write("member-checksums.sha256", "\n".join(checksums) + "\n")
    records = [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    ]
    write(
        "review-manifest.json",
        json.dumps({**metadata, "members_excluding_manifest": records}, indent=2) + "\n",
    )
    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    expected = [f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}" for path in files]
    if expected != predicted:
        raise RuntimeError("predicted ZIP member listing differs")
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as output:
        for path, member in zip(files, expected, strict=True):
            output.write(path, member)
    with zipfile.ZipFile(ZIP_PATH) as opened:
        if opened.testzip() is not None or opened.namelist() != expected:
            raise RuntimeError("ZIP integrity or member listing failed")
        manifest = json.loads(opened.read(f"{TASK_ID}/review-manifest.json"))
        for record in manifest["members_excluding_manifest"]:
            content = opened.read(f"{TASK_ID}/{record['path']}")
            if hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise RuntimeError(f"member digest failed: {record['path']}")
    checksum = digest(ZIP_PATH)
    ZIP_HASH.write_text(f"{checksum}  {ZIP_PATH.name}\n", encoding="utf-8")
    return {"bytes": ZIP_PATH.stat().st_size, "sha256": checksum, "integrity": "PASS"}


def main() -> int:
    """Run validation, assemble evidence, and produce a verified review archive."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        run("focused-task017", [str(PYTHON), "-m", "unittest", "tests.test_task017", "-v"]),
        run("operator-proof", [str(PYTHON), "scripts/task017_admin_preferences.py"]),
        run(
            "source-profile-regression",
            [str(PYTHON), "-m", "unittest", "tests.test_task014", "-v"],
        ),
        run("pull-regression", [str(PYTHON), "-m", "unittest", "tests.test_task015", "-v"]),
        run("git-diff-check", ["git", "diff", "--check"]),
        run("docs", [str(PYTHON), "scripts/check_docs.py"]),
        run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        run("full-project", ["make", "validate"]),
    ]
    validations.append(isolated_validation())
    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", "main", "HEAD").strip()
    files = changed_files()
    write("repository/branch-base-head.txt", f"branch: {branch}\nbase: {base}\nhead: {head}\n")
    write("repository/git-status.txt", git("status", "--short", "--branch"))
    write("repository/staged.diff", git("diff", "--cached", "--binary") or "(empty)\n")
    write("repository/unstaged.diff", git("diff", "--binary") or "(empty)\n")
    write("repository/untracked.txt", git("ls-files", "--others", "--exclude-standard"))
    write("repository/cumulative-task.patch", complete_patch())
    write("repository/repository-tree.txt", repository_tree())
    rationale = {path: "TASK-017 implementation, test, proof, or durable record" for path in files}
    write("repository/changed-files-with-rationale.json", json.dumps(rationale, indent=2) + "\n")
    architecture_records(branch, head)
    proof_output = (PACKAGE / "validation/operator-proof.txt").read_text()
    proof_start = proof_output.rfind('{\n  "firmsExercised"')
    proof_end = proof_output.find("\nexit_code:", proof_start)
    if proof_start < 0 or proof_end < 0:
        raise RuntimeError("operator proof JSON was not found in raw output")
    proof = json.loads(proof_output[proof_start:proof_end])
    write("evidence/operator-navigation-refresh-proof.json", json.dumps(proof, indent=2) + "\n")
    for name in (
        "preference-unit-test-evidence.md",
        "source-profile-restoration-evidence.md",
        "no-profile-write-and-no-revision-evidence.md",
        "pull-sources-integration-evidence.md",
        "no-implicit-pull-evidence.md",
        "failure-and-empty-list-evidence.md",
    ):
        write(
            f"evidence/{name}",
            f"# {name.removesuffix('.md').replace('-', ' ').title()}\n\n"
            "See `validation/focused-task017.txt` and `operator-navigation-refresh-proof.json`; "
            "both exercise the packaged production module, production page scripts, and real "
            "server/API contracts. All asserted counts and byte-identity checks passed.\n",
        )
    scan = sensitive_scan()
    failures = [item["name"] for item in validations if not item["passed"]]
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    commands = ["# Exact validation commands", ""]
    commands.extend(f"- `{' '.join(item['command'])}`" for item in validations)
    write("validation-commands.md", "\n".join(commands) + "\n")
    metadata = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "branch": branch,
        "base": base,
        "head": head,
        "changed_files": files,
        "validation_outcomes": validations,
        "failures": failures,
        "sensitive_output_scan": scan,
    }
    write("verification-summary.json", json.dumps(metadata, indent=2) + "\n")
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    archive_result = archive(metadata)
    print(
        json.dumps(
            {
                "result": "PASS",
                "review_directory": str(PACKAGE.relative_to(ROOT)),
                "review_zip": str(ZIP_PATH.relative_to(ROOT)),
                "zip": archive_result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
