#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-032 review package."""

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
TASK_ID = "TASK-032"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
ZIP_INTEGRITY = ZIP_PATH.with_suffix(".zip.integrity.txt")
INPUT = ROOT / ".artifacts/review-input" / TASK_ID
BROWSER_INPUT = INPUT / "browser-proof.json"
LIVE_INPUT = INPUT / "live-proof.json"
LEGACY_LIVE_INPUT = PACKAGE / "live/live-proof.json"
EXCLUDED = {".git", ".venv", ".artifacts", "__pycache__", ".mypy_cache"}
VALIDATION_TIMEOUT_SECONDS = 900
EXCLUDE_FROM_TASK = {
    "openrouter-smoke.txt",
    "docs/reference/codex_and_openrouter.rtf",
}


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


def run(
    name: str,
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout_seconds: int = VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env={**os.environ, "PYTHONPATH": "src"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
        )
        output = result.stdout
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + "\nVALIDATION TIMED OUT\n"
        exit_code = 124
    write(
        f"validation/{name}.txt",
        f"$ {' '.join(command)}\n"
        f"timeout_seconds: {timeout_seconds}\n\n"
        f"{output}\nexit_code: {exit_code}\n",
    )
    return {
        "name": name,
        "command": command,
        "exit_code": exit_code,
        "passed": exit_code == 0,
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

    with tempfile.TemporaryDirectory(prefix="rfi-task032-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [sys.executable, "-m", "unittest", "tests.test_task032",
             "tests.test_task029", "tests.test_task028", "tests.test_task023",
             "tests.test_task021", "tests.test_task031", "-v"],
            [sys.executable, "scripts/quality.py", "lint"],
            [sys.executable, "scripts/quality.py", "format"],
            [sys.executable, "scripts/quality.py", "typecheck"],
            [sys.executable, "scripts/check_docs.py"],
            [sys.executable, "scripts/check_baseline.py"],
        )
        transcript = [
            "Copied-tree validation; Git, state, artifacts, caches, and credentials excluded.",
            "",
        ]
        passed = True
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    cwd=destination,
                    env={**os.environ, "PYTHONPATH": "src"},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=VALIDATION_TIMEOUT_SECONDS,
                )
                command_output = result.stdout
                exit_code = result.returncode
            except subprocess.TimeoutExpired as error:
                command_output = (error.stdout or "") + "\nVALIDATION TIMED OUT\n"
                exit_code = 124
            transcript.extend((
                f"$ {' '.join(command)}",
                f"timeout_seconds: {VALIDATION_TIMEOUT_SECONDS}",
                command_output,
                f"exit_code: {exit_code}",
                "",
            ))
            passed = passed and exit_code == 0
    write("validation/isolated-tree.txt", "\n".join(transcript))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree", "TASK-032 regression and policy matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def sensitive_scan(changed: list[str]) -> dict[str, Any]:
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
    return f"""# TASK-032 completion report

## Branch and base

Branch: `codex/task-032-process-local-fetch-queue-progress-history`
Base: `{base}`
HEAD: `{head}`

## Implementation and design summary

TASK-032 improves the Linux Mailing Lists operator experience by adding:
1. occasional, meaningful progress updates from running mailing-list fetches;
2. consistent operator-visible timestamps; and
3. bounded terminal fetch history that survives application restart.

The Process Local Fetch Queue remains the execution authority. Queued and running
fetch requests remain process-local and are not resumed after restart. Only bounded
operator-facing terminal history and selected display events are durable.

## Progress callback contract

`LinuxMailingListWorkflowService.fetch_up_to_date(...)` accepts an optional
`on_progress: Callable[[FetchProgress], None]` parameter. The `FetchProgress`
dataclass contains: `phase` ("acquiring" or "window_complete"), `message`,
`window_start`, `window_end`, `windows_completed`, and `occurred_at`.

Progress is emitted at the top of each ~31-day acquisition-window iteration and
after each window completes. The callback is best-effort: an exception while
publishing progress never fails the fetch.

## Where progress is emitted

In `src/rfi/mailing_lists/workflow.py`, inside the `while cursor <= through:` loop:
- At the top of each window: `phase="acquiring"` with the current window dates.
- After a window with no seed matches: `phase="window_complete"`.
- After a successful window completion: `phase="window_complete"`.

## Queue running-job updates

The queue's `_work` method passes an `on_progress` closure to
`fetch_up_to_date`. The closure acquires the existing `threading.Condition` lock,
updates `FetchJob.progress`, `FetchJob.message`, and `FetchJob.updated_at`,
and calls `_maybe_progress_event`.

## Progress-event coalescing

`_maybe_progress_event` emits a `progress` QueueEvent only when the current
sequence minus `_last_progress_sequence` is >= `PROGRESS_EVENT_MIN_INTERVAL` (3).
This prevents progress events from flooding the event log.

## Timestamp fields

- `FetchJob.queued_at` (existing, reused)
- `FetchJob.started_at` (existing, reused)
- `FetchJob.finished_at` (existing, reused)
- `FetchJob.updated_at` (new) — last progress or state update
- `QueueEvent.occurred_at` (existing, reused)
- All timestamps are UTC ISO-8601 strings from the queue's clock.

## Timestamp format and timezone

All timestamps are ISO-8601 UTC (`datetime.now(UTC).isoformat()`). The browser
renders them with `toLocaleString()` and `toLocaleTimeString()` for local display.

## Terminal history persistence

Terminal job summaries are persisted to the `mailing_list_fetch_history` SQLite
table via `MailingListRepository.record_fetch_history`. The queue's `_work`
method calls `_persist_history` after each terminal state transition
(completed, failed, cancelled). Abandoned jobs are persisted by `cancel_all`.

## Event scrollback persistence

Non-progress queue events are persisted to the `mailing_list_fetch_events` SQLite
table via `MailingListRepository.record_fetch_event`. The `_event` method calls
`_persist_event` for all non-progress events.

## Retention and pruning

- Terminal history: 50 entries (`FETCH_HISTORY_LIMIT = 50`)
- Event scrollback: 200 entries (`FETCH_EVENT_LIMIT = 200`)
- Pruning is deterministic: oldest eligible entries removed first
- Active process-local jobs are never pruned
- Pruning runs after each insert

## Restart semantics

After restart, crash, or host restart:
- queued jobs are not restored;
- a running job is not restored;
- the active queue starts empty;
- persisted terminal history remains visible;
- persisted bounded display events remain visible;
- durable mailing-list artifacts remain authoritative.

No active work is restored. Terminal history survives restart.

## API and browser compatibility

All existing queue routes preserved:
- `GET /api/linux-mailing-lists/fetches`
- `POST /api/linux-mailing-lists/fetches`
- `POST /api/linux-mailing-lists/fetches/{{stream_id}}`
- `POST /api/linux-mailing-lists/fetches/cancel-all`

Snapshot response adds fields compatibly: `history`, `history_limit`,
`durable_events`, `durable_event_limit`. Running job adds `progress` and
`updated_at`. Browser polling remains 1.5 seconds. No WebSockets or
additional workers introduced.

## Live Lore proof

See `live/live-proof.json` for the bounded live Lore proof record. The live
proof used a controlled bounded fetch against `linux-block` with a narrow
date range to demonstrate progress updates at window boundaries.

## Validation

{outcomes}

## Known limitations

- Progress is best-effort and coalesced, not a guaranteed telemetry stream.
- Progress events are not persisted to durable scrollback (only non-progress events).
- The process-local queue remains intentionally non-durable for active work.
- No individual-job cancellation (only bulk cancel-all).
- No WebSocket or server-sent events (by design).

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Process Local Fetch Queue | FIFO, suppression, cancellation, progress, timestamps | Complete |
| Durable terminal history | Bounded SQLite terminal and event scrollback | Complete |
| Progress callback | Optional backward-compatible progress reporting | Complete |
| Browser display | Progress, timestamps, history via 1.5s polling | Complete |
| Source, stream, acquisition | Governed config and bounded execution | Complete |
| Scheduling and queue recovery | Cross-restart background work | Not Started (out of scope) |
"""


def main() -> int:
    if not LIVE_INPUT.is_file() and LEGACY_LIVE_INPUT.is_file():
        LIVE_INPUT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_LIVE_INPUT, LIVE_INPUT)

    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    for path in (ZIP_PATH, ZIP_HASH, ZIP_INTEGRITY):
        path.unlink(missing_ok=True)

    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", "HEAD", "main").strip()
    committed = git("diff", "--name-only", f"{base}..{head}").splitlines()
    working = git("diff", "--name-only").splitlines()
    staged_names = git("diff", "--cached", "--name-only").splitlines()
    untracked_names = [
        path for path in git("ls-files", "--others", "--exclude-standard").splitlines()
        if path not in EXCLUDE_FROM_TASK
    ]
    changed = sorted(set(committed + working + staged_names + untracked_names))
    changed = [path for path in changed if path not in EXCLUDE_FROM_TASK]

    validations = [
        run("focused-task032", [sys.executable, "-m", "unittest", "tests.test_task032", "-v"]),
        run("task029-regression", [sys.executable, "-m", "unittest", "tests.test_task029", "-v"]),
        run("task028-regression", [sys.executable, "-m", "unittest", "tests.test_task028", "-v"]),
        run("task023-regression", [sys.executable, "-m", "unittest", "tests.test_task023", "-v"]),
        run("task021-regression", [sys.executable, "-m", "unittest", "tests.test_task021", "-v"]),
        run("task031-regression", [sys.executable, "-m", "unittest", "tests.test_task031", "-v"]),
        run("schema-migration", [sys.executable, "-m", "unittest", "tests.test_task021", "-v"]),
        run("fixture-proof", [sys.executable, "scripts/task023_mailing_lists.py", "fixture-proof"]),
        run("lint", [sys.executable, "scripts/quality.py", "lint"]),
        run("format", [sys.executable, "scripts/quality.py", "format"]),
        run("typecheck", [sys.executable, "scripts/quality.py", "typecheck"]),
        run("docs", [sys.executable, "scripts/check_docs.py"]),
        run("baseline", [sys.executable, "scripts/check_baseline.py"]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
        run("full-relevant", [
            sys.executable, "-m", "unittest",
            "tests.test_task032", "tests.test_task029", "tests.test_task028",
            "tests.test_task023", "tests.test_task021", "tests.test_task031",
            "tests.test_task025", "tests.test_task030",
        ]),
        isolated_validation(),
        sensitive_scan(changed),
    ]

    copies = {
        "task-ticket.md": ROOT / "tasks/TASK-032-process-local-fetch-queue-progress-history.md",
        "architecture/adr-0024.md": ROOT /
            "docs/decisions/0024-process-local-fetch-queue-progress-and-durable-history.md",
        "architecture/operator-console-design.md": ROOT /
            "docs/linux-mailing-list-operator-console.md",
        "evidence/focused-test.py": ROOT / "tests/test_task032.py",
        "evidence/queue.py": ROOT / "src/rfi/mailing_lists/queue.py",
        "evidence/workflow.py": ROOT / "src/rfi/mailing_lists/workflow.py",
        "evidence/repository.py": ROOT / "src/rfi/mailing_lists/repository.py",
        "evidence/contracts.py": ROOT / "src/rfi/mailing_lists/contracts.py",
        "evidence/sqlite.py": ROOT / "src/rfi/storage/sqlite.py",
        "evidence/server.py": ROOT / "src/rfi/admin/server.py",
        "evidence/linux_mailing_lists.html": ROOT / "src/rfi/admin/linux_mailing_lists.html",
        "browser/browser-proof.json": BROWSER_INPUT,
        "live/live-proof.json": LIVE_INPUT,
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
