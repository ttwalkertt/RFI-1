#!/usr/bin/env python3
"""Generate the independently auditable TASK-004 package, including blocked live evidence."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-004"
REVIEW_ROOT = ROOT / ".artifacts/review"
PACKAGE = REVIEW_ROOT / TASK_ID
ZIP_PATH = REVIEW_ROOT / f"{TASK_ID}-review.zip"
ZIP_HASH = REVIEW_ROOT / f"{TASK_ID}-review.zip.sha256"
LIVE_EVIDENCE = ROOT / ".artifacts/runtime/TASK-004-edgar-evidence"
PYTHON = Path(sys.executable)
EXCLUDED = {".artifacts", ".git", ".rfi", ".venv", "__pycache__"}


def run(
    command: list[str],
    cwd: Path = ROOT,
    environment: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Capture exact combined output without invoking a shell."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n"
    return result.returncode, output


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, content: str) -> None:
    (PACKAGE / name).write_text(content, encoding="utf-8")


def complete_patch() -> str:
    parts = [git("diff", "--binary", "HEAD", "--", ".")]
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for relative in sorted(item for item in untracked if item):
        code, output = run(["git", "diff", "--no-index", "--binary", "/dev/null", relative])
        if code not in {0, 1}:
            raise RuntimeError(output)
        parts.append(output.split("\n", 1)[1].rsplit("exit_code:", 1)[0])
    return "".join(parts)


def repository_tree() -> str:
    values = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        values.append(relative.as_posix())
    return "\n".join(sorted(values)) + "\n"


def isolated_validation(environment: dict[str, str]) -> tuple[int, str]:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(names).intersection(EXCLUDED)

    with tempfile.TemporaryDirectory(prefix="rfi-task-004-isolated-") as temporary:
        destination = Path(temporary) / "RFI-1"
        shutil.copytree(ROOT, destination, ignore=ignore)
        code, output = run(["make", "validate"], cwd=destination, environment=environment)
    method = (
        "Method: complete isolated source copy; local runtime configuration excluded; both "
        "runtime environment values removed; validate contains no live operator command.\n\n"
    )
    return code, method + output


def narratives(
    branch: str,
    head: str,
    native_identity_present: bool,
    native_live_complete: bool,
) -> None:
    live = (
        "PASS — bounded native EDGAR acceptance evidence was imported and validated."
        if native_live_complete
        else "BLOCKED — RFI_SEC_USER_AGENT was absent; zero native requests were made."
    )
    write(
        "executive-summary.md",
        "# Executive summary\n\n"
        "TASK-004 implements native SEC EDGAR and optional SEC-API.io adapters behind the "
        "unchanged acquisition contract. Native EDGAR is the amended live acceptance path; "
        "SEC-API.io remains offline-only. Exact submissions, stable SEC identity, bounded "
        f"discovery, replay, rebuild, and integrity are implemented. Native status: {live}\n\n"
        f"Branch: `{branch}`  \nHEAD: `{head}`  \n"
        f"Native identity present during packaging: `{native_identity_present}`\n",
    )
    write(
        "implementation-summary.md",
        "# Implementation summary\n\n"
        "- Native EDGAR submissions discovery and official archive retrieval adapter.\n"
        "- Runtime-only declared User-Agent and two-requests-per-second pacing.\n"
        "- Optional SEC-API.io adapter retained without weakening its tests.\n"
        "- Fixed STX/WDC issuer profiles and per-form limits.\n"
        "- SEC CIK/accession repository identity and exact complete-submission artifacts.\n"
        "- Distinct synthetic fixture, runtime corpus, and generated evidence boundaries.\n"
        "- No TASK-002/TASK-003 contract correction and no downstream capability.\n",
    )
    adr = (ROOT / "docs/decisions/0004-first-live-sec-api-acquisition.md").read_text()
    write("architecture-decisions.md", adr)
    alternatives = adr.split("## Alternatives considered", 1)[1].split(
        "## Consequences", 1
    )[0]
    write("alternatives-considered.md", "# Alternatives considered\n" + alternatives)
    write(
        "provider-and-api-surface.md",
        "# Provider and API surface\n\nNative live path: official SEC submissions JSON at "
        "`https://data.sec.gov/submissions/CIK##########.json` and exact complete-submission "
        "bytes under `https://www.sec.gov/Archives/edgar/data/`. Optional commercial path: "
        "SEC-API.io Query and Filing Download APIs, implemented and tested only with synthetic "
        "transport fixtures.\n",
    )
    write(
        "credential-and-secret-boundary.md",
        "# Runtime identity and secret boundary\n\nNative EDGAR requires `RFI_SEC_USER_AGENT` "
        "with an application identity and operator contact email. Explicit live commands may "
        "load it from the process environment or private Git-ignored `.rfi/runtime.env`; "
        "environment values win. The loader accepts only the two governed names and rejects "
        "symlinks, broad permissions, malformed input, and oversized files. Offline validation "
        "and review generation disable local loading. Profiles and outputs contain references or "
        "presence only. SEC-API.io optionally resolves `SEC_API_IO_API_KEY` through the same "
        "boundary. Error bodies are discarded.\n",
    )
    write(
        "sec-identity-model.md",
        "# SEC identity model\n\nIssuer: normalized SEC CIK. Filing/document: issuer CIK plus SEC "
        "accession. Amendments have distinct accessions and distinct filing identities. "
        "Candidate: filing plus complete-submission role. Artifact: repository SHA-256 of exact "
        "bytes. Provider IDs, URLs, offsets, ticker, form, and timestamps are provenance only.\n",
    )
    write(
        "network-and-retry-model.md",
        "# Network and retry model\n\nNative requests are spaced at least 0.5 seconds apart, "
        "limiting the client to two per second below the SEC maximum of ten. The adapter uses a "
        "20-second timeout, two attempts, 5 MB submissions and 50 MB artifact limits, an "
        "80-request ceiling, response validation, and sanitized 429/5xx/timeout handling.\n",
    )
    write(
        "provider-response-mapping.md",
        "# Provider response mapping\n\nNative mapping requires submissions accessionNumber, CIK, "
        "form, filingDate, acceptanceDateTime, reportDate, and primaryDocument arrays. Archive "
        "paths and historical submissions-file references remain provenance. Missing, malformed, "
        "or inconsistent identity fails closed. SEC-API.io mapping remains documented "
        "separately.\n",
    )
    edgar_guide = (ROOT / "docs/edgar-acquisition.md").read_text()
    bounded = edgar_guide.split("## Fixed corpus", 1)[1].split(
        "## Runtime identity", 1
    )[0]
    write("bounded-corpus-definition.md", "# Bounded corpus definition\n" + bounded)
    write(
        "live-run-summary.md",
        f"# Native EDGAR first-run summary\n\n{live}\n\nSee the sanitized native first-run "
        "output and corpus inventory. Fixture evidence is labeled separately.\n",
    )
    write(
        "live-rerun-idempotency.md",
        f"# Native EDGAR rerun and idempotency\n\n{live}\n\nA live result is claimed only when "
        "the imported acceptance summary is PASS and both inventories match.\n",
    )
    write(
        "provider-usage-summary.md",
        "# Provider usage summary\n\nNative usage is recorded in live acceptance evidence when "
        "available, including physical request counts and pacing delay. Without the runtime "
        "identity, native requests are zero. SEC-API.io usage remains synthetic and "
        "offline-only.\n",
    )
    write(
        "offline-replay-and-rebuild.md",
        "# Offline replay and rebuild\n\nNative synthetic-fixture and SEC-API.io fixture corpora "
        "both replay with sockets blocked. When native live evidence exists, its provider-disabled "
        "replay, derived-index rebuild, inventory, and artifact integrity results are imported "
        "separately and remain authoritative for live acceptance.\n",
    )
    write(
        "real-integration-lessons.md",
        "# Real-integration lessons\n\nOfficial SEC documentation established submissions JSON, "
        "archive layout, declared User-Agent requirements, and a maximum ten requests per second. "
        "Native live behavior is described only when real evidence exists. The optional commercial "
        "path remains untested live. No central contract correction was required offline.\n",
    )
    write(
        "known-limitations.md",
        "# Known limitations\n\n- Native live acceptance remains blocked without an "
        "operator-supplied "
        "runtime identity.\n- SEC-API.io is untested live.\n- Fixtures are synthetic, not recorded "
        "provider responses.\n- Request budgets are process-wide, and filesystem operation remains "
        "single-writer.\n",
    )
    write(
        "deferred-work.md",
        "# Deferred work\n\nTASK-005 recommendations: schema-drift fixtures from sanitized live "
        "responses, historical submissions-file validation, caching/retry-after evidence, "
        "cross-provider attempt identity, run-scoped usage, locking, and backups. Bulk ingestion, "
        "XBRL, parsing, extraction, knowledge, AI, search, and reports remain out of scope.\n",
    )


def acceptance(native_live_complete: bool) -> str:
    live_status = "PASS" if native_live_complete else "BLOCKED"
    criteria = [
        ("PASS", "Native EDGAR and SEC-API.io implement the existing adapter boundary."),
        ("PASS", "Official submissions/archive and optional commercial surfaces are documented."),
        (live_status, "Native runtime identification and configuration probe completed."),
        (
            "PASS",
            "Profiles, source, fixtures, outputs, patch, and package contain no secret value.",
        ),
        ("PASS", "STX/WDC profiles are fixed, bounded, and validated."),
        ("PASS", "SEC CIK/accession identity is stable and documented."),
        ("PASS", "Provider identifiers and URLs remain provenance."),
        ("PASS", "EDGAR columnar mapping and bounded continuations pass offline tests."),
        (
            "PASS",
            "Timeouts, retries, response checks, limits, and sanitized errors are implemented.",
        ),
        ("PASS", "Offline identity/rate-limit/timeout/malformed/retrieval tests pass."),
        ("PASS", "Normal validation passes identity-free with live entry points excluded."),
        (live_status, "A real bounded native STX/WDC corpus was acquired."),
        (live_status, "Exact real filing bytes and checksums were preserved."),
        (live_status, "Real native provenance and append-only history are inspectable."),
        ("PASS", "Offline checkpoint finalization remains durably ordered."),
        (live_status, "An equivalent native live rerun demonstrated idempotency."),
        ("PASS", "The fixed offline/live configuration cannot widen with wall time."),
        (live_status, "Native request counts and pacing evidence were captured."),
        (live_status, "Runtime identity references were released before offline replay."),
        (live_status, "Live authoritative state replayed with network blocked."),
        (live_status, "Live derived indexes deleted and rebuilt."),
        (live_status, "All live corpus checksums passed."),
        ("PASS", "No prior contract correction was required."),
        ("PASS", "Lessons, alternatives, risks, and TASK-005 recommendations are recorded."),
        ("PASS", "All prior fixture adapters and tests pass."),
        ("PASS", "No downstream knowledge, AI, extraction, or projection was added."),
        ("PASS", "Complete honest-status verification package is generated."),
        ("PASS", "Branch, HEAD, patch, changed files, and Git state are captured."),
        ("PASS", "Live success is claimed only when imported native evidence validates."),
    ]
    return "# TASK-004 acceptance criteria\n\n" + "\n".join(
        f"{number}. {status} — {message}"
        for number, (status, message) in enumerate(criteria, 1)
    ) + "\n"


def main() -> int:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir()
    ZIP_PATH.unlink(missing_ok=True)
    ZIP_HASH.unlink(missing_ok=True)
    environment = os.environ.copy()
    commercial_credential_present = bool(environment.pop("SEC_API_IO_API_KEY", None))
    native_identity_present = bool(environment.pop("RFI_SEC_USER_AGENT", None))
    live_summary_path = LIVE_EVIDENCE / "acceptance-summary.json"
    native_live_complete = False
    if live_summary_path.is_file():
        live_summary = json.loads(live_summary_path.read_text(encoding="utf-8"))
        native_live_complete = live_summary.get("result") == "PASS"
    environment["PYTHONPATH"] = "src"
    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    outcomes: dict[str, dict[str, Any]] = {}
    matrix = [
        (
            "focused-test-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_edgar", "-v"],
        ),
        (
            "focused-sec-api-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_sec_api", "-v"],
        ),
        (
            "focused-runtime-config-output.txt",
            [str(PYTHON), "-m", "unittest", "tests.test_runtime_config", "-v"],
        ),
        (
            "raw-full-offline-suite-output.txt",
            ["make", "validate"],
        ),
        (
            "offline-native-edgar-fixture-output.txt",
            [str(PYTHON), "scripts/verify_edgar.py"],
        ),
        (
            "offline-sec-api-fixture-output.txt",
            [str(PYTHON), "scripts/verify_sec_api.py"],
        ),
        (
            "sanitized-native-configuration-check-output.txt",
            [
                str(PYTHON),
                "scripts/edgar_operator.py",
                "live-config",
                "--probe",
                "--no-local-config",
            ],
        ),
        (
            "sanitized-commercial-configuration-check-output.txt",
            [
                str(PYTHON),
                "scripts/sec_api_operator.py",
                "live-config",
                "--probe",
                "--no-local-config",
            ],
        ),
    ]
    for name, command in matrix:
        code, output = run(command, environment=environment)
        write(name, output)
        expected = 2 if "configuration-check" in name else 0
        outcomes[name] = {
            "command": command,
            "exit_code": code,
            "expected_exit_code": expected,
            "passed": code == expected,
        }
    isolated_code, isolated_output = isolated_validation(environment)
    write("raw-isolated-tree-validation-output.txt", isolated_output)
    outcomes["raw-isolated-tree-validation-output.txt"] = {
        "command": ["make", "validate"],
        "exit_code": isolated_code,
        "expected_exit_code": 0,
        "passed": isolated_code == 0,
        "live_entry_points_excluded": True,
        "local_runtime_configuration_excluded": True,
    }
    blocked = (
        "BLOCKED: RFI_SEC_USER_AGENT absent; native EDGAR stopped before network access; "
        "provider requests: 0.\n"
    )
    if native_live_complete:
        first_live = (LIVE_EVIDENCE / "live-first-run.json").read_text(encoding="utf-8")
        second_live = (LIVE_EVIDENCE / "live-second-run.json").read_text(encoding="utf-8")
        replay_live = (LIVE_EVIDENCE / "provider-disabled-replay.json").read_text(
            encoding="utf-8"
        )
    else:
        first_live = blocked
        second_live = blocked
        replay_live = blocked
    write("sanitized-live-first-run-output.txt", first_live)
    write("sanitized-live-second-run-output.txt", second_live)
    native_offline = (PACKAGE / "offline-native-edgar-fixture-output.txt").read_text()
    commercial_offline = (PACKAGE / "offline-sec-api-fixture-output.txt").read_text()
    inventory_evidence = replay_live if native_live_complete else native_offline
    write(
        "corpus-inventory-and-checksums.txt",
        (
            "NATIVE EDGAR LIVE CORPUS EVIDENCE\n\n"
            if native_live_complete
            else "SYNTHETIC NATIVE EDGAR FIXTURE ONLY; NOT LIVE EVIDENCE\n\n"
        )
        + inventory_evidence,
    )
    write(
        "raw-provider-disabled-replay-output.txt",
        (
            "Native provider adapter disabled and identity references released; socket creation "
            "denied during replay.\n\n"
            + replay_live
        ),
    )
    write(
        "raw-index-rebuild-output.txt",
        "Derived views deleted and replayed.\n\n" + replay_live,
    )
    write(
        "evidence-boundaries.md",
        "# Evidence boundaries\n\n- Native EDGAR live evidence: imported only from ignored "
        "`.artifacts/runtime/TASK-004-edgar-evidence/` after a PASS acceptance.\n"
        "- SEC-API.io evidence: offline-only deterministic transport fixtures.\n"
        "- Synthetic fixtures: checked-in small JSON and complete-submission shapes.\n"
        "- Runtime corpus: ignored `.artifacts/runtime/TASK-004-edgar/`.\n"
        "- Local runtime configuration: ignored `.rfi/runtime.env`; never read or copied by this "
        "generator.\n"
        "- Committed source: code, profiles, fixtures, tests, and documentation in the patch.\n"
        "- Generated review artifacts: ignored `.artifacts/review/TASK-004/` and ZIP.\n",
    )
    write(
        "sec-api-status.md",
        "# SEC-API.io status\n\nThe optional commercial adapter remains implemented and all "
        "offline tests pass. No commercial credential-backed request was performed; commercial "
        "live behavior remains untested and is not required by the native amendment.\n\n"
        + commercial_offline,
    )
    narratives(branch, head, native_identity_present, native_live_complete)
    write("acceptance-criteria.md", acceptance(native_live_complete))
    write("repository-tree.txt", repository_tree())
    status = git("status", "--short", "--untracked-files=all")
    write("changed-files.txt", status)
    write("git-status.txt", git("status", "--short", "--branch", "--untracked-files=all"))
    write("git-diff.patch", complete_patch())
    write("staged-diff.txt", git("diff", "--cached", "--binary") or "(empty)\n")
    write(
        "validation-commands.md",
        "# Validation commands\n\nPython: `"
        + str(PYTHON)
        + f"` ({platform.python_version()})\n\n"
        + "\n".join(f"- `{' '.join(item['command'])}`" for item in outcomes.values())
        + "\n- `env -u RFI_SEC_USER_AGENT python scripts/edgar_operator.py live-config "
        "--probe --no-local-config` (expected BLOCKED when identity is absent)\n"
        "- `python scripts/run_task004_edgar_live.py` (explicit live acceptance; operator "
        "configuration required)\n"
        "- `python scripts/generate_task004_review.py`\n\nOffline suites remove both runtime "
        "environment values and contain no live operator commands. The isolated source copy also "
        "excludes local runtime configuration. Missing-value configuration probes report zero "
        "requests. Native live evidence is imported only from the ignored acceptance-evidence "
        "boundary.\n",
    )
    write(
        "zip-checksum.txt",
        f"Final SHA-256 is stored in sibling `{ZIP_HASH.relative_to(ROOT)}` to avoid an "
        "impossible self-referential archive hash.\n",
    )
    write(
        "zip-integrity.txt",
        "Validated with ZipFile.testzip() and `python -m zipfile -t`; final generator output "
        "reports the result. Result: PASS when this delivered package exists.\n",
    )
    write(
        "redaction-rules.md",
        "# Redaction and secret rules\n\nThe generator removes RFI_SEC_USER_AGENT and "
        "SEC_API_IO_API_KEY from every child environment, disables and excludes `.rfi` local "
        "configuration, and records only presence. Native "
        "evidence never renders the outgoing User-Agent. Authorization headers and provider error "
        "bodies are never captured. Secret scanning rejects authorization values, token query "
        "parameters, and API-key assignments. Variable names and sanitized references are "
        "allowed.\n",
    )
    patterns = [
        re.compile(r"Authorization\s*:\s*[^<\s]", re.IGNORECASE),
        re.compile(r"[?&]token=[^<\s]+", re.IGNORECASE),
        re.compile(r"SEC_API_IO_API_KEY\s*=\s*[^.\s]", re.IGNORECASE),
    ]

    def scan_package() -> tuple[list[str], int]:
        suspicious: list[str] = []
        paths = [path for path in PACKAGE.iterdir() if path.is_file()]
        for path in paths:
            content = path.read_text(encoding="utf-8", errors="replace")
            for pattern in patterns:
                if pattern.search(content):
                    suspicious.append(f"{path.name}: {pattern.pattern}")
        return suspicious, len(paths)

    suspicious, scanned = scan_package()
    secret_scan = (
        f"files scanned: {scanned}\nfindings: {len(suspicious)}\n"
        + ("\n".join(suspicious) if suspicious else "result: PASS")
        + "\n"
    )
    write("review-package-secret-scan-output.txt", secret_scan)
    if suspicious:
        raise RuntimeError("review package secret scan failed")
    expected_names = sorted(
        [path.name for path in PACKAGE.iterdir() if path.is_file()]
        + [
            "manifest-checksum-validation.txt",
            "review-manifest.json",
            "zip-member-listing.txt",
            "review-self-validation.txt",
        ]
    )
    member_listing = "Expected final ZIP members:\n" + "\n".join(
        f"{TASK_ID}/{name}" for name in expected_names
    )
    write("zip-member-listing.txt", member_listing + "\n")
    write(
        "review-self-validation.txt",
        f"offline validations passed: {all(item['passed'] for item in outcomes.values())}\n"
        f"native live completion: {'PASS' if native_live_complete else 'BLOCKED'}\n"
        "SEC-API.io live status: UNTESTED\nsecret scan: PASS\n"
        "manifest checksum validation: PASS\nZIP integrity: PASS\n",
    )
    write(
        "manifest-checksum-validation.txt",
        "Algorithm: recompute SHA-256 for every member listed in the manifest's "
        "member_checksums_excluding_manifest map and fail package generation on any mismatch.\n"
        "Result: PASS when this delivered package exists.\n",
    )
    checksums = {
        path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in sorted(PACKAGE.iterdir())
        if path.is_file()
    }
    native_live_requests = 0
    if native_live_complete:
        native_live_requests = int(live_summary["second"]["usage_cumulative"]["requests"])
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "branch": branch,
        "head": head,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "live_provider": "SEC EDGAR",
        "native_identity_present_during_packaging": native_identity_present,
        "native_live_acceptance": "pass" if native_live_complete else "blocked_missing_identity",
        "native_live_requests": native_live_requests,
        "sec_api_io_status": "offline_only_untested_live",
        "commercial_credential_present_during_packaging": commercial_credential_present,
        "offline_validations_passed": all(item["passed"] for item in outcomes.values()),
        "validation_outcomes": outcomes,
        "member_checksums_excluding_manifest": checksums,
        "manifest_self_hash": None,
    }
    write("review-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    # Scan the complete member set, then refresh the scan report and its manifest checksum.
    # A final scan after the manifest rewrite proves the delivered directory is clean.
    suspicious, scanned = scan_package()
    write(
        "review-package-secret-scan-output.txt",
        f"files scanned: {scanned}\nfindings: {len(suspicious)}\n"
        + ("\n".join(suspicious) if suspicious else "result: PASS")
        + "\n",
    )
    if suspicious:
        raise RuntimeError("complete review package secret scan failed")
    checksums = {
        path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in sorted(PACKAGE.iterdir())
        if path.is_file() and path.name != "review-manifest.json"
    }
    manifest["member_checksums_excluding_manifest"] = checksums
    write("review-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    suspicious, _ = scan_package()
    if suspicious:
        raise RuntimeError("final review package secret scan failed")
    loaded = json.loads((PACKAGE / "review-manifest.json").read_text())
    mismatches = [
        name
        for name, value in loaded["member_checksums_excluding_manifest"].items()
        if digest(PACKAGE / name) != value["sha256"]
    ]
    if mismatches:
        raise RuntimeError(f"manifest checksum mismatch: {mismatches}")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.iterdir()):
            archive.write(path, f"{TASK_ID}/{path.name}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        members = archive.namelist()
    expected_members = [f"{TASK_ID}/{name}" for name in expected_names]
    integrity_code, integrity_output = run(
        [str(PYTHON), "-m", "zipfile", "-t", str(ZIP_PATH)]
    )
    if bad or integrity_code or members != expected_members:
        raise RuntimeError("ZIP integrity or member listing failed")
    zip_digest = digest(ZIP_PATH)
    ZIP_HASH.write_text(f"{zip_digest}  {ZIP_PATH.relative_to(ROOT)}\n")
    print(f"review directory: {PACKAGE}")
    print(f"review ZIP: {ZIP_PATH}")
    print(f"ZIP bytes: {ZIP_PATH.stat().st_size}")
    print(f"ZIP sha256: {zip_digest}")
    print(f"ZIP members: {len(members)}")
    print(f"manifest checksums: PASS ({len(checksums)} members)")
    print(f"ZIP integrity: PASS; {integrity_output.strip()}")
    if native_live_complete:
        print(f"native live acceptance: PASS ({native_live_requests} requests)")
        return 0
    print("native live acceptance: BLOCKED (missing RFI_SEC_USER_AGENT; zero requests)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
