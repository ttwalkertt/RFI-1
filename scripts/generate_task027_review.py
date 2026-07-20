#!/usr/bin/env python3
"""Generate and verify the complete TASK-027 independent review package."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task018_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-027"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
PYTHON = Path(sys.executable)
BROWSER_INPUT = ROOT / ".artifacts/review-input/TASK-027"

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def copy(relative: str, source: str) -> None:
    """Copy one repository source into the self-contained package."""
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / source, target)


def extract_json(transcript: str) -> dict[str, Any]:
    """Extract one JSON object from a retained command transcript."""
    content = (PACKAGE / f"validation/{transcript}.txt").read_text(encoding="utf-8")
    start = content.find("{\n")
    end = content.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError(f"JSON proof absent from {transcript}")
    return json.loads(content[start:end])


def write_records(branch: str, head: str, base: str) -> dict[str, Any]:
    """Write architecture, design, browser, workflow, and usability records."""
    copies = {
        "task-ticket.md": "tasks/TASK-027-non-modal-operator-help-system-and-workflow-guide.md",
        "canonical/operator-guide.md": "docs/operator-guide.md",
        "canonical/help-topic-registry.py": "src/rfi/admin/help.py",
        "reference/application-cli.md": "docs/application-cli.md",
        "reference/stream-configuration-and-yaml.md": (
            "docs/stream-configuration-and-yaml.md"
        ),
        "reference/revisioned-artifact-streams.md": "docs/revisioned-artifact-streams.md",
        "reference/pull-workflow.md": "docs/pull-workflow.md",
        "reference/sqlite-repository.md": "docs/sqlite-structured-state-repository.md",
    }
    for destination, source in copies.items():
        copy(destination, source)
    browser_proof_path = BROWSER_INPUT / "browser-proof.json"
    if not browser_proof_path.is_file():
        raise RuntimeError("required TASK-027 real-browser proof is absent")
    browser_proof = json.loads(browser_proof_path.read_text(encoding="utf-8"))
    if not all(browser_proof["checks"].values()):
        raise RuntimeError("TASK-027 browser proof contains a failed check")
    for name in browser_proof["screenshots"]:
        source = BROWSER_INPUT / name
        if not source.is_file() or source.stat().st_size == 0:
            raise RuntimeError(f"required browser screenshot is absent: {name}")
        target = PACKAGE / "browser" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(browser_proof_path, PACKAGE / "browser/browser-proof.json")
    workflow = extract_json("workflow-proof")
    review.write("evidence/workflow-proof.json", json.dumps(workflow, indent=2) + "\n")
    review.write(
        "implementation-summary.md",
        "# Implementation summary\n\n"
        "TASK-027 adds one canonical Markdown operator guide, a deterministic safe local renderer, "
        "an explicit stable topic registry and complete major-page mapping, `/help` and "
        "`/help/{topic}` routes on the existing administration server, and a shared Help link "
        "inserted by the authoritative page composer. The link uses the ordinary named target "
        "`rfi-operator-help`; it neither submits nor navigates the administration page. Unknown "
        "topics return a local 404 Help page with complete contents and an actionable notice.\n\n"
        f"Branch: `{branch}`  \nBase: `{base}`  \nHEAD: `{head}`\n",
    )
    review.write(
        "design-decisions-and-scope.md",
        "# Design decisions and scope\n\n"
        "The canonical source is `docs/operator-guide.md`. Stable `help-topic` markers separate "
        "link identity from display headings. `PAGE_HELP_TOPICS` is the completeness contract for "
        "the seven implemented administration pages. Server-side rendering uses a deliberately "
        "small escaped Markdown subset and no external service, JavaScript dependency, or network "
        "asset. The full manual is rendered on every topic route so browser Find and printing "
        "work. Repository verification, backup, and restore remain truthful CLI workflows; no "
        "speculative "
        "repository-administration page was invented. No modal, overlay, onboarding tour, chatbot, "
        "or broad navigation redesign was introduced.\n",
    )
    review.write(
        "browser/browser-verification.md",
        "# Browser-level verification\n\n"
        "A real local administration server was opened at `127.0.0.1:8877`. In Streams, the "
        "operator entered an unsaved name, description, and keywords. Context Help opened tab 2 "
        "at `/help/streams#streams` while the main editor remained tab 1. The operator then edited "
        "Authors in the original tab; all earlier values remained. Reinvoking Help kept tab IDs "
        "1 and 2 and retargeted tab 2. Related navigation reached Stream validation and preview. "
        "An invalid topic displayed the safe local notice and contents. Exact values, URLs, tab "
        "IDs, topic viewport positions, checks, and screenshot names are in "
        "`browser-proof.json`.\n",
    )
    review.write(
        "workflow/workflow-verification.md",
        "# Workflow proof\n\n"
        "`validation/workflow-proof.txt` executes the guide's acquisition sequence through firm "
        "and profile publication, readiness/attemptability, Pull Workflow, durable result, and "
        "retained artifact inspection. It executes YAML review and bounded preview without "
        "persistence, intentional import, semantic revision, saved stream execution, five durable "
        "memberships with lineage, and canonical export round trip. It identifies active state, "
        "verifies, creates a checksummed backup, restores only to fresh state, reverifies, "
        "reopens, "
        "and confirms repository identity preservation. No guide/behavior discrepancy remained.\n",
    )
    review.write(
        "usability-findings.md",
        "# Usability findings and disposition\n\n"
        "1. Deep-link scrolling initially used smooth movement across the complete manual and "
        "could leave a topic heading behind the sticky header. Corrected in scope with immediate "
        "anchor jumps and `scroll-margin-top`; the browser proof records the heading at about 105 "
        "pixels.\n\n"
        "2. Wrapped Markdown list items initially rendered continuation text outside the list "
        "item. Corrected in the deterministic renderer so procedures remain coherent.\n\n"
        "3. Repository protection is CLI-only. This is accurately documented and not treated as "
        "a missing Help mapping because no repository administration browser page exists. A future "
        "repository-health UI may be considered separately if operating evidence warrants it.\n",
    )
    review.write(
        "known-limitations.md",
        "# Known limitations\n\n"
        "RFI-1 requests an ordinary named browsing context. Browser policy controls popup "
        "handling, "
        "tab-versus-window presentation, monitor placement, and whether a named context is reused. "
        "The verified browser reused one separate tab. Browser Find supplies search; there is no "
        "custom full-text index. The local server remains unauthenticated and single-operator. "
        "The repository guide is loaded from the checked-out source tree used by this local "
        "application; no external or installed documentation service is involved.\n",
    )
    review.write(
        "architectural-status-summary.md",
        "# Architectural Status Summary\n\n"
        "- Operator help content authority — **Complete**. One repository-owned canonical guide "
        "covers current pages, workflows, state semantics, recovery, CLI, and glossary.\n"
        "- Local Help presentation — **Complete**. Existing admin server renders safe, printable, "
        "browser-searchable Help without network access or a second process.\n"
        "- Context mapping and navigation — **Complete**. Seven implemented major pages map "
        "through "
        "one explicit registry to unique stable topics and related links.\n"
        "- Non-modal browser interaction — **Complete with browser-controlled placement**. A named "
        "target preserves main-page interaction and drafts; browser policy remains authoritative.\n"
        "- Repository/acquisition/stream/YAML protection workflows — **Complete and verified** "
        "against current public contracts.\n"
        "- Architectural change — Help is now a supported presentation subsystem over canonical "
        "repository documentation; persistence, acquisition, and stream authorities are "
        "unchanged.\n"
        "- Important limitation — no custom search index or repository-administration browser "
        "page.\n"
        "- Next architectural milestone — select from operating evidence; no follow-up milestone "
        "is "
        "authorized by TASK-027.\n",
    )
    return browser_proof


def main() -> int:
    """Run gates, assemble records, and build a checksum-verified ZIP."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        review.run(
            "focused-task027",
            [str(PYTHON), "-m", "unittest", "tests.test_task027", "-v"],
        ),
        review.run(
            "workflow-proof",
            [str(PYTHON), "scripts/task027_workflows.py"],
        ),
        review.run(
            "relevant-admin-cli-storage-workflows",
            [
                str(PYTHON), "-m", "unittest",
                "tests.test_task009", "tests.test_task010", "tests.test_task011",
                "tests.test_task012", "tests.test_task014", "tests.test_task015",
                "tests.test_task017", "tests.test_task018", "tests.test_task019",
                "tests.test_task021", "tests.test_task023", "tests.test_task024",
                "tests.test_task025", "tests.test_task025_hardening",
                "tests.test_task026", "tests.test_acquisition", "tests.test_engine",
                "tests.test_runtime_config", "tests.test_foundation", "-v",
            ],
        ),
        review.run("documentation-check", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("lint", [str(PYTHON), "scripts/quality.py", "lint"]),
        review.run("format-check", [str(PYTHON), "scripts/quality.py", "format"]),
        review.run("typecheck", [str(PYTHON), "scripts/quality.py", "typecheck"]),
        review.run("baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        review.run("source-archive", [str(PYTHON), "scripts/build_source_archive.py"]),
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("complete-repository-validation", ["make", "validate"]),
    ]
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
            {
                path: "TASK-027 implementation, canonical guide, test, proof, or task ticket"
                for path in files
            },
            indent=2,
        )
        + "\n",
    )
    browser_proof = write_records(branch, head, base)
    scan = review.sensitive_scan()
    failures = [item["name"] for item in validations if not item["passed"]]
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    review.write(
        "validation-commands.md",
        "# Exact validation commands and retained outputs\n\n"
        + "\n".join(
            f"- `{' '.join(item['command'])}` — "
            f"`{'PASS' if item['passed'] else 'FAIL'}`; see "
            f"`validation/{item['name']}.txt`."
            for item in validations
        )
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
        "browser_proof": browser_proof,
        "sensitive_output_scan": scan,
        "generated_artifacts_excluded_from_product_diff": True,
    }
    review.write("verification-summary.json", json.dumps(metadata, indent=2) + "\n")
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    archive = review.archive(metadata)
    print(
        json.dumps(
            {
                "result": "PASS",
                "review_directory": str(PACKAGE.relative_to(ROOT)),
                "review_zip": str(ZIP_PATH.relative_to(ROOT)),
                "checksum_file": str(ZIP_HASH.relative_to(ROOT)),
                "zip": archive,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
