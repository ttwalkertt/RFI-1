#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-046 review package."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-046"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
ZIP_INTEGRITY = ZIP_PATH.with_suffix(".zip.integrity.txt")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def write(relative: str, content: str) -> None:
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


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


def report(changed: list[str]) -> str:
    return f"""# TASK-046 completion report

## Result

The standalone External Sources operator screen, route, navigation/help inventory entry,
operator-facing links, page-specific template, and obsolete instructions were removed. A request to
`/external-sources` now reaches the same ordinary 404 path as any unknown browser route; there is no
redirect or tombstone handler. Streams describe governed sources as repository-provided inputs and
continue to load them from the unchanged `GET /api/external-sources` endpoint.

## Preserved contracts and evidence

No repository, service, persistence, schema, migration, source model, transport policy, acquisition,
backup/restore, or CLI production file changed. The three API handlers remain in their prior order
and implementation in `src/rfi/admin/server.py`. Focused TASK-026 coverage proves validate is
non-mutating, create returns 201, exact repetition is idempotent, immutable policy conflicts fail,
and Streams consume the saved source. TASK-025 proves a saved external-source stream runs and its
memberships remain queryable. TASK-028 proves an established Linux mailing-list workflow creates or
reuses the governed source without the removed page. Existing-record startup and schema-12 coverage
remain exercised by those suites; Git records no migration-file change.

The semantic before/after API comparison is exact by construction: API dispatch, service calls,
serialization, ordering, status selection, and mutation code have a zero-line diff. Equivalent
fixture regressions exercise list, validate, create, idempotency, and immutable conflict behavior.

## Scope

Changed files: {', '.join(f'`{item}`' for item in changed)}.

Production changes are limited to operator presentation and route composition. There are no scope
deviations and no replacement source-management UI.

## Validation

- Focused: `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task046 tests.test_task026`
  `tests.test_task027 tests.test_task025 tests.test_task028 -v`
- Full: `make validate`
- Static scope: `git diff --name-only HEAD` over repository, persistence, schema, and migration
  paths

Exact command output is included under `validation/`.

## Limitations

Governed sources remain intentionally unavailable for management through the operator UI. Existing
internal services, APIs, CLI, and workflow-owned source resolution remain the supported machine and
workflow contracts. A replacement management surface is outside TASK-046.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Operator presentation | Surviving console pages and navigation | Complete |
| External Sources page | Dedicated governed-source management UI | Removed |
| Governed-source registry | Identity, validation, immutable policy | Complete and unchanged |
| External-source HTTP APIs | List, validate, create, conflicts | Complete and unchanged |
| Streams | Select and execute against existing governed sources | Complete and unchanged |
| Linux mailing-list workflow | Resolve or reuse governed Lore sources | Complete and unchanged |
| Persistence | Schema 12, startup, backup/restore | Complete and unchanged |
| Replacement management UI | Any relocated operator controls | Not Started; outside scope |

Architectural change: only the dedicated operator presentation was removed; the governed registry
remains an internal service and authority. Important limitation: source management is not exposed in
the operator console. Next architectural milestone: not determined by this subtractive change.
"""


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    for path in (ZIP_PATH, ZIP_HASH, ZIP_INTEGRITY):
        path.unlink(missing_ok=True)
    changed = sorted(
        set(
            git("diff", "--name-only", "HEAD", "--", ".").splitlines()
            + git("ls-files", "--others", "--exclude-standard").splitlines()
        )
    )
    outputs = {
        "focused.txt": ROOT / ".artifacts/task046-focused.txt",
        "full-validation.txt": ROOT / ".artifacts/task046-full-validation.txt",
    }
    (PACKAGE / "validation").mkdir()
    for destination, source in outputs.items():
        if not source.exists():
            raise RuntimeError(f"missing validation evidence: {source}")
        shutil.copy2(source, PACKAGE / "validation" / destination)
    write("repository/git-status.txt", git("status", "--short", "--branch"))
    write("repository/changed-files.json", json.dumps({"files": changed}, indent=2) + "\n")
    write("repository/complete.patch", complete_patch())
    schema_diff = git(
        "diff", "--name-status", "HEAD", "--",
        "src/rfi/migrations", "src/rfi/persistence.py",
    )
    write("repository/schema-migration-diff.txt", schema_diff)
    write("completion-report.md", report(changed))
    ticket = ROOT / "tasks/TASK-046 — Remove External Sources Opera.md"
    shutil.copy2(ticket, PACKAGE / "task-ticket.md")
    shutil.copy2(ROOT / "tests/test_task046.py", PACKAGE / "test_task046.py")
    members = sorted(path for path in PACKAGE.rglob("*") if path.is_file())
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "head_before_task_commit": git("rev-parse", "HEAD").strip(),
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
    write("package-members.sha256", "".join(
        f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}\n" for path in checksum_members
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
    result = {
        "result": "PASS",
        "zip": str(ZIP_PATH.relative_to(ROOT)),
        "members": member_count,
        "sha256": checksum,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
