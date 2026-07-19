#!/usr/bin/env python3
"""Generate and verify the complete TASK-019 review directory and ZIP."""

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
TASK_ID = "TASK-019"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation() -> dict[str, Any]:
    """Run TASK-019 and complete copied-tree gates without Git, state, or credentials."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task019-isolated-") as temporary:
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
        output = ["Copied-tree validation; Git, state, artifacts, and credentials excluded.", ""]
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
    """Copy durable decisions and provide architect-facing review summaries."""
    copies = {
        "task-ticket.md": "tasks/TASK-019-multiple-artifact-observations.md",
        "architecture-decisions.md": (
            "docs/decisions/0015-multiple-immutable-artifact-observations.md"
        ),
        "artifact-observation-contract.md": "docs/multiple-artifact-observations.md",
        "repository-query-contract.md": "docs/artifact-query-service-and-browser.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-019 separates content-addressed artifact identity, "
        "immutable acquisition observation identity, and run-bound acquisition-attempt identity. "
        "Repeated unchanged pulls append observations without copying bytes or conflicting with "
        "prior attempts. Artifact detail now selects and navigates exactly one snapshot-bound "
        "observation while the stored preview remains fixed.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "A separate authoritative observation store, legacy read projection, run-bound "
            "attempt identities, normalized observation detail, opaque navigation cursors, and "
            "browser Previous/Next controls implement the correction."
        ),
        "identity-and-ownership.md": (
            "Artifact ID is the exact-byte SHA-256 identity. Observation ID identifies one "
            "successful acquisition observation and references one artifact and attempt. Attempt "
            "ID is bound to one engine run and remains idempotent when that run retries."
        ),
        "duplicate-pull-proof.md": (
            "The operator proof and focused workflow regression pull unchanged bytes through two "
            "profile revisions: one artifact, two observations, distinct attempts, unchanged "
            "stored bytes, no immutable conflict, and integrity PASS."
        ),
        "observation-navigation-proof.md": (
            "Detail supports first, last, and explicit observation identity. Next and Previous "
            "use opaque state-digest-bound cursors; repository change returns stale_cursor."
        ),
        "replay-rebuild-and-integrity.md": (
            "Observations are authoritative local records. Replay rebuilds existing document and "
            "checkpoint views from attempts, preserves observation order, and verifies every "
            "observation-to-attempt/artifact/source relationship."
        ),
        "browser-behavior.md": (
            "Browser detail defaults to last. Navigation replaces observation metadata only; a "
            "guard keyed by artifact ID prevents preview reconstruction for the same artifact."
        ),
        "known-limitations-and-deferred-work.md": (
            "Navigation is limited to observations of the current immutable artifact selected for "
            "a document. There is no metadata merging, repair, mutation, comparison, filtering, "
            "timeline, extraction redesign, planner, or cross-artifact history browser."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def main() -> int:
    """Run every gate, capture repository evidence, and build a verified archive."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        review.run(
            "focused-task019",
            [str(PYTHON), "-m", "unittest", "tests.test_task019", "-v"],
        ),
        review.run(
            "task018-regression",
            [str(PYTHON), "-m", "unittest", "tests.test_task018", "-v"],
        ),
        review.run("operator-proof", [str(PYTHON), "scripts/task019_artifact_observations.py"]),
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("docs", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"]),
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
        json.dumps(
            {path: "TASK-019 implementation, proof, or durable record" for path in files},
            indent=2,
        )
        + "\n",
    )
    architecture_records(branch, head)
    proof_text = (PACKAGE / "validation/operator-proof.txt").read_text(encoding="utf-8")
    start = proof_text.find("{\n")
    end = proof_text.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError("operator proof JSON not found")
    review.write("evidence/operator-proof.json", proof_text[start:end] + "\n")
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
    print(json.dumps({
        "result": "PASS",
        "review_directory": str(PACKAGE.relative_to(ROOT)),
        "review_zip": str(ZIP_PATH.relative_to(ROOT)),
        "zip": result,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
