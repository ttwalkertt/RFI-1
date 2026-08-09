#!/usr/bin/env python3
"""Headless retained-transcript corpus inspection and investigation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.acquisition import AcquisitionRepository
from rfi.artifacts import ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.research import (
    ModelBudget,
    OpenAIResponsesInvestigator,
    TranscriptInvestigator,
    TranscriptKnowledgeAccess,
    TranscriptScope,
)
from rfi.source_profiles import load_canonical_template


def access(arguments: argparse.Namespace) -> TranscriptKnowledgeAccess:
    """Compose public repository readers into the transcript IQA."""
    state = arguments.state
    artifacts = ArtifactQueryService(
        AcquisitionRepository(state / "acquisition"),
        FirmRepository.open(state / "firm-catalog"),
        load_canonical_template(),
    )
    scope = TranscriptScope(
        tuple(arguments.firm or ("seagate",)),
        tuple(arguments.artifact_type or (
            "earnings_transcript", "management_transcript",
        )),
        arguments.date_from,
        arguments.date_through,
    )
    return TranscriptKnowledgeAccess(artifacts, scope)


def render(value: Any, destination: Path | None) -> None:
    """Write stable JSON to stdout or one explicit evidence path."""
    text = json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    if destination is None:
        print(text, end="")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print(destination)


def main() -> int:
    """Run the bounded corpus or investigation command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("corpus", "ask"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--firm", action="append")
    parser.add_argument(
        "--artifact-type",
        action="append",
    )
    parser.add_argument("--date-from")
    parser.add_argument("--date-through")
    parser.add_argument("--question")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-tool-calls", type=int, default=12)
    parser.add_argument("--max-model-turns", type=int, default=10)
    parser.add_argument("--max-output-tokens", type=int, default=1_800)
    parser.add_argument("--max-tool-output-chars", type=int, default=75_000)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    iqa = access(arguments)
    try:
        if arguments.command == "corpus":
            render(asdict(iqa.describe_corpus()), arguments.output)
            return 0
        if not arguments.question:
            parser.error("ask requires --question")
        budget = ModelBudget(
            arguments.max_tool_calls,
            arguments.max_model_turns,
            arguments.max_output_tokens,
            arguments.max_tool_output_chars,
        )
        model = OpenAIResponsesInvestigator(arguments.model)
        run = TranscriptInvestigator(iqa, model, budget).investigate(arguments.question)
        render(asdict(run), arguments.output)
        return 0
    finally:
        iqa.close()


if __name__ == "__main__":
    raise SystemExit(main())
