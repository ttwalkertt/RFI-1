#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-067 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-067"
ZIP_PATH = ROOT / ".artifacts/review/TASK-067-review.zip"
VALIDATION = ROOT / ".artifacts/task067-validation"
REPORT_PATH = ROOT / ".artifacts/review/TASK-067-review-report.json"


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
    result = subprocess.run(
        command, cwd=ROOT, env={**os.environ, "PYTHONPATH": "src"}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False,
    )
    target = VALIDATION / f"{name}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"$ {' '.join(command)}\n\n{result.stdout}\nexit_code: {result.returncode}\n",
        encoding="utf-8",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def generate(base: str | None) -> int:
    required = [
        VALIDATION / "live-smoke.json",
        VALIDATION / "screenshots/01-feeds-overview.jpg",
        VALIDATION / "screenshots/02-feed-editor.jpg",
        VALIDATION / "screenshots/03-delete-confirmation.jpg",
        VALIDATION / "screenshots/04-history-expanded-json.jpg",
        VALIDATION / "screenshots/05-unavailable-queue.jpg",
        VALIDATION / "screenshots/06-manual-fulfillment-flow.jpg",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("required TASK-067 review evidence is absent: " + ", ".join(missing))
    outcomes = [
        run("focused", ["make", "task067-test"]),
        run(
            "artifact-browser-regressions",
            [".venv/bin/python", "-m", "unittest", "tests.test_task018",
             "tests.test_task067", "-v"],
        ),
        run("deterministic-evidence", [".venv/bin/python", "scripts/task067_review_evidence.py"]),
        run(
            "acquisition-persistence-regressions",
            [".venv/bin/python", "-m", "unittest", "tests.test_task015",
             "tests.test_task019", "tests.test_task021", "tests.test_task047", "-v"],
        ),
        run(
            "live-smoke-evidence",
            [".venv/bin/python", "scripts/task067_live_smoke.py", "--verify",
             str(VALIDATION / "live-smoke.json")],
        ),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-067 validations failed")
    copied = [
        ("task-ticket.md", ROOT / "tasks/TASK-067-repository-owned-feed-sources.md"),
        ("completion/architectural-review.md", ROOT / "docs/TASK-067-review.md"),
        ("evidence/task067-tests.py", ROOT / "tests/test_task067.py"),
        ("evidence/task018-tests.py", ROOT / "tests/test_task018.py"),
        ("evidence/artifact-contracts.py", ROOT / "src/rfi/artifacts/contracts.py"),
        ("evidence/artifact-query-service.py", ROOT / "src/rfi/artifacts/service.py"),
        ("evidence/artifact-browser.html", ROOT / "src/rfi/admin/artifact_browser.html"),
        ("evidence/admin-server.py", ROOT / "src/rfi/admin/server.py"),
        ("evidence/feed-contracts.py", ROOT / "src/rfi/feeds/contracts.py"),
        ("evidence/feed-parser.py", ROOT / "src/rfi/feeds/parser.py"),
        ("evidence/feed-repository.py", ROOT / "src/rfi/feeds/repository.py"),
        ("evidence/feed-service.py", ROOT / "src/rfi/feeds/service.py"),
        ("evidence/feed-adapter.py", ROOT / "src/rfi/feeds/adapter.py"),
        ("evidence/feed-transport.py", ROOT / "src/rfi/feeds/transport.py"),
        ("evidence/feeds-operator.html", ROOT / "src/rfi/admin/feeds.html"),
        ("evidence/operator-documentation.md", ROOT / "docs/operator-guide.md"),
        ("evidence/live-smoke.py", ROOT / "scripts/task067_live_smoke.py"),
        ("evidence/review-evidence.py", ROOT / "scripts/task067_review_evidence.py"),
        ("evidence/fixture-readme.md", ROOT / "fixtures/feeds/README.md"),
        *((f"evidence/fixtures/{path.name}", path)
          for path in sorted((ROOT / "fixtures/feeds").iterdir()) if path.is_file()),
        *((f"validation/{name}.txt", VALIDATION / f"{name}.txt")
          for name in ("focused", "artifact-browser-regressions", "deterministic-evidence",
                       "acquisition-persistence-regressions", "live-smoke-evidence",
                       "diff-check", "full-validation")),
        *((f"validation/{name}", VALIDATION / name) for name in (
            "live-smoke.json", "cli-human.txt", "cli-json.json", "cli-json-exit.txt",
            "cron-example.txt", "api-examples.json", "aggregate.rss", "feed-run.json",
            "run-summary-outcomes.json",
            "artifact-browser-repair.json",
            "restart-persistence.json", "startup-recovery.json", "candidate-preview.json",
            "manual-fulfillment.json", "schema-evidence.json",
            "ui-state-summary.json", "results.json",
        )),
        *((f"validation/screenshots/{path.name}", path)
          for path in sorted((VALIDATION / "screenshots").glob("*.jpg"))),
    ]
    build_package(
        root=ROOT, task_id="TASK-067", package=PACKAGE, zip_path=ZIP_PATH,
        copied_members=copied, base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-067")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_PATH.with_suffix(".zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8"
    )
    package_report = {**report, "zip": str(ZIP_PATH), "sha256": digest}
    REPORT_PATH.write_text(
        json.dumps(package_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(package_report, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(
            verify_package(args.verify, expected_task_id="TASK-067"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
