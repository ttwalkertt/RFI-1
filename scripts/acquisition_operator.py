#!/usr/bin/env python3
"""Inspect, verify, rebuild, and demonstrate repository acquisition state."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition.demo import isolated_demo, render_demo  # noqa: E402
from rfi.acquisition.engine import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AdapterRegistry,
)
from rfi.acquisition.fixture_adapters import (  # noqa: E402
    FixtureCatalogAdapter,
    FixtureFeedAdapter,
    fixture_profiles,
)
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402


def render(value: Any) -> None:
    """Print deterministic JSON for operator and review use."""
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    """Run a repository acquisition operator command."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "demo",
            "sources",
            "artifacts",
            "history",
            "checkpoints",
            "index",
            "verify",
            "rebuild",
            "delete-derived",
            "adapters",
            "run-source",
            "run-all",
        ),
    )
    parser.add_argument("--state", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--run-key", default="operator")
    parser.add_argument("--fixture-state", default="default")
    parser.add_argument("--fail-candidate")
    parser.add_argument(
        "--fixture", type=Path, default=ROOT / "fixtures/acquisition/sample-document.txt"
    )
    arguments = parser.parse_args()
    if arguments.command == "demo":
        print(render_demo(isolated_demo(arguments.fixture)), end="")
        return 0
    if arguments.state is None:
        parser.error("--state is required for repository inspection commands")
    repository = AcquisitionRepository(arguments.state)
    if arguments.command in {"adapters", "run-source", "run-all"}:
        catalog = FixtureCatalogAdapter(
            ROOT / "fixtures/acquisition", "catalog-states.json", arguments.fixture_state
        )
        feed = FixtureFeedAdapter(ROOT / "fixtures/acquisition", "feed-pages.json")
        if arguments.fail_candidate:
            catalog.transient_retrieval_failures.add(arguments.fail_candidate)
            feed.transient_retrieval_failures.add(arguments.fail_candidate)
        registry = AdapterRegistry((catalog, feed))
        for profile in fixture_profiles():
            repository.register_source(profile)
        engine = AcquisitionEngine(repository, registry, lambda: "2026-04-01T00:00:00Z")
        kernel = AcquisitionKernel(engine, repository)
        if arguments.command == "adapters":
            render(registry.registrations())
            return 0
        if arguments.command == "run-source":
            if arguments.source is None:
                parser.error("--source is required for run-source")
            render(engine.run_source(arguments.source, arguments.run_key).to_dict())
            return 0
        render([item.to_dict() for item in kernel.run_enabled(arguments.run_key)])
        return 0
    commands = {
        "sources": repository.sources,
        "artifacts": repository.artifact_metadata,
        "history": repository.history,
        "checkpoints": repository.checkpoints,
        "index": repository.document_index,
        "verify": repository.verify_integrity,
    }
    if arguments.command in commands:
        render(commands[arguments.command]())
    elif arguments.command == "rebuild":
        render(asdict(repository.replay()))
    else:
        repository.delete_derived_state()
        render({"result": "PASS", "deleted": "derived acquisition state"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
