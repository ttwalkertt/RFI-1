#!/usr/bin/env python3
"""Generate and verify the complete TASK-020 architecture review package."""

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
TASK_ID = "TASK-020"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation() -> dict[str, Any]:
    """Run documentation and project gates without Git, state, artifacts, or credentials."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task020-isolated-") as temporary:
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
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
            [str(PYTHON), "-c", "import rfi; print(rfi.__version__)"],
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


def architecture_records(branch: str, head: str) -> None:
    """Copy durable records and create independently readable decision summaries."""
    copies = {
        "task-ticket.md": "tasks/TASK-020-structured-repository-storage-architecture-review.md",
        "primary-deliverable.md": "docs/storage_architecture_design_draft.md",
        "architecture-decision.md": "docs/decisions/0016-hybrid-sqlite-structured-state.md",
        "governing-architecture.md": "ARCHITECTURE.md",
        "roadmap.md": "ROADMAP.md",
        "backlog.md": "BACKLOG.md",
        "task018-query-guidance.md": (
            "docs/TASK-018-engineering-guidance-artifact-query-contract.md"
        ),
        "task019-completion-record.md": "tasks/TASK-019-multiple-artifact-observations.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-020 recommends explicit hybrid relational authority: "
        "SQLite for authoritative structured runtime state, content-addressed filesystem objects "
        "for immutable artifact bytes, version-controlled governance/configuration files, and "
        "rebuildable indexes that remain non-authoritative. No migration or dependency is added. "
        "The decision is GO for a separately authorized, offline-reconciled migration task and "
        "NO-GO for permanent dual-write or database artifact BLOBs.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "options-and-recommendation.md": (
            "Compared current files, a relational read model, relational authority, explicit "
            "hybrid authority, and other stores. Relational authority is selected in hybrid form; "
            "the read-model-only option duplicates schemas without correcting write integrity."
        ),
        "authority-model.md": (
            "SQLite owns structured firms, concepts, profiles, acquisition records, metadata, "
            "knowledge history, and transactional projections. Exact artifact bytes remain in the "
            "content-addressed filesystem. Workspaces retain separate portable authority."
        ),
        "structured-data-byte-boundary.md": (
            "Bytes are immutably created and flushed first. A short structured transaction then "
            "references verified digest, size, and content location. Missing referenced bytes are "
            "corruption; unreferenced bytes are inspectable orphans."
        ),
        "record-handling-retain-retire.md": (
            "Retain domain identities, provenance, ordering, integrity, optimistic revisions, "
            "queries, and repository contracts. Retire JSON path/glob mechanics, pointer files, "
            "manual relational scans, and structured-file backup after verified cutover."
        ),
        "contract-preservation.md": (
            "Database schema remains private. TASK-018 query/summary/detail/content and TASK-019 "
            "observation semantics are differential compatibility gates; consumers never issue SQL."
        ),
        "transactions-concurrency-and-indexes.md": (
            "Short SQLite transactions atomically publish related structured records. WAL remains "
            "local-host, one-writer operation with concurrent readers. Indexes follow demonstrated "
            "firm/artifact chronology, observation, attempt, checkpoint, and provenance queries."
        ),
        "migration-rollback-and-authority-cutover.md": (
            "Inventory and freeze contracts, build an inactive adapter, import offline, compare "
            "all identities and public queries, back up, then switch one authority marker. No "
            "permanent dual-write or stale automatic fallback is allowed."
        ),
        "backup-restore-replay-and-corruption.md": (
            "Use the SQLite backup API or verified offline copies plus an immutable-byte manifest. "
            "Restore through staging and full verification. Replay only declared projections and "
            "fail closed on database, semantic, chain, or byte corruption."
        ),
        "embedded-versus-server.md": (
            "SQLite matches local single-writer evidence and standard-library deployment. "
            "PostgreSQL is triggered by multi-host writers, sustained write concurrency, remote "
            "service operation, HA, or point-in-time recovery requirements."
        ),
        "conceptual-schema.md": (
            "The primary deliverable defines repository metadata, catalog revision, acquisition, "
            "artifact observation, attempt, checkpoint, pull, knowledge, provenance, rebuildable "
            "index, and independently portable workspace table groups."
        ),
        "risks-unresolved-questions-and-triggers.md": (
            "Material risks are semantic drift, authority collapse, writer contention, backup "
            "misuse, byte/row divergence, migration damage, legacy loss, and product lock-in. "
            "Knowledge physical boundaries and recovery objectives remain implementation questions."
        ),
        "go-no-go.md": (
            "GO for a separately ticketed migration with offline shadow import, differential "
            "contract proof, backup/restore rehearsal, and one cutover. NO-GO for behavior change "
            "in TASK-020, ad hoc tables, permanent dual-write, or database BLOB migration."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def repository_evidence() -> None:
    """Capture the inspected persistence implementations and declared boundaries."""
    command = [
        "git",
        "grep",
        "-n",
        "-E",
        (
            "class .*Repository|sqlite3|current-generation|catalog.json|"
            "retrieval-ledger|artifact-observations"
        ),
        "--",
        "src/rfi",
        "docs/decisions",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    review.write(
        "evidence/current-storage-inventory.txt",
        f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n",
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("cannot capture current storage inventory")
    review.write(
        "evidence/product-source-links.md",
        "# Product source links\n\n"
        "- SQLite transactions: <https://www.sqlite.org/lang_transaction.html>\n"
        "- SQLite WAL: <https://www.sqlite.org/wal.html>\n"
        "- SQLite foreign keys: <https://www.sqlite.org/foreignkeys.html>\n"
        "- SQLite backup: <https://www.sqlite.org/backup.html>\n"
        "- PostgreSQL concurrency: <https://www.postgresql.org/docs/current/mvcc.html>\n"
        "- PostgreSQL backup: <https://www.postgresql.org/docs/current/backup.html>\n"
        "- DuckDB concurrency: <https://duckdb.org/docs/current/connect/concurrency>\n",
    )


def main() -> int:
    """Run all gates, capture evidence, and build a checksummed review archive."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("documentation", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        review.run("lint", [str(PYTHON), "scripts/quality.py", "lint"]),
        review.run("import", [str(PYTHON), "-c", "import rfi; print(rfi.__version__)"]),
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
                path: "TASK-020 architecture review, decision, governance, or evidence"
                for path in files
            },
            indent=2,
        )
        + "\n",
    )
    architecture_records(branch, head)
    repository_evidence()
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
        "recommendation": "hybrid-sqlite-authoritative-structured-state",
        "migration_implemented": False,
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
