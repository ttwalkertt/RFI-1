#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-068 review package."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-068"
ZIP_PATH = ROOT / ".artifacts/review/TASK-068-review.zip"
VALIDATION = ROOT / ".artifacts/task068-validation"
REPORT_PATH = ROOT / ".artifacts/review/TASK-068-review-report.json"


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
    """Run and capture one deterministic review validation."""
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


def verify_documentation_scope(base_ref: str) -> dict[str, object]:
    """Prove the committed task did not change production behavior."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    changed = sorted(item for item in result.stdout.splitlines() if item)
    allowed_roots = ("docs/", "tasks/", "scripts/")
    allowed_files = {
        "ARCHITECTURE.md",
        "BACKLOG.md",
        "Makefile",
        "README.md",
        "ROADMAP.md",
        "TASKS.md",
        "src/rfi/__init__.py",
    }
    unexpected = [
        path
        for path in changed
        if path not in allowed_files and not path.startswith(allowed_roots)
    ]
    source_changes = [path for path in changed if path.startswith("src/rfi/")]
    source_ok = source_changes in ([], ["src/rfi/__init__.py"])
    source_behavior_ast_unchanged = True
    if source_changes:
        base_source = subprocess.run(
            ["git", "show", f"{base_ref}:src/rfi/__init__.py"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        def behavior_ast(source: str) -> str:
            tree = ast.parse(source)
            if (
                tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                tree.body.pop(0)
            return ast.dump(tree, include_attributes=False)

        source_behavior_ast_unchanged = (
            base_source.returncode == 0
            and behavior_ast(base_source.stdout)
            == behavior_ast((ROOT / "src/rfi/__init__.py").read_text(encoding="utf-8"))
        )
    report = {
        "base_ref": base_ref,
        "changed_files": changed,
        "unexpected_files": unexpected,
        "source_changes": source_changes,
        "source_behavior_ast_unchanged": source_behavior_ast_unchanged,
        "source_change_classification": (
            "package documentation string only" if source_changes else "none"
        ),
        "result": (
            "PASS"
            if (
                result.returncode == 0
                and not unexpected
                and source_ok
                and source_behavior_ast_unchanged
            )
            else "FAIL"
        ),
    }
    target = VALIDATION / "documentation-scope.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "name": "documentation-scope",
        "command": ["internal", "verify_documentation_scope", base_ref],
        "exit_code": 0 if report["result"] == "PASS" else 1,
    }


def generate(base: str | None) -> int:
    """Run validations and assemble the final committed review range."""
    base_ref = base or "origin/main"
    VALIDATION.mkdir(parents=True, exist_ok=True)
    outcomes = [
        run(
            "architecture-inventory",
            [
                ".venv/bin/python",
                "scripts/task068_architecture_inventory.py",
                "--output",
                str(VALIDATION / "architecture-inventory.json"),
            ],
        ),
        run("documentation-links", ["make", "docs-check"]),
        run("design-baseline", ["make", "baseline-check"]),
        run(
            "capability-claim-tests",
            [
                ".venv/bin/python",
                "-m",
                "unittest",
                "tests.test_task005",
                "tests.test_task006",
                "tests.test_task007",
                "tests.test_task008",
                "tests.test_task015",
                "tests.test_task018",
                "tests.test_task021",
                "tests.test_task064",
                "tests.test_task066",
                "tests.test_task067",
                "-v",
            ],
        ),
        run("committed-diff-check", ["git", "diff", "--check", f"{base_ref}..HEAD"]),
        verify_documentation_scope(base_ref),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-068 validations failed")
    copied = [
        (
            "task-ticket.md",
            ROOT
            / (
                "tasks/TASK-068_Reconcile_Repository_Design_Guidance_"
                "and_Current_Architectural_State.md"
            ),
        ),
        ("completion/architectural-review.md", ROOT / "docs/TASK-068-review.md"),
        ("orientation/current-state.md", ROOT / "docs/current-state.md"),
        ("orientation/README.md", ROOT / "README.md"),
        ("orientation/ARCHITECTURE.md", ROOT / "ARCHITECTURE.md"),
        ("orientation/ROADMAP.md", ROOT / "ROADMAP.md"),
        ("orientation/TASKS.md", ROOT / "TASKS.md"),
        ("orientation/BACKLOG.md", ROOT / "BACKLOG.md"),
        ("authority/design-baseline.md", ROOT / "docs/design-baseline.md"),
        ("authority/design-baseline.json", ROOT / "docs/design-baseline.json"),
        (
            "evidence/architecture-inventory.py",
            ROOT / "scripts/task068_architecture_inventory.py",
        ),
        ("evidence/root-package.py", ROOT / "src/rfi/__init__.py"),
        ("evidence/cli-composition.py", ROOT / "src/rfi/cli.py"),
        ("evidence/admin-composition.py", ROOT / "src/rfi/admin/server.py"),
        ("evidence/pull-composition.py", ROOT / "src/rfi/pull/__init__.py"),
        ("evidence/task005-tests.py", ROOT / "tests/test_task005.py"),
        ("evidence/task006-tests.py", ROOT / "tests/test_task006.py"),
        ("evidence/task007-tests.py", ROOT / "tests/test_task007.py"),
        ("evidence/task008-tests.py", ROOT / "tests/test_task008.py"),
        ("evidence/task066-blocked-review.md", ROOT / "docs/TASK-066-review.md"),
        *((f"validation/{name}.txt", VALIDATION / f"{name}.txt")
          for name in (
              "architecture-inventory",
              "documentation-links",
              "design-baseline",
              "capability-claim-tests",
              "committed-diff-check",
              "full-validation",
          )),
        (
            "validation/architecture-inventory.json",
            VALIDATION / "architecture-inventory.json",
        ),
        ("validation/documentation-scope.json", VALIDATION / "documentation-scope.json"),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-068",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base_ref,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-068")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {**report, "zip": str(ZIP_PATH), "sha256": digest}
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    """Generate or independently verify one review package."""
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--verify", type=Path)
    argument_parser.add_argument("--base")
    arguments = argument_parser.parse_args()
    if arguments.verify:
        print(json.dumps(
            verify_package(arguments.verify, expected_task_id="TASK-068"), indent=2
        ))
        return 0
    return generate(arguments.base)


if __name__ == "__main__":
    raise SystemExit(main())
