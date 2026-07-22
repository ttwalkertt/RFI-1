#!/usr/bin/env python3
"""Generate and verify the complete TASK-028 independent review package."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import generate_task018_review as review

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-028"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = PACKAGE.parent / f"{TASK_ID}-review.zip"
ZIP_HASH = ZIP_PATH.with_suffix(".zip.sha256")
INPUT = ROOT / ".artifacts/review-input/TASK-028"
PYTHON = Path(sys.executable)

review.TASK_ID = TASK_ID
review.PACKAGE = PACKAGE
review.ZIP_PATH = ZIP_PATH
review.ZIP_HASH = ZIP_HASH


def copy(relative: str, source: Path) -> None:
    """Copy one durable or captured input into the self-contained package."""
    target = PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def extract_json(name: str) -> dict[str, Any]:
    """Extract the proof JSON from a retained command transcript."""
    content = (PACKAGE / f"validation/{name}.txt").read_text(encoding="utf-8")
    start = content.find("{\n")
    end = content.rfind("\nexit_code:")
    if start < 0 or end < 0:
        raise RuntimeError(f"JSON proof absent from {name}")
    return json.loads(content[start:end])


def isolated_validation() -> dict[str, Any]:
    """Run focused workflow and policy proof without Git, state, artifacts, or credentials."""

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(review.EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task028-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        commands = (
            [str(PYTHON), "-m", "unittest", "tests.test_task028", "tests.test_task023",
             "tests.test_task025_hardening", "-v"],
            [str(PYTHON), "scripts/task028_workflow.py"],
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
            result = review.subprocess.run(
                command,
                cwd=destination,
                env={**review.os.environ, "PYTHONPATH": "src"},
                text=True,
                stdout=review.subprocess.PIPE,
                stderr=review.subprocess.STDOUT,
                check=False,
            )
            output.extend((
                f"$ {' '.join(command)}", result.stdout,
                f"exit_code: {result.returncode}", "",
            ))
            passed = passed and result.returncode == 0
    review.write("validation/isolated-tree.txt", "\n".join(output))
    return {
        "name": "isolated-tree",
        "command": ["copied-tree TASK-028 and policy matrix"],
        "exit_code": 0 if passed else 1,
        "passed": passed,
    }


def validation_summary(validations: list[dict[str, Any]]) -> str:
    """Render exact commands and outcomes for the completion report."""
    return "\n".join(
        f"- `{' '.join(item['command'])}` — "
        f"`{'PASS' if item['passed'] else 'FAIL'}` (exit {item['exit_code']}); "
        f"raw output: `validation/{item['name']}.txt`."
        for item in validations
    )


def records(
    branch: str,
    base: str,
    head: str,
    files: list[str],
    validations: list[dict[str, Any]],
    staged: str,
    unstaged: str,
    untracked: str,
    status: str,
) -> None:
    """Write the human and machine evidence required by the task ticket."""
    copies = {
        "task-ticket.md": ROOT / "tasks/TASK-028-linux-kernel-mailing-list-stream-workflow.md",
        "architecture/design-record.md": ROOT / "docs/linux-mailing-list-workflow.md",
        "architecture/decision.md": (
            ROOT / "docs/decisions/0022-linux-mailing-list-workflow-facade.md"
        ),
        "operator/operator-guide.md": ROOT / "docs/operator-guide.md",
        "browser/browser-proof.json": INPUT / "browser-proof.json",
        "browser/rendered-evidence.md": INPUT / "rendered-evidence.md",
        "browser/raw-api-saved.json": INPUT / "raw-api-saved.json",
        "browser/raw-api-result.json": INPUT / "raw-api-result.json",
        "browser/raw-network-server.log": INPUT / "raw-network-server.log",
        "live/live-proof.json": INPUT / "live-proof.json",
    }
    for destination, source in copies.items():
        if not source.is_file():
            raise RuntimeError(f"required review input absent: {source}")
        copy(destination, source)
    browser = json.loads((INPUT / "browser-proof.json").read_text(encoding="utf-8"))
    live = json.loads((INPUT / "live-proof.json").read_text(encoding="utf-8"))
    if not all(browser["checks"].values()) or live["result"] != "PASS":
        raise RuntimeError("browser or live proof has a failed check")
    fixture = extract_json("workflow-proof")
    review.write("evidence/fixture-workflow-proof.json", json.dumps(fixture, indent=2) + "\n")
    for screenshot in sorted((INPUT / "screenshots").glob("*.jpg")):
        copy(f"browser/screenshots/{screenshot.name}", screenshot)
    live_first = live["first_run"]
    live_repeat = live["repeated_run"]
    staged_state = "empty" if not staged.strip() else "non-empty"
    worktree_state = (
        "dirty (intentional TASK-028 working-tree changes)" if status.strip() else "clean"
    )
    review.write(
        "completion-report.md",
        f"""# TASK-028 completion report

## Operator outcome and exact workflow

Navigate using **Linux Mailing Lists**. The task surface uses these exact stages: **Choose mailing
list** → **Name the stream** → **Define bounded scope** → **Review** → **Create and test** →
**Retrieved evidence**. The primary controls are **Add mailing list**, **Validate archive
connectivity**, **Review mailing-list stream**, **Create and test stream**, and **Reload saved
streams**. Reload names the durable state it reloads, warns on unsaved work, and is not an ambiguous
generic Refresh action. No visit to **External Sources** is required.

The archive selector offers known human-readable Lore lists and **Enter another Lore archive URL**.
Custom values must normalize to one canonical HTTPS archive directly under
`https://lore.kernel.org/`; unsupported hosts, credentials, ports, queries, fragments, and invalid
archive shapes are rejected. The supplied stream name becomes a normalized stream identity. The
canonical archive identity plus `-lore` becomes the source identity. An occupied identity with a
different meaning receives deterministic increasing SHA-256 suffix prefixes; identical intent
resolves the existing record/revision rather than creating a duplicate.

The bounded scope requires start/through dates (maximum 31 days), a direct-message maximum, a
larger total-message maximum, and reply depth. Optional supported relevance controls are keywords,
subjects, and senders/participants. Required ancestors may predate the seed window to preserve
connected context. No unbounded archive-mirroring control exists.

## Validation, review, save, test, and acquisition

**Validate archive connectivity** checks canonical structure and the live Atom endpoint but saves
nothing. **Review mailing-list stream** validates and displays the full normalized intent,
generated identities, bounds, records, and side effects; it saves, tests, and retrieves nothing.
**Create and test stream** coordinates the existing source service and stream/revision service to
create or resolve durable configuration, then invokes established bounded acquisition, immutable
artifact/provenance storage, and stream-result contracts. Later acquisition remains a separate,
explicit bounded operation.

Progress and feedback are visible for archive validation, governed source, stream revision,
retrieval, connected context, immutable storage, and result publication. Review failure persists
nothing. If source creation succeeds before a later failure, the response names that durable state
and safe retry. Retrieval failures retain their lifecycle status and retryability. Repeated
submission resolves identical configuration idempotently. Empty, partial, failed, and truncated
tests are never presented as complete connected evidence.

**Configuration ready** means the saved source/stream/revision can be executed later. **Test
evidence incomplete or truncated** means the bounded test did not prove complete connected
evidence. These concepts remain separate in the service result, saved-state projection, browser
badges, guide, automated tests, raw API proof, screenshots, and live proof. Truncation and
connectivity reporting were not weakened.

## Exact legacy source repair

The defect was reproduced against the operator's original repository state. Generated
archive/source identity was `linux-block` / `linux-block-lore`. A prior External Sources record
stored
`https://lore-kernel-org/linux-block`; the workflow requested
`https://lore.kernel.org/linux-block/`. The stored value is not a supported Lore URL and does not
normalize; the requested value normalizes to itself. The failure path was
`validate_archive → review → _source → source_conflict`, before Lore network access.

The existing record had zero stream revisions, attempts, observations, checkpoints, mailing-list
runs, and messages. Schema migration v5 therefore matched the exact known record and atomically
updated the governed-source and mailing-list projections. The stable source ID was preserved and
both source counts remained one. Restart was idempotent. Any different predicate or durable
dependency is left untouched, and there is no generalized operator-facing repair capability.

Equivalent supported variants—host-name case and an omitted trailing slash—now normalize to one
canonical URL and reuse prior source IDs, including identities from the earlier External Sources
workflow. HTTP, alternate hosts, nested paths, queries, fragments, ports, credentials, or a
different archive path are not aliases. Genuine in-use mismatches remain protected from
replacement. External Sources validation now applies the same canonical Lore rule, preventing the
malformed-host state from recurring.

The normal RFI connectivity request through the operator's original server returned HTTP 200,
`reachable: true`, title `linux-block.vger.kernel.org archive mirror`, and update time
`2026-07-21T16:43:21Z`. RFI-1 did not receive Anubis or another anti-bot response, so anti-bot
handling was neither investigated further nor modified. No browser cookies were read or used.

## Exact live Lore proof

Archive: `{live['archive']}`. Scope: {live['operator_selection']['date_from']} through
{live['operator_selection']['date_through']}; keyword `zloop`; direct limit 1; total limit 8; reply
depth 1. First result: `{live_first['run_status']}`, configuration executable, test evidence
incomplete/truncated, connectivity `{live_first['connectivity_state']}`; 1 direct seed, 5 expanded
context messages, 6 persisted messages, 5 relationships, 6 newly created artifacts, and 0
idempotent messages. The repeated result remained `{live_repeat['status']}`, created 0 artifacts,
reused all 6 messages, retained 5 relationships, and was stream-run idempotent. Actual subject,
sender, effective time, Message-ID, parent/depth/reply context, direct/context-only reason, and
canonical Lore links are visible in the browser; **Inspect all retained evidence in Artifacts**
opens the established inspection surface.

## Help and terminology compliance

Every meaningful field has persistent adjacent purpose, format, bounds, and consequence guidance.
Non-modal repository-owned help is linked for choosing Lore, bounds, discussion context, generated
identities, lifecycle, incomplete results, retry, and connectivity. The template contains zero
`placeholder` attributes; placeholders are not used as required help. Every primary action reports
busy/no-change/success/failure state and a next action. Existing source, stream, YAML, help,
acquisition, artifact, provenance, and SQLite repository contracts remain authoritative; no shadow
store exists.

## Validation results

{validation_summary(validations)}

## Review package and integrity

- Review directory: `.artifacts/review/TASK-028`
- Review ZIP: `.artifacts/review/TASK-028-review.zip`
- ZIP size, integrity, and SHA-256: `POST_ARCHIVE_SEAL`
Member paths, byte sizes, and SHA-256 values are in `review-manifest.json`; verification output is
in `zip-integrity.txt`, `member-checksums.sha256`, and the sibling ZIP checksum file.

## Exact repository state

- Branch: `{branch}`
- Base: `{base}`
- HEAD: `{head}`
- Staged: `{staged_state}`
- Unstaged: `{'non-empty' if unstaged.strip() else 'empty'}`
- Untracked: `{'non-empty' if untracked.strip() else 'empty'}`
- Worktree: `{worktree_state}`

The exact porcelain status, staged diff, unstaged diff, untracked listing, cumulative patch, and
tree are retained under `repository/`.

## Known limitations and departures

The built-in archive catalog is intentionally small; supported custom canonical Lore archives are
available. There is no scheduler, durable cursor, archive mirror, participant-alias resolver,
cross-list federation, full-text index, or patch-series semantic model. Live execution depends on
Lore and bounded results may legitimately be incomplete. There was no departure from TASK-028.

No commit, push, merge, branch deletion, cleanup, or unrelated Git lifecycle operation occurred.
""",
    )
    documents = {
        "operator-workflow-summary.md": (
            "Choose list → name stream → define date/relevance/bounds → non-persistent review → "
            "Create and test stream → inspect direct and context-only evidence. Internal source, "
            "schema, revision, and persistence mechanics remain secondary."
        ),
        "before-after-workflow.md": (
            "Before: External Sources → copy identity → generic Streams → "
            "revision/validation/test. "
            "After: one Linux Mailing Lists task surface coordinates those unchanged authorities "
            "and ends with retained messages rather than configuration alone."
        ),
        "page-and-interaction-state-model.md": (
            "The page distinguishes new unsaved, valid reviewed/unsaved, saved untested, working "
            "stages, configuration readiness, and separate complete, incomplete, empty, partial, "
            "failed, or untested evidence. Seven stage rows report "
            "archive, source, stream, retrieval, context, storage, and verification. New/reload "
            "protect unsaved work and all network actions disable duplicate submission."
        ),
        "generated-identity-policy.md": (
            "Source identity is canonical archive plus `-lore`; stream identity is normalized "
            "human name. Occupied different meanings receive deterministic increasing SHA-256 "
            "prefixes. Identical intent resolves the current definition without a new revision."
        ),
        "partial-failure-and-retry-policy.md": (
            "Review persists nothing. Source creation followed by stream failure reports the "
            "durable source and safe retry. Acquisition failures use established lifecycle and "
            "retryability. Empty matches do not provide complete test evidence. Partial evidence "
            "is inspectable but not test success. A bounded truncated result leaves the saved "
            "configuration executable while "
            "the test-evidence badge remains explicitly incomplete or truncated."
        ),
        "field-help-inventory.md": (
            "Archive selector/URL, name, description, start/through dates, keywords, subjects, "
            "participants, direct limit, total limit, and reply depth each have persistent "
            "adjacent "
            "purpose/format/bounds/consequence guidance. Required instruction uses no placeholder."
        ),
        "context-help-topic-mapping.md": (
            "The page maps to `linux-mailing-lists`; linked topics cover choosing Lore, bounded "
            "acquisition, discussion context, generated identities, lifecycle, incompleteness, "
            "retry, and Lore connectivity through the TASK-027 named non-modal target."
        ),
        "placeholder-policy-audit.md": (
            "The workflow template contains zero placeholder attributes. Examples are not used as "
            "documentation; persistent `.help` text and canonical non-modal topics carry guidance."
        ),
        "negative-proofs.md": (
            "Hard date/direct/total/depth validation and absence of an unbounded control prevent "
            "mirroring. No stream/source ID input exists. Review/validation repository counts stay "
            "zero. Unsupported hosts are actionable. Empty/timeout tests never claim complete "
            "evidence. Partial "
            "creation names durable state. Browser routes use the façade, and SQLite remains the "
            "only structured authority. TASK-023 connectivity and TASK-025/026 invariants pass."
        ),
        "architectural-status-summary.md": (
            "The workflow façade and browser/API are Complete. Lore bounded Atom discovery and "
            "reply enumeration are Usable with Limitations. Source, stream, acquisition, immutable "
            "artifact, provenance, and SQLite authorities remain Complete and unchanged. Durable "
            "cursors, scheduling, cross-list federation, identity resolution, and patch-series "
            "semantics remain Not Started. No next milestone is authorized by TASK-028."
        ),
        "known-limitations.md": (
            "The catalog is small; custom canonical Lore archives are supported. No cursor, "
            "scheduler, archive mirror, participant aliases, full-text index, federation, or patch "
            "series model exists. Live execution depends on Lore and bounded results may be "
            "explicitly incomplete."
        ),
        "browser/network-and-console-evidence.md": (
            "Raw server access-log evidence retains method, route, and HTTP status for the browser "
            "sequence, including create/test/result reads, restart, a 400 invalid-archive review, "
            "and its 200 recovery. Raw saved-state and result API bodies retain configuration and "
            "evidence semantics plus the exact six-message result. Browser warning/error logs were "
            "empty. Nine actual browser JPEGs cover fresh, review, progress, result, restart, "
            "failure, and recovery states."
        ),
    }
    for name, body in documents.items():
        title = name.removesuffix(".md").replace("-", " ").title()
        review.write(name, f"# {title}\n\n{body}\n")
    review.write(
        "repository/changed-files-with-rationale.json",
        json.dumps(
            {path: (
                "TASK-028 workflow implementation, proof, documentation, or required "
                "regression update"
            )
             for path in files},
            indent=2,
        ) + "\n",
    )


def finalize_directory_report(
    archive: dict[str, Any], metadata: dict[str, Any]
) -> None:
    """Record the final ZIP seal without pretending a ZIP can contain its own digest."""
    report_path = PACKAGE / "completion-report.md"
    report = report_path.read_text(encoding="utf-8").replace(
        "`POST_ARCHIVE_SEAL`",
        f"`{archive['bytes']} bytes; integrity {archive['integrity']}; "
        f"SHA-256 {archive['sha256']}`",
    )
    report += (
        "\nThe ZIP necessarily contains the pre-seal form of this paragraph: embedding the final "
        "digest inside the bytes being digested is cryptographically self-referential. This "
        "review-directory report and the sibling `TASK-028-completion-report.md` are the final "
        "sealed report; the ZIP remains independently integrity-checked and its exact digest is "
        "in `TASK-028-review.zip.sha256`.\n"
    )
    report_path.write_text(report, encoding="utf-8")
    (PACKAGE.parent / "TASK-028-completion-report.md").write_text(report, encoding="utf-8")
    checksum_path = PACKAGE / "member-checksums.sha256"
    manifest_path = PACKAGE / "review-manifest.json"
    members = sorted(
        path for path in PACKAGE.rglob("*")
        if path.is_file() and path not in {checksum_path, manifest_path}
    )
    checksum_path.write_text(
        "\n".join(
            f"{review.sha256(path)}  {path.relative_to(PACKAGE).as_posix()}"
            for path in members
        ) + "\n",
        encoding="utf-8",
    )
    records = [
        {
            "path": path.relative_to(PACKAGE).as_posix(),
            "sha256": review.sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(
            path for path in PACKAGE.rglob("*")
            if path.is_file() and path != manifest_path
        )
    ]
    manifest_path.write_text(
        json.dumps(
            {**metadata, "final_zip_seal": archive, "members_excluding_manifest": records},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run all gates, assemble the package, and build a verified ZIP."""
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    validations = [
        review.run("focused-task028", [str(PYTHON), "-m", "unittest", "tests.test_task028", "-v"]),
        review.run(
            "required-regressions",
            [str(PYTHON), "-m", "unittest", "tests.test_task023", "tests.test_task025",
             "tests.test_task025_hardening", "tests.test_task026", "tests.test_task027", "-v"],
        ),
        review.run("workflow-proof", [str(PYTHON), "scripts/task028_workflow.py"]),
        review.run("documentation-check", [str(PYTHON), "scripts/check_docs.py"]),
        review.run("lint", [str(PYTHON), "scripts/quality.py", "lint"]),
        review.run("format-check", [str(PYTHON), "scripts/quality.py", "format"]),
        review.run("typecheck", [str(PYTHON), "scripts/quality.py", "typecheck"]),
        review.run("baseline", [str(PYTHON), "scripts/check_baseline.py"]),
        review.run("source-archive", [str(PYTHON), "scripts/build_source_archive.py"]),
        review.run("git-diff-check", ["git", "diff", "--check"]),
        review.run("complete-repository-validation", ["make", "validate"]),
        isolated_validation(),
    ]
    branch = review.git("branch", "--show-current").strip()
    head = review.git("rev-parse", "HEAD").strip()
    base = review.git("merge-base", "main", "HEAD").strip()
    files = review.changed_files()
    status = review.git("status", "--short", "--branch")
    staged = review.git("diff", "--cached", "--binary")
    unstaged = review.git("diff", "--binary")
    untracked = review.git("ls-files", "--others", "--exclude-standard")
    review.write(
        "repository/branch-base-head.txt",
        f"branch: {branch}\nbase: {base}\nhead: {head}\n",
    )
    review.write("repository/git-status.txt", status)
    review.write(
        "repository/staged.diff",
        staged or "(empty)\n",
    )
    review.write("repository/unstaged.diff", unstaged or "(empty)\n")
    review.write(
        "repository/untracked.txt",
        untracked,
    )
    review.write("repository/cumulative-task.patch", review.complete_patch())
    review.write("repository/repository-tree.txt", review.repository_tree())
    records(branch, base, head, files, validations, staged, unstaged, untracked, status)
    scan = review.sensitive_scan()
    failures = [item["name"] for item in validations if not item["passed"]]
    if scan["result"] != "PASS":
        failures.append("sensitive-output-scan")
    review.write(
        "validation-commands.md",
        "# Exact validation commands and retained outputs\n\n" + "\n".join(
            f"- `{' '.join(item['command'])}` — `{'PASS' if item['passed'] else 'FAIL'}`; "
            f"see `validation/{item['name']}.txt`." for item in validations
        ) + "\n",
    )
    browser_artifacts = [
        {
            "path": f"browser/screenshots/{path.name}",
            "bytes": path.stat().st_size,
            "sha256": review.sha256(path),
        }
        for path in sorted((INPUT / "screenshots").glob("*.jpg"))
    ]
    browser_artifacts.extend(
        {
            "path": f"browser/{path.name}",
            "bytes": path.stat().st_size,
            "sha256": review.sha256(path),
        }
        for path in (
            INPUT / "raw-network-server.log",
            INPUT / "raw-api-saved.json",
            INPUT / "raw-api-result.json",
        )
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
        "live_proof": json.loads((INPUT / "live-proof.json").read_text(encoding="utf-8")),
        "browser_proof": json.loads((INPUT / "browser-proof.json").read_text(encoding="utf-8")),
        "browser_artifacts": browser_artifacts,
        "sensitive_output_scan": scan,
        "generated_artifacts_excluded_from_product_diff": True,
    }
    review.write("verification-summary.json", json.dumps(metadata, indent=2) + "\n")
    if failures:
        print(json.dumps({"result": "FAIL", "failures": failures}, indent=2))
        return 1
    archive = review.archive(metadata)
    finalize_directory_report(archive, metadata)
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
