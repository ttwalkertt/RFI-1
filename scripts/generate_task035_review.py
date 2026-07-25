#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-035 review package."""

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

ROOT = Path(__file__).resolve().parents[1]
TASK = "TASK-035"
PACKAGE = ROOT / ".artifacts/review" / TASK
ZIP = PACKAGE.parent / f"{TASK}-review.zip"


def run(name: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command, cwd=ROOT, env={**os.environ, "PYTHONPATH": "src"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False, timeout=900,
    )
    target = PACKAGE / "validation" / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {
        "name": name, "command": command, "exit_code": result.returncode,
        "output": target.relative_to(PACKAGE).as_posix(),
    }


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ).stdout.strip()


def main() -> int:
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    python = str(Path(sys.executable))
    validations = [
        run("focused-task035", [python, "-m", "unittest", "tests.test_task035", "-v"]),
        run("mailing-list-regression", [
            python, "-m", "unittest", "tests.test_task030", "tests.test_task031",
            "tests.test_task032", "tests.test_task029", "tests.test_task028",
            "tests.test_task023", "tests.test_task021", "-v",
        ]),
        run("make-validate", ["make", "validate"]),
    ]
    if any(item["exit_code"] != 0 for item in validations):
        print(json.dumps(validations, indent=2))
        return 1

    ticket = ROOT / (
        "tasks/TASK-035-canonical-mailing-list-message-identity-"
        "and-observation-slice-revA.md"
    )
    shutil.copy2(ticket, PACKAGE / "ticket.md")
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    parent = git("rev-parse", "HEAD^")
    changed = git("diff", "--name-only", f"{parent}..{head}").splitlines()
    (PACKAGE / "changed-files.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")
    (PACKAGE / "repository-status.txt").write_text(
        f"branch: {branch}\ncommit: {head}\n\n{git('status', '--short', '--branch')}\n",
        encoding="utf-8",
    )
    report = f"""# TASK-035 completion report

Generated: {datetime.now(UTC).isoformat()}
Branch: `{branch}`
Commit: `{head}`

## Implemented authority boundary

Schema v7 owns one global `canonical_mailing_list_messages` mapping. It maps one valid normalized
Message-ID to a deterministic repository identifier and existing artifact/document records;
`source_id` is provenance and is absent from canonical identity. Exact bytes remain solely in the
content-addressed artifact store.

`mailing_list_run_items` remains the single active per-run observation authority. Durable columns
distinguish fetched, reused, and unavailable outcomes plus content fetch, artifact creation, and
canonical creation. Canonical registration/verification and its causing observation publish in one
SQLite transaction. Conflicting bytes never replace canonical content and produce inspectable
`mailing_list_message_conflicts` evidence.

## Migration and compatibility

The v6-to-v7 migration is additive. One shared Message-ID normalizer drives parsing, lookup,
registration, backfill, validation, and conflict grouping. Unambiguous retained RFC822 history is
backfilled deterministically. Historical multi-artifact identities are recorded as conflicts and
left uncollapsed. Existing run, artifact, document, relationship, discussion, and tombstone rows
are preserved. Historical observations conservatively use `reused` because old rows cannot prove
whether content was downloaded during their run.

## Proposal departures

The implementation intentionally does not install the proposal's wholesale global relationship,
discussion, parser-version, patch-series, or split observation schemas. It retains source-scoped
derived projections and evolves `mailing_list_run_items`; this is the smallest design consistent
with the ticket's one-authority and boundedness requirements.

## Proof index

- Canonical materialization and overlapping reuse: `validation/focused-task035.txt`,
  `test_first_materialization_and_overlapping_run_reuse`.
- Cross-source reuse: the same file, `test_cross_source_reuse_preserves_both_provenances`.
- Conflict fail-closed and diagnostic: the same file,
  `test_conflicting_bytes_fail_closed_with_diagnostic`.
- Migration/backfill preservation: the same file,
  `test_v6_upgrade_backfills_without_rewriting_runs_or_projections`.
- Unavailable then available: the same file,
  `test_unavailable_then_available_keeps_both_evidence_forms`.
- Integrity and backup/restore: the same file,
  `test_integrity_constraints_and_backup_restore`.
- Exact regression and full validation outputs are under `validation/`.

## Known limitations and deferred decisions

- Historical rows cannot reconstruct original content-fetch or creation facts and are marked
  conservatively.
- Conflict resolution is intentionally deferred; unresolved historical conflicts block canonical
  registration while preserving evidence.
- Source-scoped discussion and relationship identities remain rebuildable projections.
- Aliasing, semantic deduplication, parser/projection versions, patch series, generalized evidence
  stores, and large-corpus optimization remain deferred.

## Architectural Status Summary

- Immutable artifact authority — **Complete**. Existing content-addressed bytes remain
  authoritative.
- Global canonical mailing-list message identity — **Complete** for valid normalized retained RFC822
  messages, including cross-source reuse and fail-closed conflict diagnostics.
- Per-run acquisition observations — **Complete** for this slice; one immutable observation per run
  retains source, inclusion, seed, connectivity, fetch/reuse, and canonical outcome.
- Compatibility and integrity — **Complete** for v6 additive migration, validation, and
  backup/restore.
- Discussion and relationship projections — **Usable with Limitations** and intentionally unchanged;
  source-scoped, derived, and rebuildable.
- Next architectural milestone — resolve only deliberately scheduled global relationship/discussion
  or parser-version work; none is required by TASK-035.
"""
    (PACKAGE / "completion-report.md").write_text(report, encoding="utf-8")
    manifest = {
        "task": TASK, "branch": branch, "commit": head, "parent": parent,
        "changed_files": changed, "validations": validations,
    }
    (PACKAGE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE.parent))
    digest = hashlib.sha256(ZIP.read_bytes()).hexdigest()
    ZIP.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP.name}\n", encoding="utf-8"
    )
    with zipfile.ZipFile(ZIP) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    ZIP.with_suffix(".zip.integrity.txt").write_text(
        json.dumps({"sha256": digest, "bad_member": bad, "members": names}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"zip": str(ZIP), "sha256": digest, "members": len(names)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
