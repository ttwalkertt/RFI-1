#!/usr/bin/env python3
"""Generate the complete independently reviewable TASK-016 evidence package."""

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
TASK_ID = "TASK-016"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
LIVE = ROOT / ".artifacts/review-input/TASK-016-live-v2.json"
FAILED_LIVE = ROOT / ".artifacts/review-input/TASK-016-live-initial-failure.txt"
FAILED_STATE = ROOT / ".artifacts/runtime/TASK-016-sec-10k"
EXCLUDED = {".artifacts", ".git", ".venv", "__pycache__"}


def write(name: str, content: str) -> None:
    """Write one UTF-8 review member, creating its parent directory."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    """Return one exact file digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(
    name: str,
    command: list[str],
    cwd: Path = ROOT,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run and retain the complete combined command output."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
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


def git(*arguments: str) -> str:
    """Run one read-only Git query."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def changed_files() -> list[str]:
    """Return tracked and untracked task files in deterministic order."""
    tracked = git("diff", "--name-only", "main", "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set((*tracked, *untracked)))


def complete_patch() -> str:
    """Render the cumulative binary-safe patch including untracked task files."""
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
    """List final source paths without Git, environments, caches, or generated evidence."""
    paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED for part in path.relative_to(ROOT).parts)
    )
    return "\n".join(paths) + "\n"


def offline_environment() -> dict[str, str]:
    """Return validation environment with every supported live credential absent."""
    environment = os.environ.copy()
    environment.pop("RFI_SEC_USER_AGENT", None)
    environment.pop("SEC_API_IO_API_KEY", None)
    environment["PYTHONPATH"] = "src"
    return environment


def isolated_validation(environment: dict[str, str]) -> dict[str, Any]:
    """Validate a clean-equivalent copied tree without Git, artifacts, or local config."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(EXCLUDED | {".rfi"})

    with tempfile.TemporaryDirectory(prefix="rfi-task016-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        launcher = destination / ".venv/bin/rfi"
        launcher.parent.mkdir(parents=True)
        launcher.write_text(
            f"#!{PYTHON}\n"
            "import sys\n"
            "from rfi.cli import main\n"
            "if __name__ == '__main__':\n"
            "    sys.exit(main())\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        commands = (
            [str(PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"],
            [str(PYTHON), "scripts/task016_sec_10k.py", "fixture-proof"],
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
        )
        outputs = [
            "Method: copied the final tree excluding .git, environment contents, .artifacts, "
            ".rfi, and caches; recreated only the installed rfi console shim required by the "
            "existing entry-point parity test.",
            "Every command used the current Python runtime with live credentials removed.",
            "",
        ]
        passed = True
        for command in commands:
            result = subprocess.run(
                command,
                cwd=destination,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            outputs.extend(
                (
                    f"$ {' '.join(command)}",
                    result.stdout,
                    f"exit_code: {result.returncode}",
                    "",
                )
            )
            passed = passed and result.returncode == 0
    write("validation/isolated-tree.txt", "\n".join(outputs))
    return {
        "name": "isolated-tree",
        "command": ["clean-equivalent offline validation matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def copy_architecture_records() -> None:
    """Copy durable ticket, ADR, operations guide, and governing summary material."""
    copies = {
        "task-ticket.md": "tasks/TASK-016-deterministic-sec-10k-retrieval.md",
        "architecture-decisions.md": (
            "docs/decisions/0012-artifact-semantic-deterministic-sec-retrieval.md"
        ),
        "architecture-and-operations.md": "docs/deterministic-sec-form-10k-retrieval.md",
        "pull-integration.md": "docs/pull-workflow.md",
        "backlog.md": "BACKLOG.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)


def write_architecture_views(branch: str, head: str) -> None:
    """Write the required human-oriented architecture review views."""
    guide = (ROOT / "docs/deterministic-sec-form-10k-retrieval.md").read_text()
    adr = (
        ROOT / "docs/decisions/0012-artifact-semantic-deterministic-sec-retrieval.md"
    ).read_text()
    write(
        "executive-summary.md",
        "# Executive summary\n\n"
        "TASK-016 implements one architecture-led live vertical slice from a revisioned firm "
        "source profile through artifact-semantic adapter selection, authoritative SEC "
        "Form 10-K selection, exact primary-document retrieval, the existing acquisition "
        "engine, and immutable repository evidence. Offline proof is deterministic; live proof "
        "is separately gated. No other form, crawling, extraction, search, or intelligence was "
        f"added.\n\nBranch: `{branch}`  \nHEAD: `{head}`\n",
    )
    write(
        "implementation-summary.md",
        "# Implementation summary\n\n"
        "- Generic retrieval registry with unique adapter identities, non-overlapping "
        "artifact/mode claims, shared-mechanism support, and explicit plan selection.\n"
        "- One `sec_10k` + `identifier` artifact adapter with explicit amendment policy.\n"
        "- Bounded SEC provider mechanics with injectable deterministic transport.\n"
        "- Existing acquisition engine/repository ingress, replay, rebuild, and integrity.\n"
        "- Operator readiness, capability, selected filing, provenance, outcome, and diagnostics.\n"
        "- Complete offline fixture proof, retained failed live proof, and passing live rerun "
        "proof.\n"
        "- Durable BACKLOG governance for unscheduled TASK-016 limitations without task "
        "authorization or roadmap sequencing.\n",
    )
    alternatives = adr.split("## Alternatives considered", 1)[1].split(
        "## Consequences and limits", 1
    )[0]
    write("alternatives-considered.md", "# Alternatives considered\n" + alternatives)
    sections = {
        "retrieval-adapter-responsibility-model.md": ("Responsibility model", "Form 10-K policy"),
        "adapter-capability-and-selection-contract.md": (
            "Responsibility model",
            "Form 10-K policy",
        ),
        "artifact-specific-form-10k-policy.md": ("Form 10-K policy", "SEC provider boundary"),
        "shared-sec-provider-service-boundary.md": (
            "SEC provider boundary",
            "Identity and provenance",
        ),
        "sec-source-and-api-surface.md": ("SEC provider boundary", "Identity and provenance"),
        "network-and-service-use-boundary.md": (
            "SEC provider boundary",
            "Identity and provenance",
        ),
        "identity-and-provenance-model.md": ("Identity and provenance", "Operator commands"),
        "failure-and-result-taxonomy.md": ("Failure taxonomy", "Extensions and deferred work"),
        "future-adapter-extension-analysis.md": ("Extensions and deferred work", None),
    }
    for name, (start, end) in sections.items():
        content = guide.split(f"## {start}", 1)[1]
        if end is not None:
            content = content.split(f"## {end}", 1)[0]
        write(name, f"# {start}\n" + content)
    write(
        "deterministic-filing-selection-policy.md",
        (PACKAGE / "artifact-specific-form-10k-policy.md").read_text(),
    )
    write(
        "source-profile-and-pull-integration-summary.md",
        "# Source-profile and Pull Workflow integration\n\n"
        "The exact source-profile revision is snapshotted before planning. Every enabled artifact "
        "participates. The capability registry selects by canonical artifact and candidate mode; "
        "the plan and attempt persist adapter identity. Accepted bytes enter only through the "
        "existing acquisition engine and repository. Other enabled unconfigured artifacts remain "
        "configuration problems and independently cause partial aggregation.\n",
    )
    write(
        "known-limitations-and-deferred-work.md",
        "# Known limitations and deferred work\n\n"
        "Only recent submissions are queried. Amendments are excluded rather than configurable. "
        "Capability overlap is rejected; priority, fallback, and multiple-match resolution remain "
        "deliberately absent. Distinct artifact adapters may share acquisition routing metadata. "
        "Exact historical selection, all other forms/artifacts, scheduling, semi-deterministic "
        "listing, discovery, crawling, LLM selection, extraction, XBRL interpretation, and "
        "downstream intelligence remain deferred. The local workflow is single-process and "
        "single-writer.\n",
    )


def live_evidence() -> dict[str, Any]:
    """Validate and split retained sanitized live evidence without copying live bytes."""
    if not LIVE.is_file() or not FAILED_LIVE.is_file():
        raise RuntimeError("required retained live evidence is absent")
    value = json.loads(LIVE.read_text())
    if value.get("result") != "PASS":
        raise RuntimeError("retained live proof did not pass")
    usage = value.get("provider_usage", {})
    if not isinstance(usage, dict) or int(usage.get("requests", 99)) > 6:
        raise RuntimeError("live request usage exceeded the declared ceiling")
    (PACKAGE / "live").mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, PACKAGE / "live/complete-live-proof.json")
    shutil.copy2(FAILED_LIVE, PACKAGE / "live/initial-failed-command.txt")
    write("live/first-live-pull.json", json.dumps(value["first_pull"], indent=2) + "\n")
    write("live/repeated-live-pull.json", json.dumps(value["repeat_pull"], indent=2) + "\n")
    write(
        "live/artifact-inventory-and-checksums.json",
        json.dumps(
            {
                "artifact_inventory": value["artifact_inventory"],
                "artifact_sha256": value["artifact_sha256"],
                "artifact_bytes": value["artifact_bytes"],
                "document_ids": value["document_ids"],
            },
            indent=2,
        )
        + "\n",
    )
    write(
        "live/replay-rebuild-integrity.json",
        json.dumps(
            {
                "network_unavailable_during_replay": value[
                    "network_unavailable_during_replay"
                ],
                "replay": value["replay"],
                "integrity_before": value["integrity_before"],
                "integrity_after": value["integrity_after"],
            },
            indent=2,
        )
        + "\n",
    )
    failed_runs = sorted((FAILED_STATE / "pull-workflows/runs").glob("*.json"))
    if not failed_runs:
        raise RuntimeError("initial failed live pull journals are absent")
    for path in failed_runs:
        shutil.copy2(path, PACKAGE / "live" / f"initial-failure-{path.name}")
    return {
        "result": value["result"],
        "requests": usage["requests"],
        "retries": usage["retries"],
        "artifact_sha256": value["artifact_sha256"],
        "artifact_bytes": value["artifact_bytes"],
        "first_outcome": value["first_pull"]["firms"][0]["artifacts"][0]["outcome"],
        "repeat_outcome": value["repeat_pull"]["firms"][0]["artifacts"][0]["outcome"],
        "initial_failed_evidence_retained": True,
    }


def sensitive_scan() -> dict[str, Any]:
    """Scan final source and assembled evidence for common secret-bearing output."""
    patterns = {
        "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
        "sec_api_value": re.compile(r"SEC_API_IO_API_KEY\s*=\s*[^.\s<][^\s]*"),
        "sec_user_agent_value": re.compile(
            r"RFI_SEC_USER_AGENT\s*=\s*[^.<{\s\n][^\n]{11,}"
        ),
        "authorization_header": re.compile(r"Authorization\s*:\s*[^<\s][^\n]*", re.I),
    }
    source_files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(
            part in {".artifacts", ".git", ".venv", ".rfi"} for part in path.parts
        )
        and not path.name.endswith(".zip")
        and "runtime" not in path.parts
    ]
    package_files = [path for path in PACKAGE.rglob("*") if path.is_file()]
    files = sorted(set((*source_files, *package_files)))
    findings = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in patterns.items():
            if pattern.search(content):
                findings.append({"pattern": label, "path": str(path.relative_to(ROOT))})
    result = {
        "files_scanned": len(files),
        "findings": findings,
        "result": "PASS" if not findings else "FAIL",
    }
    write("sensitive-output-scan.json", json.dumps(result, indent=2) + "\n")
    return result


def archive(metadata: dict[str, Any]) -> None:
    """Hash members, create the final ZIP, and independently verify every member."""
    write(
        "zip-integrity.txt",
        "The generator creates the archive only after all required validations pass, then uses "
        "ZipFile.testzip(), compares the exact member listing, extracts every member in memory, "
        "and verifies its SHA-256 against review-manifest.json. Any mismatch makes generation "
        "fail. Final generator result: PASS.\n",
    )
    files_before_listing = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    expected_listing = [
        f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}"
        for path in files_before_listing
    ]
    expected_listing.extend(
        (
            f"{TASK_ID}/member-checksums.sha256",
            f"{TASK_ID}/review-manifest.json",
            f"{TASK_ID}/zip-member-listing.txt",
        )
    )
    expected_listing.sort(key=lambda value: Path(value).parts)
    write("zip-member-listing.txt", "\n".join(expected_listing) + "\n")
    members_before_checksums = sorted(
        path for path in PACKAGE.rglob("*") if path.is_file()
    )
    checksum_lines = [
        f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}"
        for path in members_before_checksums
    ]
    write("member-checksums.sha256", "\n".join(checksum_lines) + "\n")
    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    records = [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in files
    ]
    manifest = {**metadata, "members_excluding_manifest": records}
    write("review-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    expected = [f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}" for path in files]
    if (PACKAGE / "zip-member-listing.txt").read_text().splitlines() != expected:
        raise RuntimeError("predicted ZIP member listing differs before archive creation")
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as output:
        for path in files:
            output.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    with zipfile.ZipFile(ZIP_PATH) as opened:
        if opened.testzip() is not None:
            raise RuntimeError("review ZIP contains a corrupt member")
        if opened.namelist() != expected:
            raise RuntimeError("review ZIP member listing differs")
        manifest_value = json.loads(opened.read(f"{TASK_ID}/review-manifest.json"))
        for record in manifest_value["members_excluding_manifest"]:
            content = opened.read(f"{TASK_ID}/{record['path']}")
            if hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise RuntimeError(f"review member checksum differs: {record['path']}")
    digest = sha256(ZIP_PATH)
    ZIP_HASH.write_text(f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Run final validation, assemble evidence, and produce a self-verified review ZIP."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    environment = offline_environment()
    validations = [
        run(
            "focused-task016",
            [str(PYTHON), "-m", "unittest", "tests.test_task016", "-v"],
            environment=environment,
        ),
        run(
            "task015-regression",
            [str(PYTHON), "-m", "unittest", "tests.test_task015", "-v"],
            environment=environment,
        ),
        run(
            "fixture-production-proof",
            [str(PYTHON), "scripts/task016_sec_10k.py", "fixture-proof"],
            environment=environment,
        ),
        run("git-diff-check", ["git", "diff", "--check"], environment=environment),
        run("docs", [str(PYTHON), "scripts/check_docs.py"], environment=environment),
        run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"], environment=environment),
        run("full-project", ["make", "validate"], environment=environment),
    ]
    validations.append(isolated_validation(environment))
    failures = [item["name"] for item in validations if not item["passed"]]
    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", "main", "HEAD").strip()
    files = changed_files()
    write("repository/branch.txt", f"branch: {branch}\nbase: {base}\nhead: {head}\n")
    write("repository/status.txt", git("status", "--short", "--branch"))
    write("repository/staged.diff", git("diff", "--cached", "--binary") or "(empty)\n")
    write("repository/unstaged.diff", git("diff", "--binary") or "(empty)\n")
    write("repository/untracked.txt", git("ls-files", "--others", "--exclude-standard"))
    write("repository/changed-files.json", json.dumps(files, indent=2) + "\n")
    write("repository/complete.patch", complete_patch())
    write("repository/tree.txt", repository_tree())
    rationale = {
        path: (
            "TASK-016 implementation, fixture, verification, operator, or durable design record"
        )
        for path in files
    }
    write("repository/changed-files-with-rationale.json", json.dumps(rationale, indent=2) + "\n")
    copy_architecture_records()
    write_architecture_views(branch, head)
    live = live_evidence()
    (PACKAGE / "fixtures").mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "fixtures/sec-10k").iterdir()):
        if source.is_file():
            shutil.copy2(source, PACKAGE / "fixtures" / source.name)
    scan = sensitive_scan()
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    commands = ["# Exact validation commands", ""]
    commands.extend(f"- `{' '.join(item['command'])}`" for item in validations)
    commands.extend(
        (
            "",
            "All commands above are offline. Live proof was separately gated and is retained "
            "under `live/`; it was not rerun by package generation.",
        )
    )
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
        "all_offline_validations_passed": not failures,
        "live_proof": live,
        "sensitive_output_scan": scan,
        "staged_changes": bool(git("diff", "--cached", "--name-only").strip()),
        "limitations": [
            "recent submissions only",
            "unamended Form 10-K only",
            "single-process local workflow",
        ],
    }
    write(
        "verification-summary.json",
        json.dumps({**metadata, "failures": failures}, indent=2) + "\n",
    )
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    archive(metadata)
    print(
        json.dumps(
            {
                "result": "PASS",
                "review_directory": str(PACKAGE.relative_to(ROOT)),
                "review_zip": str(ZIP_PATH.relative_to(ROOT)),
                "zip_bytes": ZIP_PATH.stat().st_size,
                "zip_sha256": sha256(ZIP_PATH),
                "zip_integrity": "PASS",
                "members": len([path for path in PACKAGE.rglob("*") if path.is_file()]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
