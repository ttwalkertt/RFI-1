#!/usr/bin/env python3
"""Emit deterministic TASK-057 failure and traversal reproduction evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from rfi.acquisition import EarningsTranscriptHttpResponse, SourceProfile
from rfi.discovery import (
    DiscoveryPolicy, DiscoveryPolicyCatalog, DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".artifacts/task057-validation/reproduction.json"
HINT = "https://ir.example.com/transcripts/"


class Search:
    endpoint = "https://search.example/results"

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        del query, limit
        return DiscoverySearchResponse((), 1)


class Transport:
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse | Exception]) -> None:
        self.responses = responses

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def policy(**changes: int) -> DiscoveryPolicy:
    return replace(DiscoveryPolicy(2, 8, 20, 3, 30, 8, 2_000_000, 60, 40, 10), **changes)


def html(url: str, body: str, status: int = 200) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, status, "text/html", f"<html>{body}</html>".encode()
    )


def run(
    responses: dict[str, EarningsTranscriptHttpResponse | Exception],
    selected: DiscoveryPolicy | None = None,
) -> dict[str, object]:
    adapter = EarningsTranscriptPullAdapter(
        DiscoveryPolicyCatalog({"standard": selected or policy()}, "standard"),
        Search(), Transport(responses), lambda: "2026-08-01T00:00:00Z",
    )
    page = adapter.discover(SourceProfile(
        "source-a", "Firm A transcripts", True, "earnings_transcript",
        {"mode": "discovery", "discovery_hints": [HINT],
         "discovery_class": "standard"},
        {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
    ), None)
    keys = (
        "primary_classification", "operator_summary", "final_coverage_classification",
        "raw_hyperlinks", "normalized_unique_hyperlinks", "eligible_hyperlinks",
        "queue_admitted_count", "visited_count", "candidate_admitted_count",
        "candidate_evaluated_count", "rejection_counts", "cycle_counts",
        "discovery_failure_counts", "candidate_retrieval_failure_counts",
        "validation_failure_counts", "bounds_exhausted", "exhausted_budget",
        "anchor_to_hint_fallthrough", "hint_to_traversal_fallthrough",
        "representative_rejections", "top_ranked_candidates",
    )
    return {key: page.diagnostics.get(key) for key in keys}


def reproduction_cases() -> dict[str, dict[str, object]]:
    """Build the eight stable cases without writing evidence as a side effect."""
    candidate = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
    second = "https://ir.example.com/2026-07-30-earnings-call-transcript.html"
    generic = "".join(
        f"<a href='/transcripts/archive-{index}'>Transcript archive</a>" for index in range(25)
    )
    return {
        "many_raw_zero_eligible": run({
            HINT: html(HINT, "".join(f"<a href='/legal/{i}'>Legal</a>" for i in range(50)))
        }),
        "configured_hint_timeout": run({HINT: TimeoutError("timed out")}),
        "configured_hint_http_failure": run({HINT: html(HINT, "", 403)}),
        "discovered_candidate_unavailable": run({
            HINT: html(HINT, f"<a href='{candidate}'>Q1 earnings call transcript</a>"),
            candidate: html(candidate, "", 404),
        }),
        "cyclic_navigation_graph": run({
            HINT: html(HINT, "<a href='/transcripts/a'>Transcript archive</a>"),
            "https://ir.example.com/transcripts/a": html(
                "https://ir.example.com/transcripts/a",
                "<a href='/transcripts/b'>Transcript archive</a>",
            ),
            "https://ir.example.com/transcripts/b": html(
                "https://ir.example.com/transcripts/b",
                f"<a href='{HINT}'>Transcript archive</a>",
            ),
        }),
        "relevant_after_generic_links": run({
            HINT: html(HINT, generic +
                       f"<a href='{candidate}'>Q1 2026 earnings call transcript</a>"),
            candidate: html(
                candidate, "Firm A quarterly earnings call transcript April 30, 2026. "
                "Operator. Chief Executive Officer. Prepared remarks.",
            ),
        }, policy(max_links_per_page=1)),
        "named_budget_exhausted": run({
            HINT: html(HINT, f"<a href='{candidate}'>Q1 earnings call transcript</a>"
                                  f"<a href='{second}'>Q2 earnings call transcript</a>"),
            candidate: html(
                candidate, "Firm A quarterly earnings call transcript April 30, 2026. "
                "Operator. Chief Executive Officer. Prepared remarks.",
            ),
        }, policy(max_candidate_evaluations=1)),
        "indeterminate_without_exhaustion": run({HINT: html(HINT, "")}),
    }


def main() -> int:
    cases = reproduction_cases()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(cases), "output": str(OUTPUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
