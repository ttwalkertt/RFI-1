#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-031 review package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-031"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
ZIP_INTEGRITY = ZIP_PATH.with_suffix(".zip.integrity.txt")
LIVE = ROOT / ".artifacts/review-input/TASK-031/live-proof.json"
EXCLUDED = {".git", ".venv", ".artifacts", "__pycache__", ".mypy_cache"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(relative: str, content: str) -> None:
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def copy(relative: str, source: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"required evidence absent: {source}")
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def run(name: str, command: list[str], *, cwd: Path = ROOT) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    write(
        f"validation/{name}.txt",
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
    )
    return {
        "name": name,
        "command": command,
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
    }


def git(*arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if check and result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def isolated_validation() -> dict[str, Any]:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task031-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [sys.executable, "-m", "unittest", "tests.test_task031", "tests.test_task023",
             "tests.test_task025", "tests.test_task025_hardening", "tests.test_task028",
             "tests.test_task029",
             "tests.test_task030", "-v"],
            [sys.executable, "scripts/quality.py", "lint"],
            [sys.executable, "scripts/quality.py", "format"],
            [sys.executable, "scripts/quality.py", "typecheck"],
            [sys.executable, "scripts/check_docs.py"],
            [sys.executable, "scripts/check_baseline.py"],
        )
        output = [
            "Copied-tree validation; Git, state, artifacts, caches, and credentials excluded.",
            "",
        ]
        passed = True
        for command in commands:
            result = subprocess.run(
                command, cwd=destination, env={**os.environ, "PYTHONPATH": "src"},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            output.extend((
                f"$ {' '.join(command)}", result.stdout,
                f"exit_code: {result.returncode}", "",
            ))
            passed = passed and result.returncode == 0
    write("validation/isolated-tree.txt", "\n".join(output))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree", "TASK-031 regression and policy matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def sensitive_scan(changed: list[str]) -> dict[str, Any]:
    # Build the sentinels from fragments so this scanner does not flag its own
    # source while still inspecting every changed repository file.
    patterns = (
        "-----BEGIN " + "PRIVATE KEY-----",
        "sk-" + "proj-",
        "AIza" + "Sy",
        "ghp" + "_",
    )
    findings = []
    for relative in changed:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 10_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if pattern in text:
                findings.append({"path": relative, "pattern": pattern})
    write(
        "validation/sensitive-output-scan.txt",
        json.dumps({"patterns": patterns, "findings": findings}, indent=2) + "\n",
    )
    return {
        "name": "sensitive-output-scan",
        "command": ["repository-local changed-file sensitive pattern scan"],
        "exit_code": 1 if findings else 0,
        "passed": not findings,
    }


def completion_report(validations: list[dict[str, Any]], base: str, head: str) -> str:
    outcomes = "\n".join(
        f"- `{' '.join(item['command'])}` — "
        f"`{'PASS' if item['passed'] else 'FAIL'}` (exit {item['exit_code']}); "
        f"raw output: `validation/{item['name']}.txt`."
        for item in validations
    )
    return f"""# TASK-031 completion report

## Prior stopping behavior and root cause

Seed searches already paged and catch-up already split date windows, but relationship expansion was
one breadth-first process-local plan. Context-budget exhaustion or a pageable thread feed set
permanent truncation, stopped the catch-up loop, and prevented later seed pages and windows. The
per-request record boundary therefore acted as a corpus-size ceiling.

## Implemented architecture and traversal

Append-only SQLite acquisition manifests now own a versioned continuation keyed by source, coverage
batch, and discovery offset. Ancestry frames run first. Reply frames then traverse depth-first and
retain parent, depth, provider offset, pending siblings, completed nodes, and policy state. Depth
first was selected because the durable frontier is the active path plus siblings and complete
branches stay locally complete. SQLite remains the sole structured authority; no table migration or
shadow queue was needed.

Every provider relationship page is bounded to at most 50 identifiers. Every run retains no more
than its seed/context limits. `continuation_pending` is successful bounded progress;
`policy_truncated` is an intentional reply-depth terminal; `failed` is provider/integrity/execution
failure; `complete` exhausts configured work. A seed page reaches a terminal state before the next
page, and all pages terminate before a date window advances. Coverage is withheld while pending or
failed and advances for complete or policy-truncated work.

## Restart, overlap, and artifact truth

Restart reads the last immutable manifest frontier. Cancellation before publish leaves it unchanged;
retry may repeat an uncommitted provider call but not completed manifest work. Content addressing,
canonical Message-ID identity, unique rows, and scoped acquired/completed identifiers suppress
duplicates across overlapping seeds, branches, pages, and runs. Run status is not artifact truth:
messages with closed retained parent paths remain connected and usable while other relationship work
is pending. Future replies are new source state for later overlapping catch-up, not defects in the
completed snapshot.

## Deterministic and live evidence

`tests.test_task031` proves 56 messages complete in exactly three bounded relationship runs;
ancestry and replies cross run boundaries; provider offsets resume; each continuation reconstructs
repository
services; exact budget exhaustion, interruption, safe retry, overlap, stable artifacts, policy
truncation, provider failure, later seed pages/windows, coverage withholding/completion, CLI/browser
terms, Lore offset construction, and future replies are covered. TASK-023/030 retain missing-parent,
tombstone, integrity, and offline projection controls.

The gated live proof used `linux-block`, 2026-07-19 through 2026-07-22, subject `PATCH`, one seed,
one context record, and depth zero. It performed three Lore requests, stored one seed and one
ancestor, and returned `continuation_pending` with coverage withheld and two source links. It is
explicitly `bounded_live_only`; terminal multi-run success is not claimed from live data. Complete
JSON is `live/live-proof.json`.

## Validation

{outcomes}

## Repository and limitations

Base `{base}`; packaged HEAD `{head}`. Direct CLI resumption requires the operator to reuse the same
continuation ID and offset; the workflow does this automatically. Provider calls interrupted before
manifest publication may repeat idempotently. Scheduling, background polling, cross-list traversal,
and tombstone supersession remain deferred. There is no departure from the ticket's architecture;
the permitted bounded-live fallback was used because the selected live run did not safely prove
terminal multi-run completion.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Lore adapter | Bounded discovery, retrieval, pageable relationship offsets | Complete |
| Acquisition orchestration | Ancestry-first depth-first durable continuation | Complete |
| SQLite run manifests | Sole continuation/status/coverage authority | Complete |
| Immutable artifacts and projections | Stable identity, dedupe, structural truth | Complete |
| Catch-up workflow | Seed-page/date-window sequencing and restart | Complete |
| API, CLI, browser, run history | Consistent relationship taxonomy | Complete |
| Scheduled/background polling | Automatic future snapshot acquisition | Not Started |

Next architectural milestone: evaluate production polling requirements from operator evidence
without broadening this continuation mechanism into a generic scheduler.
"""


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    for path in (ZIP_PATH, ZIP_HASH, ZIP_INTEGRITY):
        path.unlink(missing_ok=True)

    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", "HEAD", "origin/main").strip()
    committed = git("diff", "--name-only", f"{base}..{head}").splitlines()
    working = git("diff", "--name-only").splitlines()
    staged_names = git("diff", "--cached", "--name-only").splitlines()
    untracked_names = git("ls-files", "--others", "--exclude-standard").splitlines()
    changed = sorted(set(committed + working + staged_names + untracked_names))

    validations = [
        run("focused-task031", [sys.executable, "-m", "unittest", "tests.test_task031", "-v"]),
        run("task023-regression", [sys.executable, "-m", "unittest", "tests.test_task023", "-v"]),
        run("task025-regression", [sys.executable, "-m", "unittest", "tests.test_task025", "-v"]),
        run(
            "task025-hardening-regression",
            [sys.executable, "-m", "unittest", "tests.test_task025_hardening", "-v"],
        ),
        run("task028-regression", [sys.executable, "-m", "unittest", "tests.test_task028", "-v"]),
        run("task029-regression", [sys.executable, "-m", "unittest", "tests.test_task029", "-v"]),
        run("task030-regression", [sys.executable, "-m", "unittest", "tests.test_task030", "-v"]),
        run("schema-migration", [sys.executable, "-m", "unittest", "tests.test_task021", "-v"]),
        run(
            "fixture-integrity",
            [sys.executable, "scripts/task023_mailing_lists.py", "fixture-proof"],
        ),
        run("lint", [sys.executable, "scripts/quality.py", "lint"]),
        run("format", [sys.executable, "scripts/quality.py", "format"]),
        run("typecheck", [sys.executable, "scripts/quality.py", "typecheck"]),
        run("docs", [sys.executable, "scripts/check_docs.py"]),
        run("baseline", [sys.executable, "scripts/check_baseline.py"]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
        isolated_validation(),
        sensitive_scan(changed),
    ]

    copies = {
        "task-ticket.md": ROOT / "tasks/TASK-031-resumable-lore-relationship-acquisition.md",
        "architecture/adr-0023.md": ROOT /
            "docs/decisions/0023-resumable-lore-relationship-acquisition.md",
        "architecture/mailing-list-design.md": ROOT /
            "docs/linux-kernel-mailing-list-intelligence-stream.md",
        "architecture/operator-console-design.md": ROOT /
            "docs/linux-mailing-list-operator-console.md",
        "operator/operator-guide.md": ROOT / "docs/operator-guide.md",
        "operator/application-cli.md": ROOT / "docs/application-cli.md",
        "evidence/deterministic-fixture.py": ROOT / "tests/test_task031.py",
        "live/live-proof.json": LIVE,
    }
    for destination, source in copies.items():
        copy(destination, source)

    status = git("status", "--short", "--branch")
    staged = git("diff", "--cached", "--binary")
    unstaged = git("diff", "--binary")
    cumulative = git("diff", "--binary", f"{base}..{head}")
    if not cumulative.strip():
        cumulative = unstaged
    write("repository/git-status.txt", status)
    write("repository/staged.diff", staged or "(empty)\n")
    write("repository/unstaged.diff", unstaged or "(empty)\n")
    write("repository/cumulative-task.patch", cumulative or "(empty)\n")
    write("repository/untracked.txt", "\n".join(untracked_names) + "\n")
    write("repository/changed-files.json", json.dumps({"files": changed}, indent=2) + "\n")
    write("completion-report.md", completion_report(validations, base, head))

    failures = [item["name"] for item in validations if not item["passed"]]
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1

    members = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "branch": branch,
        "base": base,
        "head": head,
        "validation_outcomes": validations,
        "members": [
            {
                "path": path.relative_to(PACKAGE).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in members
        ],
    }
    write("review-manifest.json", json.dumps(manifest, indent=2) + "\n")
    checksum_members = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    write(
        "package-members.sha256",
        "".join(
            f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}\n"
            for path in checksum_members
        ),
    )
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE.parent))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
        member_count = len(archive.infolist())
    checksum = sha256(ZIP_PATH)
    ZIP_HASH.write_text(f"{checksum}  {ZIP_PATH.name}\n", encoding="utf-8")
    ZIP_INTEGRITY.write_text(
        f"testzip: {bad_member or 'PASS'}\nmembers: {member_count}\n"
        f"bytes: {ZIP_PATH.stat().st_size}\nsha256: {checksum}\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "result": "PASS",
        "review_directory": str(PACKAGE.relative_to(ROOT)),
        "review_zip": str(ZIP_PATH.relative_to(ROOT)),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_members": member_count,
        "zip_test": bad_member or "PASS",
        "sha256": checksum,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
