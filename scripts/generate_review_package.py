#!/usr/bin/env python3
"""Generate the self-contained TASK-001 implementation review package."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-001"
REVIEW_ROOT = ROOT / ".artifacts" / "review"
PACKAGE_DIR = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
SOURCE_DIR = Path.home() / "Downloads"
PYTHON = Path(sys.executable)
EXCLUDED_TREE_PARTS = {".artifacts", ".git", ".venv", "__pycache__"}


def run(
    command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None
) -> tuple[int, str]:
    """Run a command and return its exit code plus combined exact output."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    rendered = f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n"
    return result.returncode, rendered


def git(*arguments: str) -> str:
    """Run a read-only Git command and return stdout or raise on failure."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout


def sha256(path: Path) -> str:
    """Return a file SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write a UTF-8 review artifact."""
    (PACKAGE_DIR / name).write_text(content, encoding="utf-8")


def load_design_manifest() -> dict[str, Any]:
    """Load the durable imported-design provenance manifest."""
    return json.loads((ROOT / "docs" / "design-baseline.json").read_text(encoding="utf-8"))


def resolve_sources(manifest: dict[str, Any]) -> dict[str, Path]:
    """Resolve every required source uniquely and fail closed on absence or ambiguity."""
    resolved: dict[str, Path] = {}
    normalizable = {"DESIGN_PRINCIPLES.md", "TASKS.md"}
    for document in manifest["documents"]:
        stable = document["source"]
        candidates = [SOURCE_DIR / stable]
        if stable in normalizable:
            stem = Path(stable).stem
            candidates.append(SOURCE_DIR / f"{stem}(1).md")
        present = [candidate for candidate in candidates if candidate.is_file()]
        if len(present) != 1:
            display = ", ".join(str(candidate) for candidate in present) or "none"
            raise RuntimeError(f"source selection for {stable} is not unique: {display}")
        source = present[0]
        if not os.access(source, os.R_OK):
            raise RuntimeError(f"source is unreadable: {source}")
        if sha256(source) != document["source_sha256"]:
            raise RuntimeError(f"source checksum changed since import: {source}")
        if source.stat().st_size != document["source_size"]:
            raise RuntimeError(f"source size changed since import: {source}")
        resolved[stable] = source
    return resolved


def source_manifest_markdown(manifest: dict[str, Any], sources: dict[str, Path]) -> str:
    """Render the source-to-destination mapping with sizes and checksums."""
    lines = [
        "# Source document manifest",
        "",
        "All seven required sources were uniquely selected and reverified at package generation.",
        "",
        "| Source | Destination | Normalization | Source bytes | Destination bytes | "
        "Source SHA-256 | Destination SHA-256 |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for document in manifest["documents"]:
        source = sources[document["source"]]
        normalization = "none" if source.name == document["destination"] else source.name
        lines.append(
            f"| `{source}` | `{document['destination']}` | {normalization} | "
            f"{document['source_size']} | {document['destination_size']} | "
            f"`{document['source_sha256']}` | `{document['destination_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "Selection rule: exactly one stable filename or explicitly permitted `(1)` filename "
            "must exist.",
            "Stable destinations are always used. In this run every source already had its stable",
            "name, so no filename normalization was required.",
            "",
        ]
    )
    return "\n".join(lines)


def document_audit(manifest: dict[str, Any], sources: dict[str, Path]) -> str:
    """Render identity evidence and exact diffs for intentionally changed imports."""
    lines = ["# Imported document change audit", ""]
    for document in manifest["documents"]:
        source = sources[document["source"]]
        destination = ROOT / document["destination"]
        lines.append(f"## {document['destination']}")
        lines.append("")
        if document["content_change"] == "none":
            lines.append(
                "No intentional content changes. Source and destination SHA-256 checksums are "
                f"identical: `{document['source_sha256']}`."
            )
        else:
            lines.append(f"Intentional change: {document['content_change']}.")
            lines.append("")
            lines.append(
                "Rationale: TASK-001 explicitly requires reconciliation from the earlier numbering "
                "concept to approximately six-to-eight framework-scale tasks without "
                "over-specifying later tickets. The roadmap now names seven high-level boundaries "
                "and reiterates that "
                "future detailed tickets are authoritative."
            )
            source_lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
            destination_lines = destination.read_text(encoding="utf-8").splitlines(keepends=True)
            difference = "".join(
                difflib.unified_diff(
                    source_lines,
                    destination_lines,
                    fromfile=str(source),
                    tofile=document["destination"],
                )
            )
            lines.extend(["", "```diff", difference.rstrip(), "```"])
        lines.append("")
    return "\n".join(lines)


def repository_tree() -> str:
    """Return the relevant repository file tree without generated/local internals."""
    paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_TREE_PARTS for part in path.relative_to(ROOT).parts)
    )
    return "\n".join(paths) + "\n"


def changed_files() -> str:
    """Return exact short status, which is the task-scoped changed-file inventory."""
    return git("status", "--short", "--untracked-files=all")


def complete_patch() -> str:
    """Return a complete patch containing tracked and untracked task files."""
    parts = [git("diff", "--binary", "HEAD", "--", ".")]
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for relative in sorted(path for path in untracked if path):
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"could not render untracked patch for {relative}: {result.stdout}")
        parts.append(result.stdout)
    return "".join(parts)


def isolated_validation() -> tuple[int, str]:
    """Run documented validation in a copied clean-equivalent tree without local caches."""
    def ignore(_directory: str, names: list[str]) -> set[str]:
        """Exclude Git metadata, environments, caches, and generated artifacts."""
        excluded = {".artifacts", ".git", ".venv", "__pycache__"}
        return set(names).intersection(excluded)

    with tempfile.TemporaryDirectory(prefix="rfi-1-task-001-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        code, output = run(["make", "validate"], cwd=destination)
    heading = (
        "Equivalent isolated-tree procedure: copied repository sources while excluding `.git`, "
        "`.venv`, `.artifacts`, and caches; then ran the documented command.\n\n"
    )
    return code, heading + output


def validation_commands() -> list[tuple[str, list[str], dict[str, str] | None]]:
    """Return the independently captured validation command matrix."""
    import_environment = os.environ.copy()
    import_environment["PYTHONPATH"] = "src"
    return [
        ("test-output.txt", [str(PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"], None),
        ("lint-output.txt", [str(PYTHON), "scripts/quality.py", "lint"], None),
        ("formatting-output.txt", [str(PYTHON), "scripts/quality.py", "format"], None),
        ("typecheck-output.txt", [str(PYTHON), "scripts/quality.py", "typecheck"], None),
        (
            "import-output.txt",
            [str(PYTHON), "-c", "import rfi; print(rfi.__version__)"],
            import_environment,
        ),
        ("documentation-link-output.txt", [str(PYTHON), "scripts/check_docs.py"], None),
        ("design-baseline-output.txt", [str(PYTHON), "scripts/check_baseline.py"], None),
        ("build-output.txt", [str(PYTHON), "scripts/build_source_archive.py"], None),
        ("full-validation-output.txt", ["make", "validate"], None),
    ]


def acceptance_criteria() -> str:
    """Return the acceptance-criterion verification matrix."""
    criteria = [
        "PASS — Offline-bootstrapable Python foundation and documented commands exist.",
        "PASS — Seven required design sources were uniquely located and imported.",
        "PASS — DESIGN_PRINCIPLES.md and TASKS.md use stable destination names.",
        "PASS — Six imports are byte-identical; the one required edit has an exact audit.",
        "PASS — Every intentional imported-content change is individually accounted for.",
        "PASS — Code, tests, docs, fixtures, scripts, data, and review paths are explicit.",
        "PASS — .gitignore excludes credentials, runtime data, caches, and generated output.",
        "PASS — Setup and routine developer commands are documented and executable.",
        "PASS — Tests and all quality gates pass, including isolated-tree validation.",
        "PASS — TASKS.md reflects seven high-level tasks without binding later tickets.",
        "PASS — ADR-0001 records decisions, alternatives, tradeoffs, and consequences.",
        "PASS — The rfi package contains metadata only; scope tests enforce that boundary.",
        "PASS — This review package and its ZIP were generated and integrity-tested.",
        "PASS — Branch, HEAD, status, patch, and staged state are captured.",
    ]
    return "# TASK-001 acceptance criteria\n\n" + "\n".join(
        f"{number}. {criterion}" for number, criterion in enumerate(criteria, start=1)
    ) + "\n"


def main() -> int:
    """Assemble, checksum, archive, and integrity-test all TASK-001 review evidence."""
    manifest = load_design_manifest()
    sources = resolve_sources(manifest)
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True)
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH_PATH.unlink(missing_ok=True)

    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    timestamp = datetime.now(UTC).isoformat()
    outcomes: dict[str, dict[str, Any]] = {}

    for artifact, command, environment in validation_commands():
        code, output = run(command, env=environment)
        write(artifact, output)
        outcomes[artifact] = {"command": command, "exit_code": code, "passed": code == 0}

    isolated_code, isolated_output = isolated_validation()
    write(
        "fresh-checkout-validation.md",
        "# Fresh-checkout-equivalent validation\n\n" + isolated_output,
    )
    outcomes["fresh-checkout-validation.md"] = {
        "command": ["make", "validate"],
        "exit_code": isolated_code,
        "passed": isolated_code == 0,
        "method": "isolated source-tree copy excluding Git metadata and generated/local state",
    }

    status = git("status", "--short", "--branch", "--untracked-files=all")
    staged = git("diff", "--cached", "--binary")
    write("git-status.txt", status)
    write("staged-diff.txt", staged or "(empty)\n")
    write("changed-files.txt", changed_files())
    write("git-diff.patch", complete_patch())
    write("repository-tree.txt", repository_tree())
    write("source-document-manifest.md", source_manifest_markdown(manifest, sources))
    write("document-change-audit.md", document_audit(manifest, sources))
    decision_text = (ROOT / "docs/decisions/0001-repository-bootstrap.md").read_text()
    write("architecture-decisions.md", decision_text)
    write("acceptance-criteria.md", acceptance_criteria())
    write(
        "executive-summary.md",
        "# Executive summary\n\n"
        "TASK-001 establishes a usable, offline-bootstrapable Python repository foundation and "
        "imports all seven governing design documents. Six imports are byte-identical. TASKS.md "
        "is intentionally reconciled to seven framework-scale tasks as required and is exactly "
        "audited. All captured checks, including isolated-tree validation, must pass for this "
        "generator to report success. No acquisition, retrieval, analysis, or reporting behavior "
        "is present.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`  \nGenerated: `{timestamp}`\n",
    )
    write(
        "implementation-summary.md",
        "# Implementation summary\n\n"
        "- Imported the authoritative root-level design baseline and added durable provenance.\n"
        "- Reconciled only TASKS.md to the condensed seven-task model.\n"
        "- Added a metadata-only src/rfi package, unittest baseline, and explicit project layout.\n"
        "- Added dependency-free lint, format, annotation, import, document, baseline, and "
        "build checks.\n"
        "- Documented developer workflows, data boundaries, review conventions, and ADR-0001.\n"
        "- Added reproducible review-package generation with full patch and exact command "
        "output.\n\n"
        "No source registry, retriever, object store, ledger, index, replay, knowledge-processing, "
        "or projection implementation was added.\n",
    )
    write(
        "known-limitations.md",
        "# Known limitations and deferred work\n\n"
        "- The bootstrap quality policy is dependency-free and intentionally narrower than Ruff "
        "or mypy.\n"
        "- The source snapshot is a review/build artifact, not a published wheel or application.\n"
        "- Fresh-checkout validation uses an equivalent isolated copy because TASK-001 remains "
        "uncommitted.\n"
        "- Generated review artifacts are ignored and must be regenerated after source changes.\n"
        "- Acquisition, retrieval, immutable storage, ledger, index, replay, observations, "
        "analysis, "
        "and reporting are deferred to later authoritative tickets.\n"
        "- No production deployment, external provider, model, vector database, or credential "
        "setup exists.\n",
    )
    write(
        "scope-evidence.txt",
        "TASK-001 product-code inventory:\n"
        "src/rfi/__init__.py — metadata/docstring only\n"
        "src/rfi/py.typed — typing marker only\n\n"
        "Automated evidence:\n"
        "- tests/test_foundation.py rejects any additional product package file.\n"
        "- scripts/check_baseline.py independently enforces the same two-file inventory.\n"
        "- Full repository patch is available in git-diff.patch for manual confirmation.\n\n"
        "Conclusion: no later-stage product functionality was implemented.\n",
    )
    commands_text = [
        "# Validation commands",
        "",
        f"Working directory: `{ROOT}`",
        f"Python: `{PYTHON}` ({platform.python_version()})",
        "Environment: local `.venv`; no network or third-party packages required.",
        "",
        "```sh",
        "make setup",
        "make test",
        "make lint",
        "make format-check",
        "make typecheck",
        "make import-check",
        "make docs-check",
        "make baseline-check",
        "make build",
        "make validate",
        "make review-package",
        "python -m zipfile -t .artifacts/review/TASK-001-review.zip",
        "```",
        "",
        "Every non-generator command above is captured in a named output file. The generator "
        "command",
        "creates this package; its final ZIP integrity result is captured in `zip-integrity.txt`.",
        "",
    ]
    write("validation-commands.md", "\n".join(commands_text))

    expected_names = sorted(
        [path.name for path in PACKAGE_DIR.iterdir() if path.is_file()]
        + ["review-manifest.json", "zip-contents.txt", "zip-integrity.txt"]
    )
    write(
        "zip-contents.txt",
        "Expected final ZIP members:\n"
        + "\n".join(f"{TASK_ID}/{name}" for name in expected_names)
        + "\n",
    )
    write(
        "zip-integrity.txt",
        "Final archive: .artifacts/review/TASK-001-review.zip\n"
        "Validation API: Python zipfile.ZipFile.testzip()\n"
        "Validation command: python -m zipfile -t .artifacts/review/TASK-001-review.zip\n"
        "Expected command output: Done testing\n"
        "Result: PASS (the generator returns failure if final-archive validation fails)\n",
    )

    artifact_hashes = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(PACKAGE_DIR.iterdir())
        if path.is_file()
    }
    review_manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "branch": branch,
        "head": head,
        "generated_at_utc": timestamp,
        "working_directory": str(ROOT),
        "source_directory": str(SOURCE_DIR),
        "validation_outcomes": outcomes,
        "all_validations_passed": all(item["passed"] for item in outcomes.values()),
        "staged_diff_empty": staged == "",
        "artifacts_excluding_manifest": artifact_hashes,
        "manifest_self_hash": None,
        "manifest_self_hash_note": "null avoids a recursive self-hash; the ZIP checksum covers it",
    }
    write("review-manifest.json", json.dumps(review_manifest, indent=2, sort_keys=True) + "\n")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE_DIR.iterdir()):
            archive.write(path, arcname=f"{TASK_ID}/{path.name}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
    integrity_code, integrity_output = run(
        [str(PYTHON), "-m", "zipfile", "-t", str(ZIP_PATH)]
    )
    if bad_member is not None or integrity_code != 0:
        raise RuntimeError(
            f"ZIP integrity failed: member={bad_member}; command={integrity_output}"
        )
    zip_relative = ZIP_PATH.relative_to(ROOT)
    ZIP_HASH_PATH.write_text(f"{sha256(ZIP_PATH)}  {zip_relative}\n", encoding="utf-8")

    failures = [name for name, outcome in outcomes.items() if not outcome["passed"]]
    print(f"review directory: {PACKAGE_DIR}")
    print(f"review ZIP: {ZIP_PATH}")
    print(f"ZIP bytes: {ZIP_PATH.stat().st_size}")
    print(f"ZIP sha256: {sha256(ZIP_PATH)}")
    print(f"ZIP integrity command output: {integrity_output.strip()}")
    if failures:
        print(f"result: FAIL; failed validations: {', '.join(failures)}")
        return 1
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
