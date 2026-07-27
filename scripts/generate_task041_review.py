#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-041 review package."""

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
TASK_ID = "TASK-041"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"


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


def run(name: str, command: list[str]) -> dict[str, Any]:
    environment = {**os.environ, "PYTHONPATH": "src"}
    environment.pop("RFI_SEC_USER_AGENT", None)
    environment.pop("SEC_API_IO_API_KEY", None)
    result = subprocess.run(
        command, cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1200, check=False,
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


def complete_patch() -> str:
    parts = [git("diff", "--binary", "HEAD", "--", ".")]
    for relative in git("ls-files", "--others", "--exclude-standard").splitlines():
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(result.stdout)
        parts.append(result.stdout)
    return "".join(parts)


def completion_report(validations: list[dict[str, Any]], changed: list[str]) -> str:
    outcomes = "\n".join(
        f"- `{' '.join(item['command'])}` — "
        f"`{'PASS' if item['passed'] else 'FAIL'}` (exit {item['exit_code']})"
        for item in validations
    )
    files = ", ".join(f"`{item}`" for item in changed)
    return f"""# TASK-041 completion report

## Implementation and ownership

RFI discovers exactly `STATE/firm-config/*.firm-config.json`, rejects duplicate JSON keys, validates
the complete file set against packaged Draft 2020-12 schema version 1, applies deterministic domain
semantics, and materializes all accepted files in one SQLite transaction before serving or pulling.
RFI never writes the authoritative files.

The files own current rows in `firms`, `firm_revisions`, `firm_identifiers`, `firm_domains`,
`firm_external_identities`, `source_profiles`, `source_profile_revisions`,
`source_profile_items`, and `firm_config_authorities`. Stable firm IDs and all prior immutable
revisions remain. Microsoft is the first managed firm; unmanaged firms retain editor authority.

## Explicit non-ownership and preservation

The materializer does not populate or modify `sec_sources`, SEC workflow runs, governed sources,
acquisition attempts/runs, observations, artifacts, documents, hashes, content bytes, provenance,
resolved URLs/accessions, mailing-list discussions, streams, reports, source objects, or derived
knowledge. Focused tests retain an exact artifact hash/content, attempt history, observation
provenance, governed source, and a deliberately different mutable `sec_sources` row across
overwrite.

SEC JSON identity populates `firm_external_identities`; unchanged TASK-040 synthesis supplies CIK
candidates for enabled SEC artifacts. Runtime filing endpoints and identities remain derived.

## Executable SEC candidate repair

The raw materialized profile intentionally persists no derived candidates. Its effective SEC
candidate is synthesized from verified identity as `identifier` plus `CIK:<10 digits>`. The unsafe
gap was that synthesis bypasses repository candidate normalization and the planner previously used
artifact/mode compatibility without reapplying canonical required fields. The planner could
therefore call a malformed blank candidate runnable until adapter execution rejected it.

Synthesis now accepts only verified nonzero 10-digit CIKs. Materialization refuses enabled managed
SEC artifacts that cannot synthesize the locator. Planning applies the canonical mode requirements
before capability matching. The fixture-backed Microsoft pull records `sec-form-10k`,
`sec-form-10q`, and `sec-form-8k` selections and completes through the existing provider adapters
and acquisition engine. `parser_hint` remains blank because the existing convention selects by
artifact plus mode. Exact `sec_sources` rows are unchanged before and after the pull.

## Startup, transaction, and failure

SQLite initialization/migration precedes file handling. Structural and complete-set semantic
validation precede mutation. One `BEGIN IMMEDIATE` transaction appends firm/profile revisions,
moves current selectors, upserts SEC external identity and ownership, and advances the repository
revision once. Invalid sets and injected persistence failure leave all projections unchanged.
Missing previously managed files refuse startup. Repeated startup intentionally appends equivalent
revisions; change detection remains out of scope.

Managed firm/profile repository and HTTP writes fail closed while GET inspection remains available.
The UI displays the external filename and disables affected controls without removing legacy
editors.

## Validation

{outcomes}

## Scope and deviations

Changed files: {files}.

There were no ownership or preservation deviations from the controlling design. The proposed schema
was narrowed as authorized: schedules, SEC URLs, amendments/exhibits, historical selection modes,
and unimplemented non-SEC parser/adapter fields were removed. `sec_sources` remains exclusively
workflow-owned.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| External JSON contract | Complete Microsoft firm and supported SEC intent | Complete |
| Structural/semantic validation | Deterministic complete-set fail-closed checks | Complete |
| SQLite materializer | Atomic append/upsert projection with stable IDs | Complete |
| Authority enforcement | Managed writes rejected; read inspection retained | Complete |
| SEC external identity/synthesis | Verified CIK metadata and effective candidates | Complete |
| Pull candidate validation | Canonical required fields before capability matching | Complete |
| Numbered-form execution | Existing SEC adapters through acquisition ingress | Complete |
| Mutable SEC workflow knowledge | Resolver-owned `sec_sources` refresh | Complete, unchanged |
| Immutable acquisition/evidence | Artifacts and provenance | Complete, unchanged |
| Full-fleet file conversion | Convert remaining firms | Not Started |
| Change detection/file watching | Deferred behavior | Not Started |

Next architectural milestone: gather operator evidence from the Microsoft file-owned slice before
converting additional firms; do not add generalized configuration reconciliation.
"""


def main() -> int:
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_PATH.with_suffix(".zip.sha256").unlink(missing_ok=True)
    ZIP_PATH.with_suffix(".zip.integrity.txt").unlink(missing_ok=True)

    changed = sorted(set(
        git("diff", "--name-only", "HEAD", "--", ".").splitlines()
        + git("ls-files", "--others", "--exclude-standard").splitlines()
    ))
    validations = [
        run("focused-task041", [sys.executable, "-m", "unittest", "tests.test_task041", "-v"]),
        run("configuration-regressions", [
            sys.executable, "-m", "unittest",
            "tests.test_task011", "tests.test_task014", "tests.test_task015",
            "tests.test_task016", "tests.test_task022", "tests.test_task036",
            "tests.test_task038", "tests.test_task040", "-v",
        ]),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"]),
    ]
    for destination, source in {
        "task-ticket.md": ROOT / "tasks/TASK-041-external-firm-configuration-materialization.md",
        "architecture/adr-0026.md": ROOT /
            "docs/decisions/0026-external-firm-configuration-materialization.md",
        "architecture/design.md": ROOT / "docs/external-firm-configuration.md",
        "completion/repository-review.md": ROOT / "Docs/TASK-041-review.md",
        "contract/firm-config-v1.schema.json": ROOT / "docs/firm-config-v1.schema.json",
        "contract/microsoft.firm-config.example.json": ROOT /
            "docs/microsoft.firm-config.example.json",
        "evidence/test_task041.py": ROOT / "tests/test_task041.py",
    }.items():
        target = PACKAGE / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
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
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    ZIP_PATH.with_suffix(".zip.integrity.txt").write_text(
        f"testzip: {bad_member or 'PASS'}\nmembers: {member_count}\n"
        f"bytes: {ZIP_PATH.stat().st_size}\nsha256: {checksum}\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "result": "PASS", "zip": str(ZIP_PATH), "sha256": checksum,
        "members": member_count,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
