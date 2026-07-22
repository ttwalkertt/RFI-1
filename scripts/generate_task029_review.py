#!/usr/bin/env python3
"""Generate the independently reviewable TASK-029 evidence package."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-029"
PACKAGE = ROOT / ".artifacts" / "review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
INPUT = ROOT / ".artifacts" / "review-input" / TASK_ID


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
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def run(name: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=ROOT,
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


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return result.stdout


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)

    validations = [
        run(
            "focused-task029",
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_task029",
                "tests.test_task029_ui_polish",
                "-v",
            ],
        ),
        run(
            "task028-regression",
            [sys.executable, "-m", "unittest", "tests.test_task028", "-v"],
        ),
        run(
            "streams-tab-unchanged",
            ["git", "diff", "--exit-code", "--", "src/rfi/admin/streams.html"],
        ),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
    ]

    sources = {
        "task-ticket.md": ROOT / "tasks/TASK-029-Simplify-Linux-Mailing-List-Operator-Workflow.md",
        "design/ui-design-and-architecture.md": (
            ROOT / "docs/linux-mailing-list-operator-console.md"
        ),
        "operator/operator-guide.md": ROOT / "docs/operator-guide.md",
        "operator/api-and-workflow.md": ROOT / "docs/linux-mailing-list-workflow.md",
        "browser/operator-console-browser-proof.json": (
            INPUT / "operator-console-browser-proof.json"
        ),
        "browser/ui-polish-browser-proof.json": INPUT / "ui-polish-browser-proof.json",
        "live/live-api-evidence.md": INPUT / "live-api-evidence.md",
    }
    for destination, source in sources.items():
        if not source.is_file():
            raise RuntimeError(f"required evidence absent: {source}")
        copy(destination, source)
    for screenshot in sorted((INPUT / "screenshots").glob("*")):
        if screenshot.suffix not in {".jpg", ".png"}:
            continue
        copy(f"browser/screenshots/{screenshot.name}", screenshot)

    status = git("status", "--short", "--branch")
    write("repository/git-status.txt", status)
    write("repository/unstaged.diff", git("diff", "--binary"))
    write("repository/staged.diff", git("diff", "--cached", "--binary") or "(empty)\n")
    write("repository/untracked.txt", git("ls-files", "--others", "--exclude-standard"))
    changed = sorted(
        set(git("diff", "--name-only").splitlines())
        | set(git("ls-files", "--others", "--exclude-standard").splitlines())
    )
    write(
        "repository/changed-files.json",
        json.dumps(
            {"files": changed, "note": "Consolidated TASK-028 and TASK-029 collection."},
            indent=2,
        )
        + "\n",
    )

    outcomes = "\n".join(
        f"- `{' '.join(item['command'])}` — "
        f"{'PASS' if item['passed'] else 'FAIL'}; see `validation/{item['name']}.txt`."
        for item in validations
    )
    report = f"""# TASK-029 completion report

## UI Design Summary

The Linux Mailing Lists page is now an operations console: selecting a saved stream opens a concise
summary, the primary card action catches that stream up, and configuration is disclosed only through
Edit. Fetch All and Cancel / Abandon All remain visible in the sidebar. Queue activity is kept in a
bounded status panel, while retained messages keep their independent scroll region. Save creates an
authoritative immutable revision and confirms it in a modal.

The design intentionally departs from the ticket's conceptual grouping by putting acquisition state
and action directly on each stream card. This makes the common decision—whether a stream needs a
fetch—visible without entering either summary detail or the editor.

## Repository guarantees

Catch-up derives coverage only from contiguous, complete, untruncated durable runs; uses a fixed
two-day overlap; splits work into bounded windows; and stops when a window is incomplete. The
process-local FIFO suppresses duplicates and checks cooperative cancellation without deleting
durable evidence. Queue state resets on restart; repository evidence does not. The Streams template
has no diff, and existing API shapes remain unchanged outside the new Linux-mailing-list endpoints.

## Validation

{outcomes}

Queue ordering, duplicate suppression, Fetch All, bounded multi-window acquisition, cancellation,
restart, effective coverage, and operator-console behavior are covered by `tests.test_task029` and
`tests.test_task029_ui_polish`.
Rendered interaction and live asynchronous API evidence are under `browser/` and `live/`.

## Architectural Status Summary

- Operator console and saved-stream summary/editor workflow — **Complete**.
- Effective repository-coverage derivation and bounded catch-up workflow — **Complete**.
- Process-local single-worker FIFO and bounded operational events — **Complete**; intentionally not
  durable and not a scheduler.
- Immutable evidence, source/revision authorities, and partial/incomplete semantics — **Complete**
  and preserved.
- Durable scheduling, resumable queue state, and cross-process coordination — **Not Started** and
  outside this milestone.
- Next milestone: evaluate real operator evidence before authorizing any durable scheduling layer.

The former placeholder task identifier was consolidated into TASK-029. No push, merge, clean, or
Streams-tab change was performed.
"""
    write("completion-report.md", report)

    failures = [str(item["name"]) for item in validations if not item["passed"]]
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1

    members = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
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
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE.parent))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
    checksum = sha256(ZIP_PATH)
    write("zip-integrity.txt", f"testzip: {bad_member or 'PASS'}\nsha256: {checksum}\n")
    checksum_path = ZIP_PATH.with_suffix(".zip.sha256")
    checksum_path.write_text(f"{checksum}  {ZIP_PATH.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "result": "PASS",
                "review_directory": str(PACKAGE.relative_to(ROOT)),
                "review_zip": str(ZIP_PATH.relative_to(ROOT)),
                "sha256": checksum,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
