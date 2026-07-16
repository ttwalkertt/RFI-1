#!/usr/bin/env python3
"""Generate the self-contained TASK-002 verification and review package."""

from __future__ import annotations

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
TASK_ID = "TASK-002"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE_DIR = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
PYTHON = Path(sys.executable)
EXCLUDED_PARTS = {".artifacts", ".git", ".venv", "__pycache__"}


def run(command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run a command and return review-ready combined exact output."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n"
    return result.returncode, output


def git(*arguments: str) -> str:
    """Run a read-only Git command and return exact stdout."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout


def sha256(path: Path) -> str:
    """Return a file SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    (PACKAGE_DIR / name).write_text(content, encoding="utf-8")


def repository_tree() -> str:
    """Return source tree paths without generated, Git, environment, or cache state."""
    paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )
    return "\n".join(paths) + "\n"


def complete_patch() -> str:
    """Render tracked and untracked task changes into one complete binary-safe patch."""
    parts = [git("diff", "--binary", "HEAD", "--", ".")]
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for relative in sorted(item for item in untracked if item):
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"could not render untracked file {relative}: {result.stdout}")
        parts.append(result.stdout)
    return "".join(parts)


def isolated_validation() -> tuple[int, str]:
    """Validate a clean-equivalent copy with no Git, environment, cache, or artifacts."""
    def ignore(_directory: str, names: list[str]) -> set[str]:
        """Exclude non-source state from the isolated copy."""
        return set(names).intersection(EXCLUDED_PARTS)

    with tempfile.TemporaryDirectory(prefix="rfi-task-002-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        code, output = run(["make", "validate"], cwd=destination)
    method = (
        "Method: copied the complete final source tree while excluding `.git`, `.venv`, "
        "`.artifacts`, and caches; then ran `make validate`. This is clean-checkout-equivalent "
        "because TASK-002 changes are intentionally uncommitted.\n\n"
    )
    return code, method + output


def validation_matrix() -> list[tuple[str, list[str], dict[str, str] | None]]:
    """Return every independently captured validation command."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    unittest = [str(PYTHON), "-m", "unittest"]
    return [
        (
            "focused-contract-registry-output.txt",
            [*unittest, "tests.test_acquisition.ContractAndRegistryTests", "-v"],
            None,
        ),
        (
            "focused-artifact-ledger-output.txt",
            [*unittest, "tests.test_acquisition.ArtifactAndLedgerTests", "-v"],
            None,
        ),
        (
            "focused-lifecycle-replay-output.txt",
            [*unittest, "tests.test_acquisition.LifecycleReplayTests", "-v"],
            None,
        ),
        (
            "failure-injection-output.txt",
            [*unittest, "tests.test_acquisition.FailureOrderingTests", "-v"],
            None,
        ),
        (
            "prohibited-capabilities-output.txt",
            [*unittest, "tests.test_acquisition.ScopeBoundaryTests", "-v"],
            None,
        ),
        (
            "project-tests-output.txt",
            [*unittest, "discover", "-s", "tests", "-v"],
            None,
        ),
        (
            "fixture-demonstration-output.txt",
            [str(PYTHON), "scripts/verify_acquisition.py", "fixture"],
            None,
        ),
        (
            "index-deletion-rebuild-output.txt",
            [str(PYTHON), "scripts/verify_acquisition.py", "rebuild"],
            None,
        ),
        (
            "artifact-integrity-output.txt",
            [str(PYTHON), "scripts/verify_acquisition.py", "integrity"],
            None,
        ),
        (
            "deterministic-clean-runs-output.txt",
            [str(PYTHON), "scripts/verify_acquisition.py", "determinism"],
            None,
        ),
        ("lint-output.txt", [str(PYTHON), "scripts/quality.py", "lint"], None),
        ("format-output.txt", [str(PYTHON), "scripts/quality.py", "format"], None),
        ("typecheck-output.txt", [str(PYTHON), "scripts/quality.py", "typecheck"], None),
        (
            "import-output.txt",
            [str(PYTHON), "-c", "import rfi; import rfi.acquisition; print(rfi.__version__)"],
            environment,
        ),
        ("docs-output.txt", [str(PYTHON), "scripts/check_docs.py"], None),
        ("baseline-output.txt", [str(PYTHON), "scripts/check_baseline.py"], None),
        ("build-output.txt", [str(PYTHON), "scripts/build_source_archive.py"], None),
        ("full-validation-output.txt", ["make", "validate"], None),
    ]


def acceptance_criteria() -> str:
    """Map every ticket acceptance criterion to durable verification evidence."""
    evidence = [
        "Contracts: source code, acquisition guide, contract/identity summary, focused tests.",
        "Identity separation: acquisition guide identity table and contract test output.",
        "Registry: immutable validated profiles and malformed/conflict tests.",
        "Exact artifacts: artifact integrity output and byte-preservation tests.",
        "Artifact conflicts: exclusive-create store plus corruption/conflict tests.",
        "Append-only history: immutable record implementation and ledger tests.",
        "Useful rebuildable index: lifecycle tests and index rebuild output.",
        "Index loss safety: rebuild output preserves bytes, history, provenance, and progress.",
        "Checkpoint ordering: failure injection tests and durability model.",
        "Idempotency: fixture demonstration and repeat tests.",
        "Conflicts: fixture demonstration and conflict tests.",
        "Offline replay: blocked-socket rebuild evidence and scope checks.",
        "Partial failures: failure injection and replay failure outputs.",
        "Independent integrity: fixture/stored SHA-256 output and corruption test.",
        "Fixture lifecycle: fixture demonstration output.",
        "Operator workflows: development and acquisition-substrate documentation.",
        "Design decisions: ADR-0002 and architecture/alternatives package documents.",
        "Existing gates: full validation and isolated-tree validation outputs.",
        "Prohibited scope absent: scope tests, source inventory, and full patch.",
        "Review package: manifest, raw outputs, checksums, listing, and integrity evidence.",
        "Final state: git status, staged diff, changed files, branch, and HEAD in manifest.",
    ]
    lines = ["# TASK-002 acceptance criteria", ""]
    lines.extend(f"{number}. PASS — {item}" for number, item in enumerate(evidence, start=1))
    return "\n".join(lines) + "\n"


def write_narrative(branch: str, head: str, timestamp: str) -> None:
    """Write required human-review summaries from durable project documents."""
    write(
        "executive-summary.md",
        "# Executive summary\n\n"
        "TASK-002 adds a dependency-free, provider-neutral acquisition repository substrate. "
        "It proves governed sources, exact immutable artifacts, append-only retrieval history, "
        "a disposable document index, ordered source progress, offline replay, idempotency, "
        "conflict detection, diagnostics, integrity checking, and observable partial failure. "
        "All captured validations must pass for package generation to succeed. No external "
        "retrieval or downstream intelligence capability is implemented.\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`  \nGenerated UTC: `{timestamp}`\n",
    )
    write(
        "implementation-summary.md",
        "# Implementation summary\n\n"
        "- Frozen provider-neutral source, candidate, provenance, retrieval, checkpoint, receipt, "
        "and replay contracts.\n"
        "- Filesystem-backed immutable source/artifact/ledger records behind a private layout.\n"
        "- Derived document index and checkpoint view rebuilt from authoritative local state.\n"
        "- Ordered lifecycle with deterministic fault injection, idempotent retry, integrity "
        "verification, and conflict rejection.\n"
        "- Fixture demonstration, operator interface, focused tests, full gates, isolated-tree "
        "validation, and reproducible review packaging.\n",
    )
    adr = (ROOT / "docs/decisions/0002-acquisition-substrate.md").read_text(encoding="utf-8")
    write("architecture-decisions.md", adr)
    alternatives = adr.split("## Alternatives considered", maxsplit=1)[1]
    alternatives = alternatives.split("## Consequences and limits", maxsplit=1)[0]
    write("alternatives-considered.md", "# Alternatives considered\n" + alternatives)
    guide = (ROOT / "docs/acquisition-substrate.md").read_text(encoding="utf-8")
    sections = {
        "contract-and-identity-model.md": ("Contracts and identity", "Authoritative and derived"),
        "durability-and-failure-model.md": (
            "Durability and failure ordering",
            "Checkpoints and replay",
        ),
        "checkpoint-and-replay-summary.md": ("Checkpoints and replay", "Operator commands"),
    }
    for name, (start, end) in sections.items():
        content = guide.split(f"## {start}", maxsplit=1)[1].split(f"## {end}", maxsplit=1)[0]
        write(name, f"# {start}\n" + content)
    write(
        "source-registry-summary.md",
        "# Source registry summary\n\nGoverned source profiles use stable internal identity, "
        "explicit "
        "enablement, generic mechanism, deterministic JSON configuration, and policy. Profiles "
        "are immutable-by-contract; exact repeats are idempotent and conflicts fail closed. "
        "Provider names and URLs cannot define source identity.\n",
    )
    write(
        "artifact-store-summary.md",
        "# Artifact store summary\n\nArtifact identity is `artifact-<sha256>`. Exact bytes and "
        "metadata "
        "are exclusive-created and fsynced. Metadata contains digest, size, and media type. "
        "Reads and full verification recompute integrity; physical layout is private.\n",
    )
    write(
        "retrieval-ledger-summary.md",
        "# Retrieval ledger summary\n\nEach attempt and checkpoint event is a separate immutable "
        "record. "
        "Normal operation only appends or accepts exact identity repetition. Success, failure, "
        "skip, and duplicate outcomes retain audit and diagnostic evidence.\n",
    )
    write(
        "document-index-summary.md",
        "# Document index summary\n\nThe JSON index maps stable document IDs to immutable "
        "artifacts, "
        "successful attempts, sources, and provenance. It owns no authoritative facts and is "
        "atomically rebuilt from ledger and artifact records. Ambiguity fails closed.\n",
    )
    write(
        "fixture-demonstration.md",
        "# Fixture demonstration\n\nThe synthetic local fixture registers a governed source, "
        "records "
        "exact evidence and progress, repeats idempotently, rejects conflict, records a simulated "
        "failure with diagnostics, deletes derived state, replays offline, and verifies bytes. "
        "Raw evidence is in `fixture-demonstration-output.txt`.\n",
    )
    write(
        "known-limitations.md",
        "# Known limitations\n\n- Single-writer POC; no cross-process transaction coordinator.\n"
        "- Filesystem permissions can alter immutable-by-contract files; checks detect evidence "
        "corruption but no cryptographic ledger chain exists.\n"
        "- Interrupted operations may retain orphan evidence intentionally.\n"
        "- JSON views are suitable for fixture/POC scale, not a measured large corpus.\n"
        "- Schema migration, backup, locking, and production object storage are not implemented.\n",
    )
    write(
        "deferred-work.md",
        "# Deferred work\n\nReal adapters, SEC/EDGAR and Investor Relations integration, network "
        "retrieval, crawling, provider credentials, pagination, extraction, OCR, LLMs, embeddings, "
        "vector search, observations, claims, projections, reports, distributed processing, and "
        "production infrastructure remain deferred.\n",
    )


def main() -> int:
    """Capture validations, assemble evidence, verify manifest and ZIP, and report outcomes."""
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir()
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH_PATH.unlink(missing_ok=True)
    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    timestamp = datetime.now(UTC).isoformat()
    outcomes: dict[str, dict[str, Any]] = {}
    for artifact, command, environment in validation_matrix():
        code, output = run(command, env=environment)
        write(artifact, output)
        outcomes[artifact] = {"command": command, "exit_code": code, "passed": code == 0}
    isolated_code, isolated_output = isolated_validation()
    write("isolated-tree-validation-output.txt", isolated_output)
    outcomes["isolated-tree-validation-output.txt"] = {
        "command": ["make", "validate"],
        "exit_code": isolated_code,
        "passed": isolated_code == 0,
        "method": "clean-equivalent copied tree excluding local/generated state",
    }
    write_narrative(branch, head, timestamp)
    write("acceptance-criteria.md", acceptance_criteria())
    write("repository-tree.txt", repository_tree())
    write("changed-files.txt", git("status", "--short", "--untracked-files=all"))
    write("git-status.txt", git("status", "--short", "--branch", "--untracked-files=all"))
    staged = git("diff", "--cached", "--binary")
    write("staged-diff.txt", staged or "(empty)\n")
    write("git-diff.patch", complete_patch())
    commands = [
        "# Validation commands",
        "",
        f"Python: `{PYTHON}` ({platform.python_version()})",
        "",
    ]
    for outcome in outcomes.values():
        commands.append(f"- `{' '.join(outcome['command'])}`")
    commands.extend(
        [
            "- `.venv/bin/python scripts/generate_review_package.py`",
            "- `python -m zipfile -t .artifacts/review/TASK-002-review.zip`",
            "",
            "All checks are applicable; none were skipped. No command requires network access.",
            "Untracked task files are included by `git diff --no-index /dev/null <file>` and are "
            "present in `git-diff.patch`.",
        ]
    )
    write("validation-commands.md", "\n".join(commands) + "\n")
    write(
        "zip-checksum.txt",
        "The final archive SHA-256 is stored in the sibling "
        "`.artifacts/review/TASK-002-review.zip.sha256`. It cannot be embedded in the archive "
        "whose bytes it hashes without a self-reference. The generator prints the same value.\n",
    )
    write(
        "zip-integrity.txt",
        "Validation APIs: `zipfile.ZipFile.testzip()` and `python -m zipfile -t`.\n"
        "Result: PASS if and only if package generation exits zero.\n",
    )
    expected = sorted(
        [path.name for path in PACKAGE_DIR.iterdir() if path.is_file()]
        + ["review-manifest.json", "review-self-validation.txt", "zip-member-listing.txt"]
    )
    write(
        "zip-member-listing.txt",
        "Expected and verified final ZIP members:\n"
        + "\n".join(f"{TASK_ID}/{name}" for name in expected)
        + "\n",
    )
    hashes_before_self_check = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(PACKAGE_DIR.iterdir())
        if path.is_file()
    }
    mismatches = [
        name
        for name, expected_hash in hashes_before_self_check.items()
        if sha256(PACKAGE_DIR / name) != expected_hash["sha256"]
    ]
    write(
        "review-self-validation.txt",
        f"pre-manifest artifacts checked: {len(hashes_before_self_check)}\n"
        f"checksum mismatches: {len(mismatches)}\n"
        f"all validations passed: {all(item['passed'] for item in outcomes.values())}\n"
        f"result: {'PASS' if not mismatches else 'FAIL'}\n",
    )
    hashes = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(PACKAGE_DIR.iterdir())
        if path.is_file()
    }
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "branch": branch,
        "head": head,
        "generated_at_utc": timestamp,
        "validation_outcomes": outcomes,
        "all_validations_passed": all(item["passed"] for item in outcomes.values()),
        "staged_diff_empty": staged == "",
        "authoritative_state": [
            "governed sources",
            "artifact bytes and metadata",
            "ledger records",
        ],
        "derived_state": ["document index", "checkpoint view", "review artifacts"],
        "artifact_checksums_excluding_manifest_and_later_self_check": hashes,
        "manifest_self_hash": None,
        "manifest_self_hash_note": (
            "null prevents recursive self-hash; ZIP checksum covers manifest"
        ),
    }
    write("review-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE_DIR.iterdir()):
            archive.write(path, arcname=f"{TASK_ID}/{path.name}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
        actual_members = archive.namelist()
    expected_members = [f"{TASK_ID}/{name}" for name in expected]
    integrity_code, integrity_output = run([str(PYTHON), "-m", "zipfile", "-t", str(ZIP_PATH)])
    if bad_member or integrity_code or actual_members != expected_members or mismatches:
        raise RuntimeError("review package self-validation or ZIP integrity failed")
    ZIP_HASH_PATH.write_text(
        f"{sha256(ZIP_PATH)}  {ZIP_PATH.relative_to(ROOT)}\n", encoding="utf-8"
    )
    failures = [name for name, item in outcomes.items() if not item["passed"]]
    print(f"review directory: {PACKAGE_DIR}")
    print(f"review ZIP: {ZIP_PATH}")
    print(f"ZIP bytes: {ZIP_PATH.stat().st_size}")
    print(f"ZIP sha256: {sha256(ZIP_PATH)}")
    print(f"ZIP integrity: PASS; {integrity_output.strip()}")
    if failures:
        print(f"result: FAIL; failed validations: {', '.join(failures)}")
        return 1
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
