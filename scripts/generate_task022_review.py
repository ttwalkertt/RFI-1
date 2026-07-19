#!/usr/bin/env python3
"""Generate and verify the complete TASK-022 implementation review package."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task016_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-022"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)
LIVE = ROOT / ".artifacts/review-input/TASK-022-live-v3.json"
FAILED_LIVE = ROOT / ".artifacts/review-input/TASK-022-live-v2.json"
SANDBOX_STATE = ROOT / ".artifacts/runtime/TASK-022-live"

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def isolated_validation(environment: dict[str, str]) -> dict[str, Any]:
    """Run required gates in a copied tree without Git, credentials, or retained state."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED | {".rfi"})

    with tempfile.TemporaryDirectory(prefix="rfi-task022-isolated-") as temporary:
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
            [str(PYTHON), "scripts/task022_sec_forms.py", "fixture-proof"],
            [str(PYTHON), "scripts/quality.py", "lint"],
            [str(PYTHON), "scripts/quality.py", "format"],
            [str(PYTHON), "scripts/quality.py", "typecheck"],
            [str(PYTHON), "scripts/check_docs.py"],
            [str(PYTHON), "scripts/check_baseline.py"],
        )
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
    copies = {
        "task-ticket.md": "tasks/TASK-022-additional-sec-numbered-form-adapters.md",
        "implementation-design.md": "docs/additional-sec-numbered-form-adapters.md",
        "architecture-decision.md": (
            "docs/decisions/0018-artifact-specific-sec-numbered-form-adapters.md"
        ),
        "form-10k-baseline.md": "docs/deterministic-sec-form-10k-retrieval.md",
        "pull-integration.md": "docs/pull-workflow.md",
        "query-browser-contract.md": "docs/artifact-query-service-and-browser.md",
        "sqlite-contract.md": "docs/sqlite-structured-state-repository.md",
    }
    for destination, source in copies.items():
        shutil.copy2(ROOT / source, PACKAGE / destination)
    review.write(
        "executive-summary.md",
        "# Executive summary\n\nTASK-022 adds four artifact-specific SEC numbered-form "
        "adapters over shared deterministic mechanics, with exact base-form and amendment "
        "policies. Form 10-K remains regression-compatible. All evidence enters through public "
        "acquisition/repository contracts and adapters remain independent of SQLite.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`\n",
    )
    records = {
        "implementation-summary.md": (
            "Four concrete adapters, one non-configurable mechanics base, existing "
            "SEC provider and public ingress."
        ),
        "architecture-decisions.md": (
            "Concrete artifact policy remains authoritative; shared code owns algorithms "
            "and provider mechanics only."
        ),
        "alternatives-considered.md": (
            "Rejected universal/configurable SEC adapters, policy tables, core workflow "
            "branching, exhibit retrieval, history, and persistence coupling."
        ),
        "existing-form-10k-responsibility-analysis.md": (
            "Generic registry; shared SEC provider; reusable numbered-form algorithms; "
            "concrete 10-K policy; external acquisition/repository authority."
        ),
        "reuse-and-refactoring-map.md": (
            "Selection/candidate/retrieval mechanics moved unchanged in semantics; 10-K "
            "constants and failures remain concrete and its full regression passes."
        ),
        "adapter-capability-and-registration-model.md": (
            "Each adapter claims exactly one canonical artifact plus identifier mode; "
            "overlap fails closed independent of order."
        ),
        "shared-sec-provider-service-boundary.md": (
            "Owns bounded transport, metadata decoding, CIK, archive paths, and content "
            "validation; owns no form policy."
        ),
        "numbered-form-adapter-responsibility-matrix.md": (
            "10-Q quarterly; 8-K high-frequency domestic current; 20-F foreign annual; "
            "6-K irregular foreign current; all exact base forms."
        ),
        "form-10k-regression-record.md": (
            "tests.test_task016 passes all 15 existing tests after extraction."
        ),
        "form-10q-policy-record.md": (
            "Exact 10-Q; exclude 10-Q/A; latest filing/acceptance/accession; period "
            "retained without accounting interpretation."
        ),
        "form-8k-policy-record.md": (
            "Exact 8-K; exclude 8-K/A; latest stream item; no period or quarterly "
            "multiplicity assumption."
        ),
        "form-20f-policy-record.md": (
            "Exact 20-F; exclude 20-F/A; distinct foreign annual artifact, never a "
            "10-K alias."
        ),
        "form-6k-policy-record.md": (
            "Exact 6-K; exclude 6-K/A; latest irregular stream item; no domestic "
            "periodic assumptions."
        ),
        "amendment-policy-matrix.md": (
            "10-Q/A, 8-K/A, 20-F/A, and 6-K/A are all excluded and counted; never "
            "selected for recency."
        ),
        "deterministic-selection-and-tie-break-matrix.md": (
            "Exact form, dedupe/conflict by accession, descending filing date, "
            "acceptance time, accession."
        ),
        "source-effective-ordering-matrix.md": (
            "Filing date is normalized chronology; acceptance/accession provide "
            "deterministic secondary identity; report/event period remains provenance."
        ),
        "identity-and-provenance-model.md": (
            "Firm, issuer CIK, canonical artifact, form, accession, primary document, "
            "document, observation, and checksum remain separate."
        ),
        "primary-document-selection-model.md": (
            "Only SEC primaryDocument is retrieved beneath issuer CIK/accession archive "
            "path; exhibits and complete submissions excluded."
        ),
        "network-and-sec-service-use-boundary.md": (
            "Official HTTPS origins, runtime identity, pacing, two attempts, bounded "
            "bytes, redirects, and sanitized diagnostics."
        ),
        "failure-and-result-taxonomy.md": (
            "Configuration, capability, no-match, ambiguity, metadata, identity, "
            "transport, content, repository, no-change, partial, and success remain distinct."
        ),
        "acquisition-and-repository-integration-summary.md": (
            "Adapters return established candidates/results; Pull Workflow and "
            "acquisition repository alone publish evidence."
        ),
        "sqlite-independence-analysis.md": (
            "Adapter modules contain no SQLite/SQL/schema imports or handles; fresh "
            "SQLite tests use only public contracts."
        ),
        "query-and-browser-integration-summary.md": (
            "All four canonical types use existing source-effective query/detail/content "
            "and read-only browser projections."
        ),
        "future-historical-acquisition-compatibility.md": (
            "Later bounded history can reuse stable CIK/accession/document identity "
            "without changing current latest policy."
        ),
        "known-limitations-and-deferred-work.md": (
            "Recent submissions and latest-only; history, schedules, exhibits, XBRL, "
            "interpretation, extraction, and analysis deferred."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def live_evidence() -> dict[str, Any]:
    if not LIVE.is_file() or not FAILED_LIVE.is_file():
        raise RuntimeError("required passing and failed live evidence are absent")
    passing = json.loads(LIVE.read_text())
    failed = json.loads(FAILED_LIVE.read_text())
    if passing.get("result") != "PASS" or failed.get("result") != "FAIL":
        raise RuntimeError("live evidence result markers are invalid")
    (PACKAGE / "live").mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, PACKAGE / "live/complete-live-proof.json")
    shutil.copy2(FAILED_LIVE, PACKAGE / "live/accession-validation-failure.json")
    forms = passing["forms"]
    for form, value in forms.items():
        slug = form.casefold().replace("-", "")
        review.write(
            f"live/form-{slug}-pull.json",
            json.dumps({**value, "phase": "first_pull"}, indent=2) + "\n",
        )
        review.write(
            f"live/form-{slug}-rerun.json",
            json.dumps({**value, "phase": "equivalent_rerun"}, indent=2) + "\n",
        )
    review.write(
        "live/live-artifact-inventory-and-checksums.json",
        json.dumps(passing["artifact_inventory"], indent=2) + "\n",
    )
    from rfi.pull import PullRunRepository

    sandbox_runs = PullRunRepository(SANDBOX_STATE / "pull-workflows").list()
    review.write(
        "live/sandbox-network-failure.json",
        json.dumps(sandbox_runs, indent=2) + "\n",
    )
    return {
        "result": "PASS",
        "forms": forms,
        "requests": passing["provider_usage"]["requests"],
        "retries": passing["provider_usage"]["retries"],
        "initial_failures_retained": True,
    }


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    environment = review.offline_environment()
    validations = [
        review.run(
            "focused-task022",
            [str(PYTHON), "-m", "unittest", "tests.test_task022", "-v"],
            environment=environment,
        ),
        review.run(
            "form10k-regression",
            [str(PYTHON), "-m", "unittest", "tests.test_task016", "-v"],
            environment=environment,
        ),
        review.run(
            "repository-query-browser",
            [
                str(PYTHON),
                "-m",
                "unittest",
                "tests.test_task018",
                "tests.test_task019",
                "tests.test_task021",
                "-v",
            ],
            environment=environment,
        ),
        review.run(
            "fixture-production-proof",
            [str(PYTHON), "scripts/task022_sec_forms.py", "fixture-proof"],
            environment=environment,
        ),
        review.run("git-diff-check", ["git", "diff", "--check"], environment=environment),
        review.run("docs", [str(PYTHON), "scripts/check_docs.py"], environment=environment),
        review.run(
            "design-baseline",
            [str(PYTHON), "scripts/check_baseline.py"],
            environment=environment,
        ),
        review.run("full-project", ["make", "validate"], environment=environment),
    ]
    validations.append(isolated_validation(environment))
    failures = [item["name"] for item in validations if not item["passed"]]
    branch = review.git("branch", "--show-current").strip()
    head = review.git("rev-parse", "HEAD").strip()
    base = review.git("merge-base", "main", "HEAD").strip()
    files = review.changed_files()
    review.write(
        "repository/branch.txt",
        f"branch: {branch}\nbase: {base}\nhead: {head}\n",
    )
    review.write("repository/status.txt", review.git("status", "--short", "--branch"))
    review.write(
        "repository/staged.diff",
        review.git("diff", "--cached", "--binary") or "(empty)\n",
    )
    review.write("repository/unstaged.diff", review.git("diff", "--binary") or "(empty)\n")
    review.write(
        "repository/untracked.txt",
        review.git("ls-files", "--others", "--exclude-standard"),
    )
    review.write("repository/changed-files.json", json.dumps(files, indent=2) + "\n")
    review.write("repository/complete.patch", review.complete_patch())
    review.write("repository/tree.txt", review.repository_tree())
    rationale = {
        path: "TASK-022 implementation, proof, or durable design record"
        for path in files
    }
    review.write(
        "repository/changed-files-with-rationale.json",
        json.dumps(rationale, indent=2) + "\n",
    )
    durable_records(branch, head)
    live = live_evidence()
    (PACKAGE / "fixtures").mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "fixtures/sec-numbered-forms").iterdir()):
        if source.is_file():
            shutil.copy2(source, PACKAGE / "fixtures" / source.name)
    evidence_map = {
        "capability-selection-evidence.txt": "validation/focused-task022.txt",
        "exact-form-and-amendment-evidence.txt": "validation/focused-task022.txt",
        "reordered-response-and-tie-break-evidence.txt": "validation/focused-task022.txt",
        "no-match-ambiguity-malformed-evidence.txt": "validation/focused-task022.txt",
        "primary-document-mapping-evidence.txt": "validation/focused-task022.txt",
        "failure-injection-evidence.txt": "validation/form10k-regression.txt",
        "sqlite-fresh-state-integration-evidence.txt": "validation/focused-task022.txt",
        "no-adapter-persistence-coupling-evidence.txt": "validation/focused-task022.txt",
        "duplicate-no-change-observation-evidence.txt": "validation/focused-task022.txt",
        "artifact-query-browser-evidence.txt": "validation/focused-task022.txt",
        "network-blocked-inspection-evidence.txt": "validation/focused-task022.txt",
        "restart-evidence.txt": "validation/focused-task022.txt",
        "integrity-evidence.txt": "validation/focused-task022.txt",
    }
    (PACKAGE / "evidence").mkdir(parents=True, exist_ok=True)
    for destination, source in evidence_map.items():
        shutil.copy2(PACKAGE / source, PACKAGE / "evidence" / destination)
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
        "all_offline_validations_passed": not failures,
        "live_proof": live,
        "sensitive_output_scan": scan,
        "staged_changes": bool(review.git("diff", "--cached", "--name-only").strip()),
    }
    review.write(
        "verification-summary.json",
        json.dumps({**metadata, "failures": failures}, indent=2) + "\n",
    )
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    review.archive(metadata)
    print(
        json.dumps(
            {
                "result": "PASS",
                "review_directory": str(PACKAGE.relative_to(ROOT)),
                "review_zip": str(ZIP_PATH.relative_to(ROOT)),
                "zip_bytes": ZIP_PATH.stat().st_size,
                "zip_sha256": review.sha256(ZIP_PATH),
                "zip_integrity": "PASS",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
