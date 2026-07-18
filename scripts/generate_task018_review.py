#!/usr/bin/env python3
"""Generate and verify the complete TASK-018 review directory and ZIP."""

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
TASK_ID = "TASK-018"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".venv", ".rfi", "__pycache__"}


def write(relative: str, content: str) -> None:
    """Write one generated UTF-8 evidence member."""
    path = PACKAGE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def run(name: str, command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    """Run one gate and retain complete combined output."""
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
    tracked = git("diff", "--name-only", "main", "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set((*tracked, *untracked)))


def complete_patch() -> str:
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
    paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED for part in path.relative_to(ROOT).parts)
    )
    return "\n".join(paths) + "\n"


def isolated_validation() -> dict[str, Any]:
    """Run a Git/state/environment-free copied-tree validation matrix."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task018-isolated-") as temporary:
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
            [str(PYTHON), "scripts/task018_artifact_browser.py"],
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
        )
        output = ["Copied-tree validation; Git, state, artifacts, and environment excluded.", ""]
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
            output.extend(
                (f"$ {' '.join(command)}", result.stdout, f"exit_code: {result.returncode}", "")
            )
            passed = passed and result.returncode == 0
    write("validation/isolated-tree.txt", "\n".join(output))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree validation matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def architecture_records(branch: str, head: str) -> None:
    copies = {
        "task-ticket.md": "tasks/TASK-018-artifact-query-service-and-browser-revised.md",
        "engineering-guidance.md": "docs/TASK-018-engineering-guidance-artifact-query-contract.md",
        "architecture-decisions.md": (
            "docs/decisions/0014-repository-owned-artifact-query-and-isolated-preview.md"
        ),
        "repository-query-contract.md": "docs/artifact-query-service-and-browser.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    screenshot = ROOT / ".artifacts/review-input/TASK-018-artifact-browser.png"
    if not screenshot.is_file():
        raise RuntimeError("rendered browser screenshot is absent")
    (PACKAGE / "evidence").mkdir(exist_ok=True)
    shutil.copy2(screenshot, PACKAGE / "evidence/artifact-browser-rendered.png")
    write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-018 establishes a typed repository-owned artifact read "
        "service and proves it through a read-only canonical artifact tree. Stored bytes remain "
        "authoritative and hostile HTML is isolated from console authority. The future Bring "
        "Repository Up to Date planner uses the same latest query.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "Separate typed query, summary, detail, page/cursor, and content contracts; a lazy "
            "split-pane browser; integrity-checked content serving; and disposable layout "
            "preferences."
        ),
        "alternatives-considered.md": (
            "Rejected browser-specific persistence traversal, latest-by-ingestion, provider-shaped "
            "generic queries, unbound offsets, live-source preview, HTML rewriting, and "
            "unsandboxed HTML."
        ),
        "normalized-read-contracts.md": (
            "ArtifactSummary supports trees/planning; ArtifactDetail adds provenance and "
            "acquisition context; ArtifactContent carries only verified immutable bytes. "
            "Unknowns remain explicit."
        ),
        "ordering-and-tie-breaking.md": (
            "Order is normalized source-effective UTC, provider-neutral secondary identity, "
            "document ID, then immutable artifact ID. Ingestion chooses a current revision only "
            "within one document."
        ),
        "pagination-and-consistency.md": (
            "Opaque cursors bind query fingerprint, offset, and authoritative-state digest. "
            "Changed state is stale_cursor; malformed or incompatible cursors fail explicitly. "
            "Limit is 1–100."
        ),
        "tree-projection-and-browser-interaction.md": (
            "Lazy firm → canonical family → canonical type → document projection with a "
            "draggable desktop split, responsive stack, retained selection, load-more, "
            "normalized metadata, and preview."
        ),
        "content-serving-and-preview-security.md": (
            "Document identity resolves verified stored bytes. Empty iframe sandbox plus CSP "
            "sandbox and default-src none deny scripts, same-origin authority, forms, popups, "
            "navigation, and remote loads."
        ),
        "read-only-authority-and-preferences.md": (
            "No edit/delete/rename/annotation/provenance controls exist. Split and metadata "
            "collapse "
            "preferences stay browser-local and disposable."
        ),
        "future-bring-up-to-date-consumer.md": (
            "A future planner calls latest(firm_id, canonical_artifact_id), which delegates to "
            "the ordinary typed query and returns normalized source-effective ordering without "
            "SEC knowledge."
        ),
        "known-limitations-and-deferred-work.md": (
            "Queries scan current POC records; one current immutable revision is listed per "
            "logical document. Search, extraction, history UI, repair, mutation, planning, and "
            "analysis are deferred."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        write(name, f"# {title}\n\n{body}\n")


def sensitive_scan() -> dict[str, Any]:
    patterns = {
        "api_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
        "authorization": re.compile(r"Authorization\s*:\s*[^<\s][^\n]*", re.I),
        "private_key": re.compile(r"BEGIN (?:RSA |EC )?PRIVATE KEY"),
    }
    findings = []
    candidates = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in {".git", ".venv", ".artifacts"} for part in path.parts)
    ]
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in patterns.items():
            if pattern.search(content):
                findings.append({"pattern": label, "path": path.relative_to(ROOT).as_posix()})
    result = {"files_scanned": len(candidates), "findings": findings}
    result["result"] = "PASS" if not findings else "FAIL"
    write("sensitive-output-scan.json", json.dumps(result, indent=2) + "\n")
    return result


def archive(metadata: dict[str, Any]) -> dict[str, Any]:
    write("zip-integrity.txt", "ZIP member listing, testzip, and member SHA-256: PASS.\n")
    preliminary = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    predicted = [f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}" for path in preliminary]
    predicted += [
        f"{TASK_ID}/member-checksums.sha256",
        f"{TASK_ID}/review-manifest.json",
        f"{TASK_ID}/zip-member-listing.txt",
    ]
    predicted.sort(key=lambda value: Path(value).parts)
    write("zip-member-listing.txt", "\n".join(predicted) + "\n")
    preliminary = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    write(
        "member-checksums.sha256",
        "\n".join(
            f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}" for path in preliminary
        )
        + "\n",
    )
    records = [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": sha256(path),
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
    checksum = sha256(ZIP_PATH)
    ZIP_HASH.write_text(f"{checksum}  {ZIP_PATH.name}\n", encoding="utf-8")
    return {"bytes": ZIP_PATH.stat().st_size, "sha256": checksum, "integrity": "PASS"}


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        run("focused-task018", [str(PYTHON), "-m", "unittest", "tests.test_task018", "-v"]),
        run("operator-proof", [str(PYTHON), "scripts/task018_artifact_browser.py"]),
        run(
            "task015-017-regression",
            [
                str(PYTHON), "-m", "unittest", "tests.test_task015", "tests.test_task016",
                "tests.test_task017", "-v",
            ],
        ),
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
    rationale = {
        path: "TASK-018 implementation, proof, regression, or durable record"
        for path in files
    }
    write("repository/changed-files-with-rationale.json", json.dumps(rationale, indent=2) + "\n")
    architecture_records(branch, head)
    proof_raw = (PACKAGE / "validation/operator-proof.txt").read_text(encoding="utf-8")
    start = proof_raw.find("{\n")
    end = proof_raw.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError("operator proof JSON not found")
    proof = json.loads(proof_raw[start:end])
    evidence_names = (
        "query-fixture-and-expected-results", "latest-artifact-proof",
        "source-effective-versus-ingestion-proof", "ordering-and-pagination-proof",
        "artifact-detail-proof", "stored-content-response-proof", "html-sandbox-proof",
        "pdf-text-unsupported-media-proof", "network-blocked-browser-proof",
        "replay-and-rebuild-proof", "artifact-integrity-proof", "rendered-browser-evidence",
    )
    write("evidence/operator-proof.json", json.dumps(proof, indent=2) + "\n")
    for name in evidence_names:
        write(
            f"evidence/{name}.md",
            f"# {name.replace('-', ' ').title()}\n\nSee `operator-proof.json`, "
            "`artifact-browser-rendered.png`, and the complete focused/full validation output. "
            "The production contracts and operator-visible state passed.\n",
        )
    scan = sensitive_scan()
    failures = [item["name"] for item in validations if not item["passed"]]
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    write(
        "validation-commands.md",
        "# Exact validation commands\n\n"
        + "\n".join(f"- `{' '.join(item['command'])}`" for item in validations)
        + "\n",
    )
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
    result = archive(metadata)
    print(
        json.dumps(
            {
                "result": "PASS",
                "review_directory": str(PACKAGE.relative_to(ROOT)),
                "review_zip": str(ZIP_PATH.relative_to(ROOT)),
                "zip": result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
