#!/usr/bin/env python3
"""Fail closed if TASK-065's single explicit provider path regresses."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function_source(path: Path, class_name: str, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name == function_name:
                        return ast.get_source_segment(source, child) or ""
    raise RuntimeError(f"missing {class_name}.{function_name}")


def main() -> int:
    provider_files = tuple((ROOT / "src/rfi").rglob("*.py"))
    registry_count = sum(
        path.read_text(encoding="utf-8").count("class TranscriptProviderRegistry")
        for path in provider_files
    )
    injected = function_source(
        ROOT / "src/rfi/discovery.py",
        "EarningsTranscriptPullAdapter",
        "injected_trial",
    )
    provider_dispatch = function_source(
        ROOT / "src/rfi/discovery.py",
        "EarningsTranscriptPullAdapter",
        "_discover_provider",
    )
    workflow = function_source(
        ROOT / "src/rfi/pull/workflow.py",
        "PullWorkflow",
        "acquire_transcript_from_seed",
    )
    api = function_source(
        ROOT / "src/rfi/admin/server.py", "AdminHandler", "_api"
    )
    checks = {
        "one_registry": registry_count == 1,
        "injected_provider_resolves_in_registry": (
            "self._provider_registry.resolve(provider)" in injected
        ),
        "trial_receives_request_provider": "provider=provider" in injected,
        "no_injected_firm_provider_fallback": (
            'configuration.get("provider")' not in injected
        ),
        "workflow_propagates_provider": (
            "injected_trial(source, target, provider, starting_seed)" in workflow
        ),
        "workflow_has_no_url_inference": all(
            token not in workflow for token in ("urlsplit", "hostname", "stockanalysis")
        ),
        "registry_dispatches_trial_provider": (
            "self._provider_registry.create(" in provider_dispatch
            and "trial.provider" in provider_dispatch
        ),
        "http_has_no_provider_specific_branch": "stockanalysis" not in api,
        "http_rejects_query_parameters": (
            "transcript seed acquisition does not accept query parameters" in api
        ),
    }
    report = {"result": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
