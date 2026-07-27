#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-039 review package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-039"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
ZIP_INTEGRITY = ZIP_PATH.with_suffix(".zip.integrity.txt")


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


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def complete_patch() -> str:
    parts = [git("diff", "--binary", "HEAD", "--", ".")]
    for relative in git("ls-files", "--others", "--exclude-standard").splitlines():
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(result.stdout)
        parts.append(result.stdout)
    return "".join(parts)


def run(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=ROOT, env={**os.environ, "PYTHONPATH": "src"}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
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


def completion_report(validations: list[dict[str, Any]], changed: list[str]) -> str:
    outcomes = "\n".join(
        f"- `{' '.join(item['command'])}` — "
        f"`{'PASS' if item['passed'] else 'FAIL'}` (exit {item['exit_code']})"
        for item in validations
    )
    return f"""# TASK-039 completion report

## Architectural rationale

Canonical `bounds.total_artifacts` continues to translate to the legacy internal
`expanded_limit` value and remains the seed-plus-context acquisition-batch allowance. Lore
relationship requests and durable continuation are unchanged and bounded.

Connected-discussion publication now has an independent, explicit component-integrity policy. It
rejects incomplete/quarantined component projections, then admits every member of a complete
component to one publication plan. The SQLite repository atomically commits the plan, memberships,
lineage, and succeeded run state; injected mid-insert failure rolls everything back. Paginated
membership reads remain unchanged.

A second finite publication count was intentionally not introduced: it would recreate the same
corpus-size rejection at another threshold and violate the ticket's requirement that complete
components publish regardless of acquisition batch count. Transactionality bounds failure exposure.
Publication-plan construction remains in memory; durable/paged construction is the appropriate
future safety mechanism if real component sizes demand it, but requires repository work outside this
no-migration milestone.

## Regression evidence

`tests/test_task039.py` acquires an eight-message connected discussion through at least three runs
with one-record relationship pages under `total_artifacts: 2`, then publishes more than two saved
members. It also proves paginated delivery, deterministic configuration translation, atomic
rollback after one attempted insert, and successful complete retry.

## Validation

{outcomes}

## Scope and changed files

No acquisition semantics, immutable artifact storage, UI, migration, branch, or remote operations
changed. Packaged files: {', '.join(f'`{item}`' for item in changed)}.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Lore acquisition | Bounded provider pages and resumable traversal | Complete |
| Stream configuration | Deterministic batch-limit translation | Complete |
| Connected publication policy | Complete component or none | Complete |
| Stream repository | Atomic plan, membership, lineage, and run-state publication | Complete |
| Membership query | Existing limit/offset delivery for published components | Complete |
| Durable paged plan construction | Bound large-plan memory | Not Started |

Next architectural milestone: gather production component-size evidence before considering durable
publication-plan construction; do not recouple it to acquisition batching.
"""


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    for path in (ZIP_PATH, ZIP_HASH, ZIP_INTEGRITY):
        path.unlink(missing_ok=True)

    changed = sorted(set(
        git("diff", "--name-only", "HEAD", "--", ".").splitlines()
        + git("ls-files", "--others", "--exclude-standard").splitlines()
    ))
    validations = [
        run("focused-task039", [
            sys.executable, "-m", "unittest", "tests.test_task039", "-v",
        ]),
        run("resumable-lore-regression", [
            sys.executable, "-m", "unittest", "tests.test_task031", "-v",
        ]),
        run("stream-publication-regression", [
            sys.executable, "-m", "unittest", "tests.test_task025", "-v",
        ]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
    ]

    for destination, source in {
        "task-ticket.md": ROOT /
            "tasks/TASK-039-split-acquisition-batch-and-publication-limits.md",
        "architecture/adr-0024.md": ROOT /
            "docs/decisions/0024-split-acquisition-batch-and-publication-limits.md",
        "architecture/stream-design.md": ROOT / "docs/revisioned-artifact-streams.md",
        "architecture/configuration.md": ROOT / "docs/stream-configuration-and-yaml.md",
        "evidence/test_task039.py": ROOT / "tests/test_task039.py",
    }.items():
        copy(destination, source)

    write("repository/git-status.txt", git("status", "--short", "--branch"))
    write("repository/complete.patch", complete_patch())
    write("repository/changed-files.json", json.dumps({"files": changed}, indent=2) + "\n")
    write("completion-report.md", completion_report(validations, changed))

    failures = [item["name"] for item in validations if not item["passed"]]
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1

    members = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "head_before_task_commit": git("rev-parse", "HEAD").strip(),
        "validation_outcomes": validations,
        "members": [{
            "path": path.relative_to(PACKAGE).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        } for path in members],
    }
    write("review-manifest.json", json.dumps(manifest, indent=2) + "\n")
    checksum_members = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    write("package-members.sha256", "".join(
        f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}\n"
        for path in checksum_members
    ))
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
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
        "result": "PASS", "review_zip": str(ZIP_PATH.relative_to(ROOT)),
        "zip_bytes": ZIP_PATH.stat().st_size, "zip_members": member_count,
        "zip_test": bad_member or "PASS", "sha256": checksum,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
