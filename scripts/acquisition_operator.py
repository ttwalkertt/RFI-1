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
        ),
    )
    parser.add_argument("--state", type=Path)
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
