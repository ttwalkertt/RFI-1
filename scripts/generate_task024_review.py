#!/usr/bin/env python3
"""Generate and verify the complete TASK-024 review package."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task018_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-024"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)
BROWSER = ROOT / ".artifacts/review-input/TASK-024-browser-proof.json"

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation() -> dict[str, Any]:
    """Run focused validation in a Git/state/artifact-free repository copy."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task024-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [str(PYTHON), "-m", "unittest", "tests.test_task024", "-v"],
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
                command,
                cwd=destination,
                env=environment,
                text=True,
                stdout=review.subprocess.PIPE,
                stderr=review.subprocess.STDOUT,
                check=False,
            )
            output.extend(
                (f"$ {' '.join(command)}", result.stdout, f"exit_code: {result.returncode}", "")
            )
            passed = passed and result.returncode == 0
    review.write("validation/isolated-tree.txt", "\n".join(output))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree focused validation matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def durable_records(branch: str, head: str) -> None:
    copies = {
        "task-ticket.md": "tasks/TASK-024-pull-result-configuration-repair-navigation.md",
        "pull-workflow.md": "docs/pull-workflow.md",
        "source-profile-editor.md": "docs/firm-source-profiles-and-acquisition-template.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    if not BROWSER.is_file():
        raise RuntimeError("required browser proof input is absent")
    (PACKAGE / "evidence").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BROWSER, PACKAGE / "evidence/real-browser-proof.json")
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-024 makes identity-bearing pull configuration failures "
        "ordinary same-tab repair links to the existing source-profile editor. The editor gives "
        "explicit URL identity precedence, reveals and focuses the artifact, and completed pull "
        "results have a rehydratable history URL so browser Back restores the initiating result. "
        "No domain, persistence, popup, modal, or alternate editing boundary was introduced.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "The pull renderer links only configuration_problem artifacts carrying firm and "
            "artifact identity. Source Profiles consumes both query parameters and reveals the "
            "target. Completed run URLs reload durable results after native Back."
        ),
        "architecture-and-boundaries.md": (
            "Pull results remain a read projection. Source Profiles remains the only edit "
            "authority. The API already supplied both identities, so domain contracts, SQLite, "
            "source-profile revisioning, and acquisition execution are unchanged."
        ),
        "browser-navigation-proof.md": (
            "The real-browser proof records one tab before and after navigation, the exact firm "
            "and artifact URL, selected firm, opened category/artifact, highlight/focus, zero "
            "dialogs, and Back restoring five actionable statuses on the durable run URL."
        ),
        "api-identity-proof.md": (
            "Focused REST testing initiates a real local pull and verifies that the durable "
            "configuration_problem result contains exact firm_id=seagate and artifact_id=sec_10q."
        ),
        "negative-proof.md": (
            "The browser harness proves success and identity-free configuration statuses remain "
            "plain badges; there is no target attribute, window.open, dialog, or history "
            "replacement. Unknown firm identity cannot apply an artifact target to a fallback firm."
        ),
        "known-limitations-and-deferred-work.md": (
            "Deep links target the current editable source-profile revision, not the historical "
            "snapshot used by the completed pull. This is intentional repair behavior. Stale run "
            "IDs or template artifact IDs surface existing safe errors and require a fresh result."
        ),
        "architectural-status-summary.md": (
            "Pull result projection — Complete: actionable configuration failures link to "
            "repair.\n\n"
            "Source-profile editor — Complete: explicit firm selection and artifact "
            "reveal/focus.\n\n"
            "Browser history projection — Complete: durable run URL restores results after "
            "Back.\n\n"
            "Domain/API/persistence boundaries — Complete and unchanged.\n\n"
            "Next milestone — TASK-007 remains the next planned architectural layer; no adjacent "
            "scope was added by TASK-024."
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
            "focused-task024",
            [str(PYTHON), "-m", "unittest", "tests.test_task024", "-v"],
        ),
        review.run(
            "pull-source-profile-regression",
            [
                str(PYTHON),
                "-m",
                "unittest",
                "tests.test_task015",
                "tests.test_task017",
                "-v",
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
        "repository/staged.diff",
        review.git("diff", "--cached", "--binary") or "(empty)\n",
    )
    review.write(
        "repository/unstaged.diff", review.git("diff", "--binary") or "(empty)\n"
    )
    review.write(
        "repository/untracked.txt",
        review.git("ls-files", "--others", "--exclude-standard"),
    )
    review.write("repository/cumulative-task.patch", review.complete_patch())
    review.write("repository/repository-tree.txt", review.repository_tree())
    review.write(
        "repository/changed-files-with-rationale.json",
        json.dumps(
            {path: "TASK-024 implementation, proof, test, or durable record" for path in files},
            indent=2,
        )
        + "\n",
    )
    durable_records(branch, head)
    scan = review.sensitive_scan()
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
        "browser_proof": json.loads(BROWSER.read_text()),
        "sensitive_output_scan": scan,
        "generated_artifacts_excluded_from_product_diff": True,
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
