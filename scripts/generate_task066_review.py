#!/usr/bin/env python3
"""Generate or independently verify the commit-aware TASK-066 review package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from review_package import build_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".artifacts/review/TASK-066"
ZIP_PATH = ROOT / ".artifacts/review/TASK-066-review.zip"
VALIDATION = ROOT / ".artifacts/task066-validation"
REPORT_PATH = ROOT / ".artifacts/review/TASK-066-review-report.json"


def run(name: str, command: list[str], timeout: int = 1800) -> dict[str, object]:
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


def generate(base: str | None) -> int:
    live_path = VALIDATION / "live-validation.json"
    transport_path = VALIDATION / "transport-viability.json"
    if not live_path.is_file():
        raise RuntimeError(
            "capture bounded live evidence before package generation with "
            "scripts/task066_live_validation.py"
        )
    if not transport_path.is_file():
        raise RuntimeError(
            "capture production transport evidence before package generation with "
            "scripts/task066_transport_viability.py"
        )
    outcomes = [
        run("focused", ["make", "task066-test"]),
        run(
            "configuration-regressions",
            [
                ".venv/bin/python", "-m", "unittest", "tests.test_task041",
                "tests.test_task054", "-v",
            ],
        ),
        run(
            "acquisition-regressions",
            [
                ".venv/bin/python", "-m", "unittest", "tests.test_task014",
                "tests.test_task015", "tests.test_task019",
                "tests.test_task047", "tests.test_task059", "tests.test_task064", "-v",
            ],
        ),
        run(
            "historical-browser-capture-evidence",
            [
                ".venv/bin/python", "scripts/task066_live_validation.py",
                "--verify", str(live_path),
            ],
        ),
        run(
            "direct-transport-viability-evidence",
            [
                ".venv/bin/python", "scripts/task066_transport_viability.py",
                "--verify", str(transport_path),
            ],
        ),
        run("diff-check", ["git", "diff", "--check"]),
        run("full-validation", ["make", "validate"], timeout=3600),
    ]
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "results.json").write_text(
        json.dumps(outcomes, indent=2) + "\n", encoding="utf-8"
    )
    if any(item["exit_code"] for item in outcomes):
        raise RuntimeError("one or more TASK-066 validations failed")
    names = tuple(str(item["name"]) for item in outcomes)
    copied = [
        (
            "task-ticket.md",
            ROOT / "tasks/TASK-066-Western-Digital-BusinessWire-Press-Release-Adapter.md",
        ),
        ("completion/architectural-review.md", ROOT / "docs/TASK-066-review.md"),
        ("evidence/task066-tests.py", ROOT / "tests/test_task066.py"),
        (
            "evidence/wdc-businesswire-adapter.py",
            ROOT / "src/rfi/acquisition/wdc_press_release.py",
        ),
        ("evidence/acquisition-contracts.py", ROOT / "src/rfi/acquisition/contracts.py"),
        ("evidence/acquisition-engine.py", ROOT / "src/rfi/acquisition/engine.py"),
        ("evidence/acquisition-repository.py", ROOT / "src/rfi/acquisition/repository.py"),
        ("evidence/pull-workflow.py", ROOT / "src/rfi/pull/workflow.py"),
        (
            "evidence/source-profile-repository.py",
            ROOT / "src/rfi/source_profiles/repository.py",
        ),
        (
            "evidence/firm-config-example.json",
            ROOT / "docs/western-digital.firm-config.example.json",
        ),
        (
            "evidence/firm-config-schema.json",
            ROOT / "src/rfi/resources/firm-config-v1.schema.json",
        ),
        ("evidence/live-validator.py", ROOT / "scripts/task066_live_validation.py"),
        (
            "evidence/transport-viability-probe.py",
            ROOT / "scripts/task066_transport_viability.py",
        ),
        ("evidence/acquisition-documentation.md", ROOT / "docs/acquisition-engine.md"),
        ("evidence/operator-documentation.md", ROOT / "docs/operator-guide.md"),
        ("evidence/fixture-readme.md", ROOT / "fixtures/press-releases/README.md"),
        *(
            (f"evidence/fixtures/{path.name}", path)
            for path in sorted((ROOT / "fixtures/press-releases").glob("*.html"))
        ),
        *((f"validation/{name}.txt", VALIDATION / f"{name}.txt") for name in names),
        ("validation/historical-browser-capture-validation.json", live_path),
        ("validation/transport-viability.json", transport_path),
        *(
            (f"validation/transport-raw/{path.name}", path)
            for path in sorted((VALIDATION / "transport-raw").glob("*"))
            if path.suffix in {".body", ".headers"}
        ),
        ("validation/results.json", VALIDATION / "results.json"),
    ]
    build_package(
        root=ROOT,
        task_id="TASK-066",
        package=PACKAGE,
        zip_path=ZIP_PATH,
        copied_members=copied,
        base_ref=base,
    )
    report = verify_package(ZIP_PATH, expected_task_id="TASK-066")
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--base")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(
            verify_package(args.verify, expected_task_id="TASK-066"), indent=2
        ))
        return 0
    return generate(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
