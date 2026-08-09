#!/usr/bin/env python3
"""Emit deterministic Stage-1 ResearchReports from completed proving runs."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rfi.research import ResearchReportWriter, TranscriptScope

CASES = ("sentiment", "demand", "technology", "chronology", "insufficient")


def scope_from_run(run: dict[str, object]) -> TranscriptScope:
    """Read the exact orientation scope already retained in the governed trace."""
    for item in run["trace"]:  # type: ignore[index]
        if (
            item["action"] == "tool_result"
            and item["detail"].get("name") == "describe_corpus"
        ):
            value = item["detail"]["output"]["scope"]
            return TranscriptScope(
                firm_ids=tuple(value["firm_ids"]),
                canonical_artifact_ids=tuple(value["canonical_artifact_ids"]),
                source_effective_from=value.get("source_effective_from"),
                source_effective_through=value.get("source_effective_through"),
            )
    raise ValueError("governed run does not contain corpus orientation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.reports.mkdir(parents=True, exist_ok=True)
    writer = ResearchReportWriter()
    emitted = []
    for case in CASES:
        run = json.loads(
            (arguments.traces / f"{case}.json").read_text(encoding="utf-8")
        )
        report = writer.write_serialized(
            run,
            scope_from_run(run),
            f"evaluation/traces/{case}.json",
        )
        destination = arguments.reports / f"{case}.json"
        destination.write_text(
            json.dumps(asdict(report), indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        emitted.append({"case": case, "report_id": report.report_id})
    print(json.dumps({"result": "PASS", "reports": emitted}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
