#!/usr/bin/env python3
"""Produce repository-grounded TASK-068 architecture inventory evidence."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

from rfi.cli import parser as cli_parser

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src/rfi"
DOWNSTREAM_POCS = {
    "rfi.source_objects",
    "rfi.knowledge",
    "rfi.retrieval",
    "rfi.intelligence",
    "rfi.workspace",
}
COMPOSITION_ROOTS = (
    ROOT / "src/rfi/cli.py",
    ROOT / "src/rfi/admin/server.py",
    ROOT / "src/rfi/pull/__init__.py",
)


def imported_modules(path: Path) -> set[str]:
    """Return absolute module names imported by one Python source."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def class_names(path: Path) -> list[str]:
    """Return top-level public class names from a contract file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    ]


def test_count(path: Path) -> int:
    """Count unittest-style test methods without importing the test module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def cli_commands() -> list[str]:
    """Read the stable top-level command names from the public parser."""
    command_parser = cli_parser()
    for action in command_parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and choices:
            return sorted(choices)
    raise RuntimeError("stable CLI command hierarchy is unavailable")


def identifier_collisions(paths: list[Path], pattern: str) -> dict[str, list[str]]:
    """Return filename-qualified numeric identifier collisions."""
    values: dict[str, list[str]] = {}
    for path in paths:
        match = re.search(pattern, path.name, re.IGNORECASE)
        if match:
            values.setdefault(match.group(1).upper(), []).append(path.name)
    return {
        key: sorted(items)
        for key, items in sorted(values.items())
        if len(items) > 1
    }


def inventory() -> dict[str, Any]:
    """Build the factual capability and composition inventory."""
    contract_files = sorted(SOURCE_ROOT.glob("*/contracts.py"))
    contracts = {
        path.parent.name: class_names(path)
        for path in contract_files
    }
    composition_imports = {
        path.relative_to(ROOT).as_posix(): sorted(imported_modules(path))
        for path in COMPOSITION_ROOTS
    }
    composed_modules = set().union(*(set(items) for items in composition_imports.values()))
    unexpected_downstream = sorted(
        module
        for module in composed_modules
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in DOWNSTREAM_POCS
        )
    )
    focused_tests = {
        f"TASK-{number}": test_count(ROOT / f"tests/test_task{number}.py")
        for number in ("005", "006", "007", "008", "067")
    }
    admin_source = (ROOT / "src/rfi/admin/server.py").read_text(encoding="utf-8")
    pull_source = (ROOT / "src/rfi/pull/__init__.py").read_text(encoding="utf-8")
    proof_scripts = {
        "005": (ROOT / "scripts/task005_operator.py").is_file(),
        "006": (ROOT / "scripts/task006_browser.py").is_file(),
        "007": (ROOT / "scripts/task007_operator.py").is_file(),
        "008": (ROOT / "scripts/task008_workspace.py").is_file(),
    }
    assertions = {
        "current_state_exists": (ROOT / "docs/current-state.md").is_file(),
        "public_contract_packages_present": len(contracts) >= 14,
        "stable_cli_present": len(cli_commands()) >= 10,
        "admin_composes_feeds": "FeedService(state)" in admin_source,
        "admin_composes_artifact_browser": "ArtifactQueryService(" in admin_source,
        "pull_composes_feeds": "FeedService(state)" in pull_source,
        "pull_registers_wdc_adapter": "WdcBusinessWirePressReleaseAdapter" in pull_source,
        "downstream_pocs_absent_from_product_composition": not unexpected_downstream,
        "downstream_proof_scripts_present": all(proof_scripts.values()),
        "downstream_focused_tests_present": all(value > 0 for value in focused_tests.values()),
    }
    return {
        "schema_version": 1,
        "public_contracts": {
            name: {"classes": names, "class_count": len(names)}
            for name, names in sorted(contracts.items())
        },
        "stable_cli_commands": cli_commands(),
        "admin_page_routes": sorted(set(re.findall(
            r'path == "(/(?:firms|source-profiles|pull-sources|feeds|'
            r'linux-mailing-lists|artifacts|streams))"',
            admin_source,
        ))),
        "composition_root_imports": composition_imports,
        "unexpected_downstream_composition_imports": unexpected_downstream,
        "downstream_poc_proof_scripts": proof_scripts,
        "focused_test_counts": focused_tests,
        "historical_identifier_collisions": {
            "adrs": identifier_collisions(
                list((ROOT / "docs/decisions").glob("*.md")), r"^(\d{4})-"
            ),
            "tasks": identifier_collisions(
                list((ROOT / "tasks").glob("*.md")), r"^TASK-(\d{3})"
            ),
        },
        "assertions": assertions,
        "result": "PASS" if all(assertions.values()) else "FAIL",
    }


def main() -> int:
    """Write or print the inventory and fail when a documented boundary is false."""
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--output", type=Path)
    arguments = argument_parser.parse_args()
    value = inventory()
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if value["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
