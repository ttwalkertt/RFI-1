#!/usr/bin/env python3
"""Generate the independently reviewable TASK-013 evidence package."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import yaml

from rfi.catalog_import import import_catalogs
from rfi.firms import FirmError, FirmRepository

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "TASK-013"
PACKAGE = ROOT / ".artifacts/review" / TASK_ID
ZIP_PATH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip"
ZIP_HASH = ROOT / ".artifacts/review" / f"{TASK_ID}-review.zip.sha256"
RFI = ROOT / ".venv/bin/rfi"
PYTHON = Path(sys.executable)


def write(name: str, content: str) -> None:
    """Write one UTF-8 review artifact."""
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(name: str, command: list[str]) -> dict[str, Any]:
    """Run and capture one verification command."""
    result = subprocess.run(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    write(
        f"validation/{name}.txt",
        f"$ {' '.join(command)}\n{result.stdout}exit_code: {result.returncode}\n",
    )
    return {"name": name, "command": command, "exit_code": result.returncode}


def git(*arguments: str) -> str:
    """Run one read-only Git query."""
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def changed_files(base: str) -> list[str]:
    """Return tracked and untracked task files in deterministic order."""
    tracked = git("diff", "--name-only", base, "--", ".").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def complete_patch(base: str) -> str:
    """Render the cumulative patch, including untracked files."""
    parts = [git("diff", "--binary", base, "--", ".")]
    for relative in git("ls-files", "--others", "--exclude-standard").splitlines():
        result = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"cannot render untracked patch: {relative}")
        parts.append(result.stdout)
    return "\n".join(parts)


def valid_catalog(template: str, multiple: bool = False) -> dict[str, Any]:
    """Replace printed placeholders with valid representative firms."""
    value = yaml.safe_load(template)
    value["catalog"]["prepared_on"] = "2026-07-17"
    value["research"]["reviewed_on"] = "2026-07-17"
    value["research"]["sources"][0]["accessed_on"] = "2026-07-17"
    firm = value["firms"][0]
    firm["firm_id"] = "review-external"
    firm["canonical_name"] = "Review External"
    firm["valid_from"] = "2020-01-01"
    firm["identifiers"][0]["value"] = "RVW"
    firm["domains"] = ["review-external.example.com"]
    firm["relevance"] = 90
    if multiple:
        second = copy.deepcopy(firm)
        second["firm_id"] = "review-secondary"
        second["canonical_name"] = "Review Secondary"
        second["identifiers"][0]["value"] = "RVW2"
        second["domains"] = ["review-secondary.example.com"]
        second["relevance"] = 25
        value["firms"].append(second)
    return value


def atomic_failure_proof(root: Path, template: str) -> dict[str, Any]:
    """Inject a failure after one artifact write and record exact rollback evidence."""
    state = root / "atomic-state"
    init = subprocess.run(
        [str(RFI), "init", "--state", str(state)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if init.returncode:
        raise RuntimeError(init.stdout)
    catalog = root / "atomic.yaml"
    catalog.write_text(
        yaml.safe_dump(valid_catalog(template, multiple=True), sort_keys=False),
        encoding="utf-8",
    )
    repository = FirmRepository.open(state / "firm-catalog")
    pointer = repository.pointer.read_bytes()
    artifacts = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repository.revisions_root.iterdir()
    }
    error = ""
    try:
        import_catalogs((catalog,), repository, fail_after_revision_count=1)
    except FirmError as caught:
        error = str(caught)
    after_artifacts = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repository.revisions_root.iterdir()
    }
    proof = {
        "injected_error": error,
        "catalog_unchanged": repository.pointer.read_bytes() == pointer,
        "revision_artifacts_unchanged": after_artifacts == artifacts,
        "no_imported_firms_visible": repository.lookup() == (),
        "repository_valid": FirmRepository.open(repository.root).verify()["result"] == "PASS",
    }
    proof["result"] = "PASS" if all(
        value is True for key, value in proof.items() if key != "injected_error"
    ) and "injected batch persistence failure" in error else "FAIL"
    write("walkthrough/atomic-persistence-failure.json",
          json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def walkthrough() -> list[dict[str, Any]]:
    """Capture schema, built-in, successful, repeat, parity, and failure behavior."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state = root / "state"
        template_result = subprocess.run(
            [str(RFI), "seed", "--print-schema"], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        write(
            "walkthrough/canonical-template.yaml",
            template_result.stdout,
        )
        parsed = yaml.safe_load(template_result.stdout)
        write(
            "walkthrough/template-parse.json",
            json.dumps(
                {
                    "valid_yaml": isinstance(parsed, dict),
                    "schema_version": parsed["schema_version"],
                },
                indent=2, sort_keys=True,
            ) + "\n",
        )
        catalog = root / "catalog.yaml"
        catalog.write_text(
            yaml.safe_dump(valid_catalog(template_result.stdout, multiple=True), sort_keys=False),
            encoding="utf-8",
        )
        results = [
            run("init", [str(RFI), "init", "--state", str(state)]),
            run("built-in-seed", [str(RFI), "seed", "--state", str(state)]),
            run(
                "long-file-import",
                [str(RFI), "seed", "--state", str(state), "--file", str(catalog)],
            ),
            run(
                "short-file-idempotent",
                [str(RFI), "seed", "--state", str(state), "-f", str(catalog)],
            ),
            run("installed-template", [str(RFI), "seed", "--print-schema"]),
            run("module-template", [str(PYTHON), "-m", "rfi", "seed", "--print-schema"]),
        ]
        invalid = root / "invalid.yaml"
        invalid.write_text("firms: [\n", encoding="utf-8")
        results.append(run(
            "malformed-yaml",
            [str(RFI), "seed", "--state", str(state), "-f", str(invalid)],
        ))
        invalid_relevance = root / "invalid-relevance.yaml"
        invalid_value = valid_catalog(template_result.stdout)
        invalid_value["firms"][0]["relevance"] = "core"
        invalid_relevance.write_text(
            yaml.safe_dump(invalid_value, sort_keys=False), encoding="utf-8"
        )
        pointer_path = state / "firm-catalog/catalog.json"
        relevance_pointer = pointer_path.read_bytes()
        relevance_artifacts = sorted(
            path.name for path in (state / "firm-catalog/revisions").iterdir()
        )
        relevance_result = run(
            "invalid-relevance",
            [str(RFI), "seed", "--state", str(state), "-f", str(invalid_relevance)],
        )
        results.append(relevance_result)
        write(
            "walkthrough/invalid-relevance-no-mutation.json",
            json.dumps(
                {
                    "exit_code": relevance_result["exit_code"],
                    "catalog_unchanged": pointer_path.read_bytes() == relevance_pointer,
                    "revision_artifacts_unchanged": sorted(
                        path.name for path in (state / "firm-catalog/revisions").iterdir()
                    ) == relevance_artifacts,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
        )
        atomic = atomic_failure_proof(root, template_result.stdout)
        results.append({
            "name": "atomic-persistence-failure",
            "command": ["deterministic repository failure injection after one artifact"],
            "exit_code": 0 if atomic["result"] == "PASS" else 1,
        })
        return results


def package(metadata: dict[str, Any]) -> None:
    """Manifest, archive, and read back the complete evidence package."""
    records = []
    for path in sorted(PACKAGE.rglob("*")):
        if path.is_file():
            records.append({
                "path": path.relative_to(PACKAGE).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            })
    write("manifest.json", json.dumps({**metadata, "files": records}, indent=2,
                                      sort_keys=True) + "\n")
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, f"{TASK_ID}/{path.relative_to(PACKAGE).as_posix()}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("review ZIP integrity failed")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_HASH.write_text(f"{digest}  {ZIP_PATH.name}\n", encoding="utf-8")


def main() -> int:
    """Run TASK-013 evidence capture and complete project validation."""
    if not RFI.is_file():
        raise RuntimeError("installed .venv/bin/rfi is missing; install the repository first")
    shutil.rmtree(PACKAGE, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    base = git("merge-base", "main", "HEAD").strip()
    flow = walkthrough()
    validations = [
        run("focused-task013", [str(PYTHON), "-m", "unittest", "tests.test_task013", "-v"]),
        run("seed-regression-task012", [str(PYTHON), "-m", "unittest",
                                        "tests.test_task012", "-v"]),
        run("complete-project", ["make", "validate"]),
    ]
    files = changed_files(base)
    write("changed-files.txt", "\n".join(files) + "\n")
    write("task.patch", complete_patch(base))
    write("repository-status.txt", git("status", "--short", "--branch"))
    write(
        "implementation-and-design.md",
        "# Implementation and design\n\nThe CLI owns arguments and output; `catalog_import` owns "
        "one recursive field registry, safe YAML decoding, validation, templates, and "
        "deterministic "
        "batch orchestration; the existing firm repository remains the persistence authority. The "
        "same fields render and decode the template. Every file and planned conflict is validated "
        "before create calls. Revisions stage before one canonical pointer publication, and "
        "staged artifacts roll back on failure. Relevance is a plain finite 0–100 number, "
        "defaulting to 0, with descending sort and minimum filtering. The importable-type "
        "registry is the future extension boundary.\n",
    )
    write(
        "limitations.md",
        "# Assumptions and limitations\n\nSchema version 1 imports target firms only. Catalog and "
        "research metadata are validated external context and are not persisted. Imports are local "
        "and create-only. The batch transaction covers new target firms in one import invocation; "
        "it is not a cross-repository transaction with starter concept seeding.\n",
    )
    expected_failures = {"malformed-yaml", "invalid-relevance"}
    failures = [
        item["name"] for item in flow
        if (item["name"] in expected_failures) == (item["exit_code"] == 0)
    ]
    failures.extend(item["name"] for item in validations if item["exit_code"] != 0)
    installed = (PACKAGE / "validation/installed-template.txt").read_text(encoding="utf-8")
    module = (PACKAGE / "validation/module-template.txt").read_text(encoding="utf-8")
    if installed.split("\n", 1)[1].rsplit("exit_code:", 1)[0] != \
            module.split("\n", 1)[1].rsplit("exit_code:", 1)[0]:
        failures.append("entry-point-parity")
    metadata = {
        "task": TASK_ID,
        "base": base,
        "branch": git("branch", "--show-current").strip(),
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "walkthrough": flow,
        "validations": validations,
    }
    package(metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    print(f"package: {PACKAGE}\nzip: {ZIP_PATH}\nchecksum: {ZIP_HASH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
