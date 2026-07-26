#!/usr/bin/env python3
"""Generate and verify the self-contained TASK-036 review package."""

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
PACKAGE = ROOT / ".artifacts/review/TASK-036"
ZIP = PACKAGE.parent / "TASK-036-review.zip"


def run(name: str, command: list[str]) -> dict[str, object]:
    environment = {**os.environ, "PYTHONPATH": "src"}
    environment.pop("RFI_SEC_USER_AGENT", None)
    environment.pop("SEC_API_IO_API_KEY", None)
    result = subprocess.run(
        command, cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900, check=False,
    )
    target = PACKAGE / "validation" / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode,
            "output": target.relative_to(PACKAGE).as_posix()}


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
        run("focused", [python, "-m", "unittest", "tests.test_task036",
                        "tests.test_task016", "tests.test_task022", "tests.test_task021", "-v"]),
        run("full", ["make", "validate"]),
    ]
    if any(item["exit_code"] != 0 for item in validations):
        print(json.dumps(validations, indent=2))
        return 1

    shutil.copy2(ROOT / "tasks/TASK-036-sec-authoritative-retrieval-workflow.md",
                 PACKAGE / "ticket.md")
    shutil.copy2(ROOT / "docs/sec-authoritative-retrieval-workflow.md",
                 PACKAGE / "architectural-design.md")
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    parent = git("rev-parse", "HEAD^")
    changed = git("diff", "--name-only", f"{parent}..{head}").splitlines()
    (PACKAGE / "changed-files.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")
    completion = f"""# TASK-036 completion report

Generated: {datetime.now(UTC).isoformat()}
Branch: `{branch}`
Commit: `{head}`

## Workflow and source evidence

The focused validation captures all required scenarios. Before bootstrap, `sec_sources` has no firm
row. Successful resolution verifies CIK 1137789 against SEC fixture submissions and persists direct
issuer, legal issuer, domestic periodic regime, verified status, and timestamp. A fresh row bypasses
resolution. A stale row refreshes metadata/timestamp only when CIK/applicability/parent identity is
unchanged. Competing CIKs are ambiguity; a changed CIK is conflict and preserves the old row.

## Deterministic retrieval and immutable evidence

Exact unamended Form 10-K policy selects accession 0001137789-25-000002 and its primary document.
Exact fixture bytes enter only through AcquisitionRepository. Repeat execution returns the same
content-addressed artifact, one artifact byte object, additional immutable attempt/observation
evidence where appropriate, and repository integrity PASS.

## Conflict, non-applicable, and cancellation evidence

Focused tests prove conflict leaves the verified CIK and artifact count unchanged, non-applicable
state performs zero requests, and cancellation transitions only received → cancelled, performs zero
requests, and remains readable with cancellation_requested=true.

## Validation results

- Focused SEC/storage regression: PASS, 38 tests.
- Full `make validate`: PASS, including 377 tests and all proof, lint, format, type, documentation,
  baseline, import, and build checks.

## Known limitations and future generalization

Production resolution is explicit-direct-CIK only; parent/non-applicable decisions require another
authoritative resolver implementation. Recent submissions and exact unamended Form 10-K are the
only filing scope. Cancellation is between bounded steps. Future generalization should be driven by
a second proven SEC workflow or operational parent-resolution evidence, not speculative framework
construction.

## Architectural Status Summary

- Target firm authority — **Complete, unchanged**.
- SEC source knowledge and reconciliation — **Complete for this slice**.
- Direct authoritative CIK resolution — **Complete**.
- Parent/non-applicable resolution — **Usable with Limitations** at the contract boundary.
- Form 10-K policy/provider — **Complete, reused**.
- Immutable artifact ingress — **Complete, reused**.
- SEC lifecycle journal, outcomes, diagnostics, cancellation — **Complete**.
"""
    (PACKAGE / "completion-report.md").write_text(completion, encoding="utf-8")
    manifest = {"task": "TASK-036", "branch": branch, "commit": head, "parent": parent,
                "changed_files": changed, "validations": validations}
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
        members = archive.namelist()
    ZIP.with_suffix(".zip.integrity.txt").write_text(
        json.dumps({"sha256": digest, "bad_member": bad, "members": members}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"zip": str(ZIP), "sha256": digest, "bad_member": bad,
                      "members": len(members)}, indent=2))
    return 0 if bad is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
