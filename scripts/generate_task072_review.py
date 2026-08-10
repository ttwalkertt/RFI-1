#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-072 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-072"
ZIP_PATH = ROOT / ".artifacts/review/TASK-072-review.zip"
REPORT_PATH = ROOT / ".artifacts/review/TASK-072-review-report.json"
VALIDATION = ROOT / ".artifacts/task072-validation"
TASK071_STATE = ROOT / ".artifacts/task071-live-eval"
EXPECTED_OPERATOR_FILES = {"pull-results.txt", "pull_stx.py"}


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
    """Run one validation and retain its exact combined output."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    target = VALIDATION / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def review_tree_is_commit_exact() -> bool:
    """Permit only the known pre-existing operator scratch files outside the task range."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    lines = [line for line in result.stdout.splitlines() if line]
    unexpected = [
        line
        for line in lines
        if not (line.startswith("?? ") and line[3:] in EXPECTED_OPERATOR_FILES)
    ]
    if unexpected:
        raise RuntimeError(
            "review generation found task changes outside the committed range: "
            + ", ".join(unexpected)
        )
    return bool(lines)


def verify_documentation_scope(base_ref: str) -> dict[str, object]:
    """Prove the committed design task changed no production or test behavior."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    changed = sorted(item for item in result.stdout.splitlines() if item)
    allowed = {
        "TASKS.md",
        "docs/TASK-072-review.md",
        "docs/decisions/0028-agent-legible-rfi-mcp-boundary.md",
        "docs/design-baseline.json",
        "docs/rfi_mcp_surface_design.md",
        "scripts/generate_task072_review.py",
        "tasks/TASK-072-design-agent-legible-rfi-mcp-surface.md",
    }
    unexpected = sorted(set(changed) - allowed)
    report = {
        "base_ref": base_ref,
        "changed_files": changed,
        "allowed_files": sorted(allowed),
        "unexpected_files": unexpected,
        "production_files_changed": [
            item for item in changed if item.startswith("src/") or item.startswith("tests/")
        ],
        "result": "PASS" if result.returncode == 0 and not unexpected else "FAIL",
    }
    target = VALIDATION / "documentation-scope.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "name": "documentation-scope",
        "command": ["internal", "verify_documentation_scope", base_ref],
        "exit_code": 0 if report["result"] == "PASS" else 1,
    }


def build_seagate_summary() -> Path:
    """Condense the retained TASK-071 proving corpus and traces used by the design."""
    corpus_path = TASK071_STATE / "corpus.json"
    traces = TASK071_STATE / "traces"
    if not corpus_path.is_file():
        raise RuntimeError(f"retained TASK-071 corpus is unavailable: {corpus_path}")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for name in ("sentiment", "demand", "technology", "chronology", "insufficient"):
        path = traces / f"{name}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        result = value["result"]
        calls = [
            {
                "name": item["detail"].get("name"),
                "arguments": item["detail"].get("arguments", {}),
            }
            for item in value["trace"]
            if item["action"] in {"tool_call", "recovery_tool_call"}
        ]
        cases.append(
            {
                "case": name,
                "question": result["question"],
                "status": result["status"],
                "gaps": result["gaps"],
                "failed_searches": result["failed_searches"],
                "tool_calls": calls,
            }
        )
    summary = {
        "repository_snapshot": corpus["repository_snapshot"],
        "document_count": len(corpus["documents"]),
        "segment_count": corpus["segment_count"],
        "date_from": corpus["date_from"],
        "date_through": corpus["date_through"],
        "canonical_artifact_counts": corpus["canonical_artifact_counts"],
        "event_kind_counts": corpus["event_kind_counts"],
        "metadata_gaps": corpus["metadata_gaps"],
        "cases": cases,
    }
    target = VALIDATION / "seagate-design-input-summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate(base: str | None) -> int:
    """Validate the committed design range and assemble the review package."""
    base_ref = base or "origin/main"
    dirty_only_for_operator_files = review_tree_is_commit_exact()
    seagate_summary = build_seagate_summary()
    outcomes = [
        run(
            "implementation-contract-inventory",
            [
                "rg",
                "-n",
                (
                    "^    def (query|detail|content|read_artifact|search|expand|"
                    "inspect_document|health|assemble|inventory|by_source_object)"
                ),
                "src/rfi/artifacts",
                "src/rfi/acquisition/repository.py",
                "src/rfi/research",
                "src/rfi/retrieval",
                "src/rfi/source_objects",
                "src/rfi/knowledge",
            ],
        ),
        run("documentation-links", ["make", "docs-check"]),
        run("design-baseline", ["make", "baseline-check"]),
        run(
            "focused-current-contracts",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task018",
                "tests.test_task071",
                "tests.test_task006",
                "-v",
            ],
        ),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        verify_documentation_scope(base_ref),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-072 validations failed")

    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-072-design-agent-legible-rfi-mcp-surface.md",
        ),
        ("design/primary-design.md", ROOT / "docs/rfi_mcp_surface_design.md"),
        ("completion/architectural-review.md", ROOT / "docs/TASK-072-review.md"),
        (
            "design/architectural-decision.md",
            ROOT / "docs/decisions/0028-agent-legible-rfi-mcp-boundary.md",
        ),
        ("orientation/current-state.md", ROOT / "docs/current-state.md"),
        ("orientation/design-baseline.json", ROOT / "docs/design-baseline.json"),
        (
            "orientation/task071-retained-truth-catalog.md",
            ROOT / "docs/TASK-071-retained-truth-catalog.md",
        ),
        ("orientation/task071-review.md", ROOT / "docs/TASK-071-review.md"),
        ("evidence/artifact-contracts.py", ROOT / "src/rfi/artifacts/contracts.py"),
        ("evidence/artifact-service.py", ROOT / "src/rfi/artifacts/service.py"),
        ("evidence/research-contracts.py", ROOT / "src/rfi/research/contracts.py"),
        ("evidence/transcript-access.py", ROOT / "src/rfi/research/access.py"),
        ("evidence/investigation-harness.py", ROOT / "src/rfi/research/harness.py"),
        ("evidence/retrieval-contracts.py", ROOT / "src/rfi/retrieval/contracts.py"),
        ("evidence/source-object-contracts.py", ROOT / "src/rfi/source_objects/contracts.py"),
        ("evidence/knowledge-contracts.py", ROOT / "src/rfi/knowledge/contracts.py"),
        ("evidence/artifact-tests.py", ROOT / "tests/test_task018.py"),
        ("evidence/task071-tests.py", ROOT / "tests/test_task071.py"),
        ("evaluation/task071-corpus.json", TASK071_STATE / "corpus.json"),
        ("evaluation/seagate-design-input-summary.json", seagate_summary),
        *(
            (
                f"evaluation/task071-traces/{name}.json",
                TASK071_STATE / "traces" / f"{name}.json",
            )
            for name in ("sentiment", "demand", "technology", "chronology", "insufficient")
        ),
        *(
            (f"validation/{name}.txt", VALIDATION / f"{name}.txt")
            for name in (
                "implementation-contract-inventory",
                "documentation-links",
                "design-baseline",
                "focused-current-contracts",
                "committed-diff-check",
                "full-validation",
            )
        ),
        ("validation/documentation-scope.json", VALIDATION / "documentation-scope.json"),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-072",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
        allow_dirty=dirty_only_for_operator_files,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-072")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {
        **report,
        "zip": str(ZIP_PATH),
        "sha256": digest,
        "excluded_preexisting_operator_files": sorted(EXPECTED_OPERATOR_FILES),
    }
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    """Generate or verify one TASK-072 package."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    arguments = parser.parse_args()
    if arguments.verify:
        print(
            json.dumps(
                verify_package(arguments.verify, expected_task_id="TASK-072"), indent=2
            )
        )
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
