#!/usr/bin/env python3
"""Generate and verify the complete TASK-026 independent review package."""

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
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-026"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(review.sys.executable)
BROWSER_PROOF = ROOT / ".artifacts/review-input/TASK-026-browser-proof.json"

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def environment() -> dict[str, str]:
    """Return a deterministic validation environment without live credentials."""
    value = os.environ.copy()
    value["PYTHONPATH"] = "src"
    value.pop("RFI_SEC_USER_AGENT", None)
    value.pop("SEC_API_IO_API_KEY", None)
    return value


def command(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """Run one proof command with stdout and stderr retained separately."""
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def cli_proof() -> dict[str, Any]:
    """Capture exact sequential CLI schema, validation, import, export, and revision proof."""
    with tempfile.TemporaryDirectory(prefix="rfi-task026-cli-") as temporary:
        root = Path(temporary)
        state = root / "state"
        external = ROOT / "fixtures/streams/task026-external.yaml"
        derived = ROOT / "fixtures/streams/task026-derived.yaml"
        invalid = root / "invalid.yaml"
        invalid.write_text(
            external.read_text(encoding="utf-8").replace(
                "artifact_schema: mail.message", "artifact_schema: unsupported.schema"
            ),
            encoding="utf-8",
        )
        changed = root / "changed.yaml"
        changed.write_text(
            external.read_text(encoding="utf-8").replace(
                "direct_matches: 25", "direct_matches: 26"
            ),
            encoding="utf-8",
        )
        schema_file = root / "schema.yaml"
        export_file = root / "export.yaml"
        setup = command([
            str(PYTHON), "scripts/task026_streams.py", "prepare-state", "--state", str(state)
        ])
        commands = (
            ("help", [str(PYTHON), "-m", "rfi", "stream", "--help"]),
            ("schema", [str(PYTHON), "-m", "rfi", "stream", "schema"]),
            ("validate", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "validate", "--file", str(external),
            ]),
            ("invalid", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "validate", "--file", str(invalid),
            ]),
            ("import-new", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "import", "--file", str(external), "--new",
            ]),
            ("import-derived", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "import", "--file", str(derived), "--new",
            ]),
            ("export-stdout", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "export", "--stream", "linux-block-storage",
            ]),
            ("export-file", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "export", "--stream", "linux-block-storage", "--output", str(export_file),
            ]),
            ("import-revision", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "import", "--file", str(changed), "--revision",
            ]),
            ("import-identical", [
                str(PYTHON), "-m", "rfi", "stream", "--state", str(state),
                "import", "--file", str(changed), "--revision",
            ]),
        )
        outputs: dict[str, subprocess.CompletedProcess[str]] = {}
        lines = [
            "$ " + " ".join(setup.args), setup.stdout, setup.stderr,
            f"exit_code: {setup.returncode}", "",
        ]
        for name, arguments in commands:
            result = command(arguments)
            outputs[name] = result
            display = " ".join(arguments)
            if name == "schema":
                schema_file.write_text(result.stdout, encoding="utf-8")
                display += f" > {schema_file}"
            lines.extend((f"$ {display}", result.stdout, result.stderr,
                          f"exit_code: {result.returncode}", ""))
        from rfi.streams import StreamRepository, StreamService

        service = StreamService(StreamRepository(state))
        exported_stdout = outputs["export-stdout"].stdout
        round_trip = service.review_yaml(exported_stdout)
        result = {
            "name": "cli-proof",
            "command": ["sequential rfi stream CLI proof matrix"],
            "exit_code": 0,
            "passed": all(
                outputs[name].returncode == (2 if name == "invalid" else 0)
                for name in outputs
            ) and setup.returncode == 0,
        }
        summary = {
            "result": "PASS" if result["passed"] else "FAIL",
            "help_exposes_schema_validate_import_export": all(
                item in outputs["help"].stdout
                for item in ("schema", "validate", "import", "export")
            ),
            "schema_redirect_is_valid_yaml": (
                yaml.safe_load(schema_file.read_text(encoding="utf-8"))["schema_version"] == 1
            ),
            "valid_exit_code": outputs["validate"].returncode,
            "invalid_exit_code": outputs["invalid"].returncode,
            "invalid_path_on_stderr": "$.stream.input.artifact_schema"
            in outputs["invalid"].stderr,
            "new_import_outcome": json.loads(outputs["import-new"].stdout)["outcome"],
            "derived_import_outcome": json.loads(outputs["import-derived"].stdout)["outcome"],
            "revision_import_outcome": json.loads(outputs["import-revision"].stdout)["outcome"],
            "identical_import_outcome": json.loads(outputs["import-identical"].stdout)[
                "outcome"
            ],
            "stdout_export_equals_file_export": (
                exported_stdout == export_file.read_text(encoding="utf-8")
            ),
            "export_round_trip_valid": round_trip.valid,
            "stream_run_count_after_imports": len(
                service.repository.rows("SELECT * FROM artifact_stream_runs")
            ),
            "history_count": len(service.history("linux-block-storage")),
            "schema_stdout_stderr_empty": outputs["schema"].stderr == "",
            "export_stdout_stderr_empty": outputs["export-stdout"].stderr == "",
        }
        result["passed"] = result["passed"] and all((
            summary["help_exposes_schema_validate_import_export"],
            summary["schema_redirect_is_valid_yaml"],
            summary["invalid_path_on_stderr"],
            summary["stdout_export_equals_file_export"],
            summary["export_round_trip_valid"],
            summary["stream_run_count_after_imports"] == 0,
            summary["history_count"] == 2,
            summary["identical_import_outcome"] == "already_current",
            summary["schema_stdout_stderr_empty"],
            summary["export_stdout_stderr_empty"],
        ))
        result["exit_code"] = 0 if result["passed"] else 1
        summary["result"] = "PASS" if result["passed"] else "FAIL"
        review.write("validation/cli-proof.txt", "\n".join(lines))
        review.write("evidence/cli-proof.json", json.dumps(summary, indent=2) + "\n")
        review.write("evidence/schema-template.yaml", schema_file.read_text(encoding="utf-8"))
        review.write("evidence/canonical-export.yaml", exported_stdout)
        return result


def isolated_validation() -> dict[str, Any]:
    """Run focused and policy gates in a Git/state/artifact/credential-free source copy."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task026-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [str(PYTHON), "-m", "unittest", "tests.test_task026", "tests.test_task025",
             "tests.test_task025_hardening", "-v"],
            [str(PYTHON), "scripts/task026_streams.py", "fixture-proof"],
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
        for arguments in commands:
            result = command(arguments, destination)
            output.extend((f"$ {' '.join(arguments)}", result.stdout, result.stderr,
                           f"exit_code: {result.returncode}", ""))
            passed = passed and result.returncode == 0
    review.write("validation/isolated-copied-tree.txt", "\n".join(output))
    return {
        "name": "isolated-copied-tree",
        "command": ["copied-tree focused TASK-025/026 and policy matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def extract_json(name: str) -> dict[str, Any]:
    """Extract the JSON object from one retained command transcript."""
    content = (PACKAGE / f"validation/{name}.txt").read_text(encoding="utf-8")
    start = content.find("{\n")
    end = content.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError(f"JSON proof absent from {name}")
    return json.loads(content[start:end])


def durable_records(branch: str, head: str) -> None:
    """Create the human and machine review records required by the task ticket."""
    copies = {
        "task-ticket.md": "tasks/TASK-026-usable-stream-configuration-and-canonical-yaml.md",
        "canonical-yaml-specification.md": "docs/stream-configuration-and-yaml.md",
        "stream-architecture.md": "docs/revisioned-artifact-streams.md",
        "architecture-decision.md": "docs/decisions/0021-canonical-stream-definition-yaml.md",
        "operator-cli-documentation.md": "docs/application-cli.md",
        "examples/external-stream.yaml": "fixtures/streams/task026-external.yaml",
        "examples/derived-stream.yaml": "fixtures/streams/task026-derived.yaml",
    }
    for destination, source in copies.items():
        target = PACKAGE / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, target)
    if not BROWSER_PROOF.is_file():
        raise RuntimeError("required real-browser proof is absent")
    (PACKAGE / "evidence").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BROWSER_PROOF, PACKAGE / "evidence/real-browser-proof.json")
    records = {
        "completion-report.md": (
            "TASK-026 delivers the five-section Streams workflow, canonical YAML version 1, "
            "browser file/paste import and saved-revision export, semantic review, and `rfi "
            "stream schema|validate|import|export`. Identical normalized import returns "
            "`already_current` without a revision. Existing identities require explicit revision "
            "mode and optimistic immutable revision creation. Browser, CLI, YAML, preview, save, "
            "and execution normalize and validate in `StreamService`. Governed sources remain "
            "the only transport authority. No intentional deviations from the ticket remain."
        ),
        "architectural-status-summary.md": (
            "Stream definition/revision authority — Complete (SQLite plus immutable revisions).\n\n"
            "Canonical definition normalization and YAML version 1 adapter — Complete.\n\n"
            "Progressive browser configuration workflow — Complete.\n\n"
            "CLI schema, validate, import, and export — Complete.\n\n"
            "Schema capability registry, typed policy, expansion, DAG, preview, publication, "
            "membership, lineage, rebuild, and artifact retention — Complete and preserved from "
            "TASK-025.\n\nGoverned source transport and secret boundary — Complete and "
            "unchanged.\n\n"
            "Limitations — YAML comments/formatting, bulk packages, scheduling, durable Lore "
            "cursor, arbitrary scripts, and plugins remain deferred.\n\nNext architectural "
            "milestone — "
            "return to evidence-driven selection of the next roadmap milestone; no stream "
            "architecture replacement is indicated."
        ),
        "ui-before-after-summary.md": (
            "Before: one dense two-column form mixed identity, topology, low-level predicate rows, "
            "expansion, bounds, save, and execution. After: numbered Identity → Input → Selection "
            "→ Context and limits → Review and save sections; common filters lead, Advanced "
            "policy is disclosed on demand, source/upstream labels are operator-readable, YAML is "
            "staged, semantic changes are shown, and saved execution is behaviorally separate."
        ),
        "cli-command-reference.md": (
            "`rfi stream schema`; `rfi stream --state PATH validate --file YAML`; `rfi stream "
            "--state PATH import --file YAML --new`; `rfi stream --state PATH import --file YAML "
            "--revision [--expected-revision ID]`; `rfi stream --state PATH export --stream ID "
            "[--revision-id ID] [--output YAML]`. Export stdout is YAML-only; diagnostics use "
            "stderr and failures return 2."
        ),
        "round-trip-proof.md": (
            "Fixture proof and focused tests demonstrate external and derived export → safe parse "
            "→ normalize equivalence, stable SHA-256, trailing newline, browser-to-CLI contract "
            "equivalence, CLI-to-browser rendering, and formatting-only semantic no-op behavior."
        ),
        "negative-architectural-proofs.md": (
            "Focused tests and fixture proof reject unknown versions/fields, duplicate YAML keys "
            "and identities, unsupported schemas/fields/operators/expansions, invalid bounds, "
            "missing sources/upstreams, self-reference, indirect cycles, and secret/transport or "
            "executable fields with YAML paths. Validation/preview create no stream revision; "
            "import creates no run, artifact bytes, or source-profile change; existing history is "
            "preserved; publication remains atomic and DAG validation is not bypassed."
        ),
        "migration-statement.md": (
            "No SQLite schema migration is required. Optional notes use the existing revision "
            "canonical JSON payload and default to empty for TASK-025 revisions. Repository schema "
            "version remains 4. YAML `schema_version: 1` is an interchange version, not a SQLite "
            "schema version."
        ),
        "known-limitations-and-deferred-capabilities.md": (
            "Comments and original YAML formatting do not round-trip. Import is one document, not "
            "a bulk package. Legacy JSON preview/save CLI operations remain for compatibility. No "
            "automatic acquisition/run, scheduler, production polling cursor, arbitrary SQL, "
            "Python, JavaScript, JSON path, workflow engine, plugin, or source-profile mutation is "
            "introduced."
        ),
        "repository-status-summary.md": (
            f"Branch: `{branch}`. HEAD remains `{head}`; no commit was created. TASK-026 files are "
            "intentionally unstaged and uncommitted for independent review. Generated review "
            "artifacts are ignored product output."
        ),
    }
    for name, body in records.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")


def main() -> int:
    """Run verification, write durable records, archive them, and report exact integrity."""
    if PACKAGE.exists() or ZIP_PATH.exists() or ZIP_HASH.exists():
        raise RuntimeError("TASK-026 review output already exists; nothing was removed")
    PACKAGE.mkdir(parents=True)
    validations = [
        review.run("focused-task026", [
            str(PYTHON), "-m", "unittest", "tests.test_task026", "tests.test_task025",
            "tests.test_task025_hardening", "-v",
        ]),
        review.run("fixture-round-trip-proof", [
            str(PYTHON), "scripts/task026_streams.py", "fixture-proof",
        ]),
        cli_proof(),
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("lint", [str(PYTHON), "scripts/quality.py", "lint"]),
        review.run("format", [str(PYTHON), "scripts/quality.py", "format"]),
        review.run("typecheck", [str(PYTHON), "scripts/quality.py", "typecheck"]),
        review.run("documentation", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("design-baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        review.run("source-archive-integrity", [
            str(PYTHON), "scripts/build_source_archive.py",
        ]),
        review.run("full-repository-validation", ["make", "validate"]),
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
        "repository/untracked.txt", review.git("ls-files", "--others", "--exclude-standard")
    )
    review.write("repository/cumulative-task.patch", review.complete_patch())
    review.write("repository/repository-tree.txt", review.repository_tree())
    review.write(
        "repository/changed-files-with-rationale.json",
        json.dumps(
            {path: "TASK-026 implementation, test, proof, documentation, or task ticket"
             for path in files},
            indent=2,
        ) + "\n",
    )
    durable_records(branch, head)
    fixture = extract_json("fixture-round-trip-proof")
    review.write("evidence/round-trip-fixture-proof.json", json.dumps(fixture, indent=2) + "\n")
    scan = review.sensitive_scan()
    failures = [item["name"] for item in validations if not item["passed"]]
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
        "browser_proof": json.loads(BROWSER_PROOF.read_text(encoding="utf-8")),
        "sensitive_output_scan": scan,
        "migration": "none; SQLite schema remains version 4",
        "generated_artifacts_excluded_from_product_diff": True,
    }
    review.write("verification-summary.json", json.dumps(metadata, indent=2) + "\n")
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    archive = review.archive(metadata)
    print(json.dumps({
        "result": "PASS",
        "review_directory": str(PACKAGE.relative_to(ROOT)),
        "review_zip": str(ZIP_PATH.relative_to(ROOT)),
        "checksum_file": str(ZIP_HASH.relative_to(ROOT)),
        "zip": archive,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
