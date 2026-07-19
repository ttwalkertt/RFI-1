#!/usr/bin/env python3
"""Generate and verify the complete TASK-021 implementation review package."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task018_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-021"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation() -> dict[str, Any]:
    """Run the required checks without Git, credentials, or retained runtime state."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task021-isolated-") as temporary:
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
            [str(PYTHON), "scripts/task019_artifact_observations.py"],
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = "src"
        environment.pop("RFI_SEC_USER_AGENT", None)
        environment.pop("SEC_API_IO_API_KEY", None)
        output = [
            "Copied-tree validation; Git, state, artifacts, caches, and credentials excluded.",
            "",
        ]
        passed = True
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
    review.write("validation/isolated-tree.txt", "\n".join(output))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree validation matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def durable_records(branch: str, head: str) -> None:
    """Copy durable architecture records and create standalone reviewer summaries."""
    copies = {
        "task-ticket.md": "tasks/TASK-021-sqlite-structured-state-repository-foundation.md",
        "implementation-design.md": "docs/sqlite-structured-state-repository.md",
        "architecture-decision.md": (
            "docs/decisions/0017-fresh-sqlite-structured-state-foundation.md"
        ),
        "task020-design.md": "docs/storage_architecture_design_draft.md",
        "task020-decision.md": "docs/decisions/0016-hybrid-sqlite-structured-state.md",
        "task018-query-guidance.md": (
            "docs/TASK-018-engineering-guidance-artifact-query-contract.md"
        ),
        "task019-observation-contract.md": "docs/multiple-artifact-observations.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-021 implements fresh schema-version-1 SQLite authority "
        "for application structured state while immutable artifact bytes remain authoritative in "
        "the content-addressed filesystem. Public repository, query, observation, and browser "
        "contracts remain unchanged. No legacy migration, dual authority, artifact BLOB storage, "
        "PostgreSQL, browser redesign, or extraction redesign is introduced.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "One application SQLite database now persists concepts, firms, source profiles, "
            "governed sources, attempts, artifacts, observations, checkpoints, and pull runs. "
            "Immutable content remains under content/sha256 and is referenced by relative digest."
        ),
        "architecture-decisions.md": (
            "Fresh initialization was selected because retained POC state had no material value. "
            "SQLite provides the structured transaction boundary; filesystem objects preserve "
            "exact-byte authority; repository contracts prevent storage leakage."
        ),
        "alternatives-considered.md": (
            "Rejected general migration, permanent dual read/write, SQLite artifact BLOBs, a "
            "query-only read model, PostgreSQL without operating triggers, and retention of JSON "
            "pointer/ledger authority for new application repositories."
        ),
        "authority-model.md": (
            "repository.sqlite3 is the sole application structured authority. content/sha256 is "
            "the sole artifact-byte authority. Version-controlled governance remains external; "
            "rebuildable indexes and browser preferences remain non-authoritative."
        ),
        "sqlite-schema-and-version.md": (
            "Schema version 1 is recorded in schema_metadata and validated on every open. The "
            "executable STRICT-table DDL, keys, checks, foreign keys, and indexes are in "
            "src/rfi/storage/sqlite.py. No table declares BLOB storage."
        ),
        "schema-ownership-matrix.md": (
            "Concept tables belong to rfi.concepts; firm tables to rfi.firms; profile tables to "
            "rfi.source_profiles; acquisition/evidence/checkpoints to rfi.acquisition; pull_runs "
            "to rfi.pull; schema/repository metadata to rfi.storage."
        ),
        "transaction-boundary-analysis.md": (
            "Short BEGIN IMMEDIATE transactions atomically publish each logical structured "
            "mutation and authority revision. Firm batches are all-or-nothing. Provider calls and "
            "content streaming remain outside write transactions."
        ),
        "content-store-coordination-model.md": (
            "Bytes are exclusively created and flushed before the structured transaction. A "
            "transaction rollback can leave a detectable orphan; a missing referenced object is "
            "corruption. Verification never adopts, repairs, or deletes evidence."
        ),
        "repository-contract-preservation-matrix.md": (
            "Initialization, catalogs, pull records, acquisition ingress/replay, artifact query, "
            "latest/oldest, source-effective ordering, observation selection/navigation, content "
            "ranges, and read-only browser behavior retain their public contracts."
        ),
        "cursor-and-snapshot-model.md": (
            "Every reader-visible structured mutation increments "
            "repository_state.authority_revision. "
            "Opaque query and observation cursors bind to sqlite-revision-N and fail with "
            "stale_cursor after any intervening authority change."
        ),
        "firm-catalog-treatment.md": (
            "No legacy catalog importer was added. The existing deterministic sample_firms "
            "definitions are reseeded only by explicit, idempotent rfi seed. External firms-only "
            "YAML import remains an existing explicit contract, not migration tooling."
        ),
        "fresh-state-cutover-and-legacy-handling.md": (
            "rfi init creates repository.sqlite3 only in fresh compatible state. Known legacy "
            "catalog, acquisition, or pull markers cause legacy_state_detected. No old records are "
            "read, copied, rewritten, or deleted."
        ),
        "backup-and-restore-procedure.md": (
            "Backup verifies both authorities, uses SQLite online backup, and packages content "
            "with a size/SHA-256 manifest. Restore requires a fresh target and validates archive "
            "inventory, schema, SQLite integrity, foreign keys, references, and bytes."
        ),
        "integrity-and-recovery-model.md": (
            "Integrity checks classify database, foreign-key, relationship, missing-content, "
            "checksum, and orphan failures. Recovery is restore from verified backup or a future "
            "explicit repair task; no silent evidence rewrite is implemented."
        ),
        "remaining-legacy-persistence-inventory.md": (
            "Knowledge generations, retrieval/source-object rebuildable stores, and independent "
            "workspace history remain outside TASK-021 because they are separate authority or "
            "projection boundaries. Historical fixtures/tests exercise contracts, not parallel "
            "application structured authority."
        ),
        "known-limitations-and-deferred-work.md": (
            "One-host moderate concurrency only; no PITR/HA, multi-host writers, automatic repair, "
            "legacy import, speculative schema migration, or database artifact bytes. No newly "
            "discovered unscheduled work required a backlog entry."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def copy_proofs() -> None:
    """Expose raw focused proof output under requirement-oriented evidence names."""
    mapping = {
        "schema-proof.txt": "validation/focused-task021.txt",
        "initialization-proof.txt": "validation/focused-task021.txt",
        "duplicate-pull-proof.txt": "validation/task019-observation-proof.txt",
        "artifact-observation-content-count-proof.txt": (
            "validation/task019-observation-proof.txt"
        ),
        "query-equivalence-proof.txt": "validation/task018-browser-proof.txt",
        "browser-proof.txt": "validation/task018-browser-proof.txt",
        "no-blob-proof.txt": "validation/focused-task021.txt",
        "backup-restore-proof.txt": "validation/focused-task021.txt",
        "restart-proof.txt": "validation/focused-task021.txt",
        "network-blocked-proof.txt": "validation/task018-browser-proof.txt",
        "integrity-proof.txt": "validation/focused-task021.txt",
        "incompatible-version-proof.txt": "validation/focused-task021.txt",
        "legacy-state-rejection-proof.txt": "validation/focused-task021.txt",
        "sec-form-10k-fresh-state-proof.txt": "validation/task016-sec-proof.txt",
    }
    for destination, source in mapping.items():
        shutil.copy2(PACKAGE / source, PACKAGE / "evidence" / destination)


def main() -> int:
    """Run every gate and create a self-verifying review archive."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        review.run(
            "focused-task021",
            [str(PYTHON), "-m", "unittest", "tests.test_task021", "-v"],
        ),
        review.run(
            "task015-019-regression",
            [
                str(PYTHON),
                "-m",
                "unittest",
                "tests.test_task015",
                "tests.test_task016",
                "tests.test_task017",
                "tests.test_task018",
                "tests.test_task019",
                "-v",
            ],
        ),
        review.run(
            "task016-sec-proof",
            [str(PYTHON), "scripts/task016_sec_10k.py", "fixture-proof"],
        ),
        review.run(
            "task018-browser-proof", [str(PYTHON), "scripts/task018_artifact_browser.py"]
        ),
        review.run(
            "task019-observation-proof",
            [str(PYTHON), "scripts/task019_artifact_observations.py"],
        ),
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("documentation", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        review.run("lint", [str(PYTHON), "scripts/quality.py", "lint"]),
        review.run("format", [str(PYTHON), "scripts/quality.py", "format"]),
        review.run("typecheck", [str(PYTHON), "scripts/quality.py", "typecheck"]),
        review.run("full-project", ["make", "validate"]),
    ]
    validations.append(isolated_validation())
    branch = review.git("branch", "--show-current").strip()
    head = review.git("rev-parse", "HEAD").strip()
    base = review.git("merge-base", "main", "HEAD").strip()
    files = review.changed_files()
    review.write(
        "repository/branch-base-head.txt",
        f"branch: {branch}\nbase: {base}\nhead: {head}\n",
    )
    review.write("repository/git-status.txt", review.git("status", "--short", "--branch"))
    review.write(
        "repository/staged.diff", review.git("diff", "--cached", "--binary") or "(empty)\n"
    )
    review.write("repository/unstaged.diff", review.git("diff", "--binary") or "(empty)\n")
    review.write(
        "repository/untracked.txt",
        review.git("ls-files", "--others", "--exclude-standard"),
    )
    review.write("repository/cumulative-task.patch", review.complete_patch())
    review.write("repository/repository-tree.txt", review.repository_tree())
    review.write(
        "repository/changed-files-with-rationale.json",
        json.dumps(
            {
                path: "TASK-021 SQLite foundation, contract preservation, proof, or durable record"
                for path in files
            },
            indent=2,
        )
        + "\n",
    )
    durable_records(branch, head)
    (PACKAGE / "evidence").mkdir(exist_ok=True)
    copy_proofs()
    scan = review.sensitive_scan()
    failures = [item["name"] for item in validations if not item["passed"]]
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    review.write(
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
        "authority_model": "sqlite-structured-state-plus-content-addressed-filesystem-bytes",
        "legacy_migration_implemented": False,
        "artifact_blob_storage": False,
        "changed_files": files,
        "validation_outcomes": validations,
        "failures": failures,
        "sensitive_output_scan": scan,
    }
    review.write("verification-summary.json", json.dumps(metadata, indent=2) + "\n")
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    result = review.archive(metadata)
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
