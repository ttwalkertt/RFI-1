#!/usr/bin/env python3
"""Generate and verify the complete TASK-025 review package."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task018_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-025"
PACKAGE_ID = "TASK-025-HARDENED"
PACKAGE = ROOT / ".artifacts/review" / PACKAGE_ID
ZIP_PATH = PACKAGE.parent / f"{PACKAGE_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)
BROWSER = ROOT / ".artifacts/review-input/TASK-025-hardening-browser-proof.json"

review.TASK_ID = PACKAGE_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation() -> dict[str, Any]:
    """Run focused stream gates in a Git/state/artifact/credential-free copy."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task025-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [
                str(PYTHON), "-m", "unittest", "tests.test_task025",
                "tests.test_task025_hardening", "-v",
            ],
            [str(PYTHON), "scripts/task025_streams.py", "fixture-proof"],
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
        )
        environment = review.os.environ.copy()
        environment["PYTHONPATH"] = "src"
        environment.pop("RFI_SEC_USER_AGENT", None)
        environment.pop("SEC_API_IO_API_KEY", None)
        output = ["Copied-tree validation; Git, state, artifacts, and credentials excluded.", ""]
        passed = True
        for command in commands:
            result = review.subprocess.run(
                command, cwd=destination, env=environment, text=True,
                stdout=review.subprocess.PIPE, stderr=review.subprocess.STDOUT,
                check=False,
            )
            output.extend((
                f"$ {' '.join(command)}", result.stdout,
                f"exit_code: {result.returncode}", "",
            ))
            passed = passed and result.returncode == 0
    review.write("validation/isolated-tree.txt", "\n".join(output))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree focused stream validation matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def durable_records(branch: str, head: str) -> None:
    copies = {
        "task-ticket.md": (
            "tasks/TASK-025-revisioned-multilevel-artifact-streams-and-configuration.md"
        ),
        "implementation-design.md": "docs/revisioned-artifact-streams.md",
        "architecture-decision.md": "docs/decisions/0020-revisioned-artifact-stream-dag.md",
        "sqlite-foundation.md": "docs/sqlite-structured-state-repository.md",
        "artifact-browser-contract.md": "docs/artifact-query-service-and-browser.md",
        "stream-topology-fixture.json": "fixtures/streams/task025-topology.json",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    if not BROWSER.is_file():
        raise RuntimeError("required TASK-025 real-browser proof is absent")
    (PACKAGE / "evidence").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BROWSER, PACKAGE / "evidence/real-browser-proof.json")
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-025 adds revisioned external and derived artifact "
        "streams as bounded SQLite materialized projections over existing immutable artifacts. "
        "Validated DAG topology, typed schema capabilities, explicit transactional execution, "
        "membership lineage, offline rebuild, admin/CLI operation, and shared-browser inspection "
        "are complete across mail and SEC schemas. The hardening pass adds governed per-source "
        "Lore transport, truthful acquisition outcomes, a finite schema registry, and permanent "
        "no-match retention proof. Durable cursor-based polling remains explicitly deferred. No "
        "artifact bytes, graph database, broker, workflow engine, or second structured authority "
        "were added.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "Schema version 4, stream contracts/repository/service, finite capability/projection/"
            "expansion registry, governed Lore transport, explicit acquisition outcomes, bounded "
            "Boolean evaluator, connected mail expansion, SEC no-expansion proof, CLI, admin "
            "page, artifact-browser projection, fixtures, tests, and proof tooling."
        ),
        "architecture-and-boundaries.md": (
            "Stable streams point to immutable revisions. Relational dependency edges form a "
            "validated DAG. A finite registry adapts native schemas and expansion. Governed source "
            "profiles own transport; acquisition/evidence storage owns artifact lifetime. SQLite "
            "and the content-addressed store retain their prior roles."
        ),
        "sqlite-schema-and-migration.md": (
            "Version 3 adds definitions/revisions, dependencies, projections, runs, publication "
            "plans, memberships, and lineage. Version 4 adds mailing-run lifecycle/error fields "
            "and upgrades governed Lore profiles with a persisted default transport policy. "
            "Supported version 1/2/3 repositories migrate in place."
        ),
        "transaction-and-idempotency.md": (
            "Runs begin durably. Publication plan, memberships, lineage, counts, and succeeded "
            "status publish in one transaction. A mid-publication failure rolls back every new "
            "membership and leaves the prior successful view current. Revision plus normalized "
            "inputs fingerprints successful reruns."
        ),
        "typed-capabilities.md": (
            "Common schema/title/text/authors/date/source fields plus mail.list_id, "
            "mail.patch_version, sec.form_type, and sec.accession use registered operators. "
            "Bounded all/any/not rejects unsupported fields and operators explicitly."
        ),
        "membership-and-lineage.md": (
            "Each membership names stream revision, run, artifact/document, direct/context kind, "
            "reason, expansion, completeness, upstream membership, and seed. One artifact can "
            "participate in many streams without byte duplication. Acquisition/evidence storage "
            "owns artifact lifetime; membership and diagnostic counts never retain or delete it."
        ),
        "offline-rebuild.md": (
            "Durable successful-run publication plans rebuild only memberships and lineage, in "
            "deterministic run order, without remote access or artifact hash changes."
        ),
        "browser-proof.md": (
            "The fresh in-app-browser proof covers governed source selection, read-only transport "
            "policy, absent cursor/provider fields, schema-driven controls, retained streams and "
            "memberships, and zero warnings/errors."
        ),
        "cross-schema-proof.md": (
            "Deterministic retained SEC fixtures use the same projection, policy, execution, run, "
            "membership, lineage, rebuild, API, CLI, and browser contracts as mail streams. "
            "Forms 10-K and 20-F select through registered sec.form_type with expansion none."
        ),
        "negative-proof.md": (
            "Focused tests reject self-reference, indirect cycles, unsupported predicates, "
            "incomplete context, over-limit expansion, response overflow, and terminal HTTP. "
            "429/503, timeout, retry exhaustion, partial success, atomic publication, no-match "
            "retention, and migration are explicit. No mirror operation, browser policy authority, "
            "graph store, broker, or second persistence engine exists."
        ),
        "known-limitations-and-deferred-work.md": (
            "Remote Lore acquisition remains explicit and bounded before stream evaluation. No "
            "durable cursor exists, so repeated requests may repeat network work and this is not "
            "production-ready polling. Multi-process rate coordination, scheduling, continuous "
            "propagation, transformed artifacts, arbitrary joins, and retention deletion remain "
            "deferred."
        ),
        "architectural-status-summary.md": (
            "Stream definitions/revisions — Complete.\n\nDAG topology and topological execution — "
            "Complete.\n\nTyped projections and predicates — Complete for mail.message and "
            "sec.filing.\n\nMail connected expansion — Complete over retained TASK-023 "
            "evidence.\n\nRuns, membership, lineage, idempotency, failure isolation, "
            "rebuild — Complete.\n\nAdmin/CLI/REST/browser surfaces — Complete.\n\n"
            "Governed Lore transport and acquisition outcomes — Complete for explicit bounded "
            "Message-ID retrieval.\n\nDurable acquisition cursor / production polling — "
            "Deferred.\n\n"
            "Remote acquisition inside stream execution — Not started by design; acquisition "
            "remains a separate provider-I/O boundary.\n\nNext milestone — operational evidence "
            "should decide whether a durable cursor or another schema adapter is the next bounded "
            "increment."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def extract_fixture_proof() -> dict[str, Any]:
    raw = (PACKAGE / "validation/fixture-proof.txt").read_text(encoding="utf-8")
    start = raw.find("{\n")
    end = raw.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError("fixture proof JSON not found")
    return json.loads(raw[start:end])


def main() -> int:
    if PACKAGE.exists() or ZIP_PATH.exists() or ZIP_HASH.exists():
        raise RuntimeError(
            "TASK-025 review output already exists; generated files were not deleted"
        )
    PACKAGE.mkdir(parents=True)
    validations = [
        review.run(
            "focused-task025",
            [
                str(PYTHON), "-m", "unittest", "tests.test_task025",
                "tests.test_task025_hardening", "-v",
            ],
        ),
        review.run(
            "fixture-proof", [str(PYTHON), "scripts/task025_streams.py", "fixture-proof"]
        ),
        review.run(
            "stream-mail-storage-browser-regression",
            [
                str(PYTHON), "-m", "unittest", "tests.test_task014", "tests.test_task015",
                "tests.test_task017", "tests.test_task018", "tests.test_task021",
                "tests.test_task023", "tests.test_task024", "-v",
            ],
        ),
        review.run("lint", [str(PYTHON), "scripts/quality.py", "lint"]),
        review.run("format", [str(PYTHON), "scripts/quality.py", "format"]),
        review.run("typecheck", [str(PYTHON), "scripts/quality.py", "typecheck"]),
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("docs", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        review.run("full-project", ["make", "validate"]),
    ]
    validations.append(isolated_validation())
    failures = [item["name"] for item in validations if not item["passed"]]
    branch = review.git("branch", "--show-current").strip()
    head = review.git("rev-parse", "HEAD").strip()
    base = review.git("merge-base", "main", "HEAD").strip()
    files = review.changed_files()
    review.write(
        "repository/branch-base-head.txt", f"branch: {branch}\nbase: {base}\nhead: {head}\n"
    )
    review.write("repository/git-status.txt", review.git("status", "--short", "--branch"))
    review.write(
        "repository/staged.diff", review.git("diff", "--cached", "--binary") or "(empty)\n"
    )
    review.write("repository/unstaged.diff", review.git("diff", "--binary") or "(empty)\n")
    review.write(
        "repository/untracked.txt", review.git("ls-files", "--others", "--exclude-standard")
    )
    review.write("repository/cumulative-task.patch", review.complete_patch())
    review.write("repository/repository-tree.txt", review.repository_tree())
    review.write(
        "repository/changed-files-with-rationale.json",
        json.dumps(
            {path: "TASK-025 implementation, proof, test, documentation, or durable record"
             for path in files},
            indent=2,
        ) + "\n",
    )
    durable_records(branch, head)
    fixture = extract_fixture_proof()
    review.write("evidence/fixture-proof.json", json.dumps(fixture, indent=2) + "\n")
    evidence = {
        "governed-lore-transport-and-run-outcomes.md": (
            "focused-task025.txt and real-browser-proof.json"
        ),
        "no-match-artifact-retention.md": "focused-task025.txt and membership-and-lineage.md",
        "atomic-replacement-publication.md": (
            "focused-task025.txt and transaction-and-idempotency.md"
        ),
        "finite-schema-registry.md": "focused-task025.txt and typed-capabilities.md",
        "external-derived-multilevel-fanout.md": "fixture-proof.json and focused-task025.txt",
        "dag-and-capability-negative-proof.md": "negative-proof.md and focused-task025.txt",
        "connected-context-and-lineage.md": "fixture-proof.json and real-browser-proof.json",
        "cross-schema-sec-proof.md": "fixture-proof.json and real-browser-proof.json",
        "idempotency-failure-and-rebuild.md": "focused-task025.txt and fixture-proof.json",
        "migration-and-regression.md": "focused-task025.txt and full-project.txt",
        "browser-workflows.md": "real-browser-proof.json",
        "persistence-boundary.md": (
            "architecture-and-boundaries.md and sqlite-schema-and-migration.md"
        ),
    }
    for destination, sources in evidence.items():
        review.write(
            f"evidence/{destination}",
            f"# {destination.removesuffix('.md').replace('-', ' ').title()}\n\n"
            f"Primary evidence: {sources}.\n",
        )
    scan = review.sensitive_scan()
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    review.write(
        "validation-commands.md",
        "# Exact validation commands\n\n"
        + "\n".join(f"- `{' '.join(item['command'])}`" for item in validations) + "\n",
    )
    metadata = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "branch": branch,
        "base": base,
        "head": head,
        "changed_files": files,
        "validation_outcomes": validations,
        "failures": failures,
        "fixture_proof": fixture,
        "browser_proof": json.loads(BROWSER.read_text()),
        "sensitive_output_scan": scan,
        "generated_artifacts_excluded_from_product_diff": True,
    }
    review.write("verification-summary.json", json.dumps(metadata, indent=2) + "\n")
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    result = review.archive(metadata)
    print(json.dumps({
        "result": "PASS",
        "review_directory": str(PACKAGE.relative_to(ROOT)),
        "review_zip": str(ZIP_PATH.relative_to(ROOT)),
        "zip": result,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
