#!/usr/bin/env python3
"""Validate and summarize the preserved TASK-073 experiment evidence."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.mcp.contracts import TraceContext
from rfi.mcp.server import compose_surface

CASES = ("sentiment", "demand", "technology", "chronology", "insufficient")
SEGMENT_URI = re.compile(r"rfi://transcript-segments/(transcript-segment-[a-f0-9]+)")


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _trace_summary(experiment: Path, case: str) -> dict[str, Any]:
    rows = _rows(experiment / "mcp" / f"{case}.jsonl")
    answer = (experiment / "answers" / f"{case}.md").read_text(encoding="utf-8")
    cited = set(SEGMENT_URI.findall(answer))
    exact = {
        segment_id
        for row in rows
        if row["capability"] == "resource:transcript-segments"
        for segment_id in row["referenced_segment_ids"]
    }
    exact_digests = {
        segment_id: tuple(row.get("range_digests", {}).values())
        for row in rows
        if row["capability"] == "resource:transcript-segments"
        and row.get("range_digests")
        for segment_id in row["referenced_segment_ids"]
    }
    failures = [row["error"] for row in rows if row.get("error")]
    if not cited.issubset(exact) or not cited.issubset(exact_digests):
        raise ValueError(f"{case}: final answer cites a segment without an exact verified read")
    generations = {
        row["access_generation"]["generation_id"]
        for row in rows
        if row.get("access_generation")
    }
    snapshots = {row["repository_snapshot"] for row in rows}
    if len(generations) != 1 or len(snapshots) != 1:
        raise ValueError(f"{case}: trace mixed repository or access generations")
    return {
        "case": case,
        "requests": len(rows),
        "capabilities": dict(collections.Counter(row["capability"] for row in rows)),
        "outcomes": dict(collections.Counter(row["outcome"] for row in rows)),
        "runtime_visible_failures": failures,
        "search_requests": sum(
            row["capability"] == "search_transcript_segments" for row in rows
        ),
        "exact_segment_reads": sum(
            row["capability"] == "resource:transcript-segments" for row in rows
        ),
        "artifact_byte_reads": sum(
            row["capability"] == "read_artifact_bytes" for row in rows
        ),
        "answer_segment_uris": sorted(cited),
        "answer_segment_uri_count": len(cited),
        "all_answer_segment_uris_exactly_verified": cited.issubset(exact_digests),
        "unique_candidate_or_exact_segments": len({
            segment_id for row in rows for segment_id in row["referenced_segment_ids"]
        }),
        "response_bytes": sum(row.get("response_bytes", 0) for row in rows),
        "generation_id": generations.pop(),
        "repository_snapshot": snapshots.pop(),
    }


def _codex_summary(experiment: Path, case: str) -> dict[str, Any]:
    rows = _rows(experiment / "codex" / f"{case}.jsonl")
    usage = next(row["usage"] for row in reversed(rows) if row["type"] == "turn.completed")
    completed = [
        row["item"]
        for row in rows
        if row["type"] == "item.completed" and row["item"].get("type") == "mcp_tool_call"
    ]
    return {
        "case": case,
        "events": len(rows),
        "completed_mcp_calls": len(completed),
        "failed_mcp_calls": sum(item.get("status") == "failed" for item in completed),
        "usage": usage,
        "event_stream_sha256": hashlib.sha256(
            (experiment / "codex" / f"{case}.jsonl").read_bytes()
        ).hexdigest(),
        "answer_sha256": hashlib.sha256(
            (experiment / "answers" / f"{case}.md").read_bytes()
        ).hexdigest(),
    }


def _corpus_inventory(state: Path) -> dict[str, Any]:
    surface = compose_surface(state, None)
    try:
        trace = TraceContext()
        page = surface.access.corpus(limit=100, cursor=None, trace=trace)
        identity = surface.access.identity()
        return {
            "repository_snapshot": identity.authority_snapshot,
            "generation_id": identity.generation_id,
            "health": identity.health.value,
            "eligible_document_count": identity.eligible_document_count,
            "indexed_document_count": identity.indexed_document_count,
            "indexed_segment_count": identity.indexed_segment_count,
            "build_outcome": identity.build_outcome.value,
            "build_diagnostics": [asdict(item) for item in identity.diagnostics],
            "inventory": page["inventory"],
            "metadata_gaps": page["metadata_gaps"],
            "documents": page["documents"],
        }
    finally:
        surface.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--task071", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = json.loads(
        (arguments.experiment / "manifest.json").read_text(encoding="utf-8")
    )
    if [item["case"] for item in manifest["cases"]] != list(CASES):
        raise ValueError("experiment does not contain the five required cases in ticket order")
    if manifest["procedural_prompt_material"] is not None:
        raise ValueError("experiment introduced procedural prompt material")
    if not manifest["repository_unchanged"]:
        raise ValueError("experiment changed retained repository authority")
    if any(item["exit_code"] for item in manifest["cases"]):
        raise ValueError("one or more Codex Work cases did not finish")
    corpus = _corpus_inventory(arguments.state)
    task071_corpus = json.loads(
        (arguments.task071 / "corpus.json").read_text(encoding="utf-8")
    )
    parity = {
        "repository_snapshot": corpus["repository_snapshot"]
        == task071_corpus["repository_snapshot"],
        "document_count": corpus["indexed_document_count"]
        == len(task071_corpus["documents"]),
        "segment_count": corpus["indexed_segment_count"]
        == task071_corpus["segment_count"],
        "date_from": corpus["inventory"]["date_from"] == task071_corpus["date_from"],
        "date_through": corpus["inventory"]["date_through"]
        == task071_corpus["date_through"],
    }
    if not all(parity.values()):
        raise ValueError(f"TASK-071 corpus parity failed: {parity}")
    summary = {
        "result": "PASS",
        "meaning": "preserved experiment integrity and corpus parity; not analytical acceptance",
        "manifest": manifest,
        "corpus_parity": parity,
        "corpus": corpus,
        "mcp_cases": [_trace_summary(arguments.experiment, case) for case in CASES],
        "codex_cases": [_codex_summary(arguments.experiment, case) for case in CASES],
        "independent_analysis_reference": {
            "available_in_repository_or_retained_task_evidence": False,
            "effect": (
                "No independent-analysis artifact or locator is present; TASK-071 is the only "
                "reproducible comparison baseline in this checkout."
            ),
        },
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "experiment-evidence-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (arguments.output / "corpus-inventory.json").write_text(
        json.dumps(corpus, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
