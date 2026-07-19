#!/usr/bin/env python3
"""Generate and verify the complete TASK-023 review package."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task018_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-023"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)
LIVE = ROOT / ".artifacts/review-input/TASK-023-live-proof.json"
BROWSER = ROOT / ".artifacts/review-input/TASK-023-browser-proof.json"

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation() -> dict[str, Any]:
    """Run focused functionality and policies in a Git/state/artifact-free copy."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task023-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [str(PYTHON), "-m", "unittest", "tests.test_task023", "-v"],
            [str(PYTHON), "scripts/task023_mailing_lists.py", "fixture-proof"],
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
        "name": "isolated-tree", "command": ["copied-tree focused validation matrix"],
        "exit_code": 0 if passed else 1, "passed": passed,
    }


def durable_records(branch: str, head: str) -> None:
    copies = {
        "task-ticket.md": "tasks/TASK-023-linux-kernel-mailing-list-intelligence-stream.md",
        "implementation-design.md": "docs/linux-kernel-mailing-list-intelligence-stream.md",
        "architecture-decision.md": (
            "docs/decisions/0019-bounded-mailing-list-discussion-projection.md"
        ),
        "sqlite-foundation.md": "docs/sqlite-structured-state-repository.md",
        "artifact-browser-contract.md": "docs/artifact-query-service-and-browser.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    (PACKAGE / "fixtures").mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "fixtures/linux-block").iterdir()):
        if source.is_file():
            shutil.copy2(source, PACKAGE / "fixtures" / source.name)
    if not LIVE.is_file() or not BROWSER.is_file():
        raise RuntimeError("required live or browser proof input is absent")
    (PACKAGE / "live").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "evidence").mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, PACKAGE / "live/live-bounded-proof.json")
    shutil.copy2(BROWSER, PACKAGE / "evidence/shared-browser-demonstration.json")
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-023 adds bounded Linux block-layer mailing-list "
        "acquisition and lazy discussion browsing over the existing immutable artifact and "
        "SQLite repository. Header-derived ancestor closure is an admission invariant; missing "
        "connectors, cycles, and malformed identity fail closed. No archive mirror, graph "
        "database, or separate browser was introduced.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "Lossless RFC 5322 retention, bounded two-stage acquisition, durable run manifests, "
            "rebuildable reply/discussion state, bounded query contracts, CLI operation, schema "
            "migration, and a sibling shared-browser projection are complete."
        ),
        "architecture-and-boundaries.md": (
            "The archive adapter discovers/fetches only. Acquisition owns bounded planning. The "
            "shared acquisition repository owns bytes and observations. MailingListRepository "
            "owns SQLite state. MailingListQueryService supplies browser/CLI projections."
        ),
        "sqlite-schema-and-migration.md": (
            "Schema version 2 adds sources, immutable runs/run-items, rebuildable messages, "
            "relationships, discussions, and membership. Version 1 migrates in place; artifact "
            "bytes remain outside SQLite."
        ),
        "relationship-and-connectivity-model.md": (
            "In-Reply-To supplies direct header authority. References remain evidence. Every "
            "connected/truncated member is validated to one stored root through complete acyclic "
            "paths. Missing connectors are incomplete; malformed identities/cycles quarantined."
        ),
        "transaction-semantics.md": (
            "Exact artifacts publish through the established bytes-first repository. One run "
            "manifest, all run items, and a complete derived projection then publish in one "
            "SQLite transaction. Earlier artifact observations cannot enter either browser "
            "projection without the structured publication."
        ),
        "bounded-acquisition-semantics.md": (
            "No empty selection exists. Seed limits are 1-100; context limits 1-500. Ancestors "
            "may cross discovery windows. Descendants expand breadth-first and truncate only at "
            "a frontier. Live operation accepts explicit Message-IDs only."
        ),
        "browser-projection-design.md": (
            "The existing artifact browser has sibling firm and development-mailing-list roots. "
            "Sources, discussions, roots, and direct children load lazily from query contracts; "
            "the detail/content mechanisms expose retained evidence safely."
        ),
        "alternatives-considered.md": (
            "Rejected archive mirroring, subject-based threading, browser graph inference, graph "
            "databases, parallel structured stores, a separate browser, and speculative patch "
            "parsing. SQLite satisfies the demonstrated bounded traversal workload."
        ),
        "negative-proof.md": (
            "Tests prove unbounded selection unavailable, missing connectors never complete, "
            "limits preserve connector paths, subject similarity creates no edge, browser source "
            "contains no threading parser, and dependencies include no graph persistence engine."
        ),
        "known-limitations-and-deferred-work.md": (
            "Live descendant enumeration, broad Lore query parsing, incremental cursors, patch "
            "series/revision relationships, cross-list federation, participant resolution, FTS, "
            "and comprehensive MIME text extraction remain deferred."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        review.run(
            "focused-task023",
            [str(PYTHON), "-m", "unittest", "tests.test_task023", "-v"],
        ),
        review.run(
            "fixture-production-proof",
            [str(PYTHON), "scripts/task023_mailing_lists.py", "fixture-proof"],
        ),
        review.run(
            "storage-browser-regression",
            [str(PYTHON), "-m", "unittest", "tests.test_task018", "tests.test_task021",
             "tests.test_task022", "-v"],
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
        "repository/staged.diff",
        review.git("diff", "--cached", "--binary") or "(empty)\n",
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
        json.dumps({path: "TASK-023 implementation, proof, or durable record" for path in files},
                   indent=2) + "\n",
    )
    durable_records(branch, head)
    fixture_output = (PACKAGE / "validation/fixture-production-proof.txt").read_text()
    start = fixture_output.find("{\n")
    end = fixture_output.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError("fixture proof JSON not found")
    fixture = json.loads(fixture_output[start:end])
    review.write("evidence/fixture-proof.json", json.dumps(fixture, indent=2) + "\n")
    evidence = {
        "ancestor-closure-and-branching.md": "focused-task023.txt and fixture-proof.json",
        "missing-connector-and-cycle.md": "focused-task023.txt",
        "frontier-truncation.md": "focused-task023.txt",
        "idempotency-and-conflict.md": "focused-task023.txt and fixture-proof.json",
        "offline-rebuild.md": "focused-task023.txt and fixture-proof.json",
        "schema-migration.md": "focused-task023.txt",
        "query-and-browser-api.md": "focused-task023.txt and shared-browser-demonstration.json",
        "negative-architecture-proof.md": "negative-proof.md and focused-task023.txt",
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
        "schema_version": 1, "task_id": TASK_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(), "branch": branch,
        "base": base, "head": head, "changed_files": files,
        "validation_outcomes": validations, "failures": failures,
        "live_proof": json.loads(LIVE.read_text()),
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
        "result": "PASS", "review_directory": str(PACKAGE.relative_to(ROOT)),
        "review_zip": str(ZIP_PATH.relative_to(ROOT)), "zip": result,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
