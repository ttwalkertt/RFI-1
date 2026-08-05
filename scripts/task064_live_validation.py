#!/usr/bin/env python3
"""Run the bounded, transcript-text-free TASK-064 live acceptance check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rfi.acquisition import SourceProfile, TranscriptAcquisitionTarget, TranscriptSeed
from rfi.acquisition.earnings_transcripts import UrllibEarningsTranscriptTransport
from rfi.acquisition.providers.stockanalysis import StockAnalysisTranscriptProvider, archive_url
from rfi.discovery import BudgetedTranscriptTransport, DiscoveryPolicy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    configured_provider = "stockanalysis"
    hint_kind = "provider_identifier"
    hint_value = "ORCL"
    policy = DiscoveryPolicy(
        max_search_queries=0,
        max_results_per_query=1,
        max_unique_eligible_links_per_page=10,
        max_depth=1,
        max_pages=3,
        max_distinct_hosts=1,
        max_bytes=2_000_000,
        max_elapsed_seconds=120,
        max_candidate_evaluations=10,
        max_redirects=2,
    )
    transport = BudgetedTranscriptTransport(
        UrllibEarningsTranscriptTransport(timeout_seconds=90, maximum_bytes=2_000_000),
        policy,
    )
    provider = StockAnalysisTranscriptProvider(transport)
    profile = SourceProfile(
        "source-task064-live", "Oracle StockAnalysis live acceptance", True,
        "earnings_transcript",
        {
            "mode": "discovery", "provider": configured_provider,
            "discovery_hint_kind": hint_kind, "discovery_hint_value": hint_value,
            "discovery_class": "task064-live", "discovery_hints": [],
        },
        {"firm_id": "oracle", "artifact_id": "earnings_transcript",
         "retrieval_adapter_id": "earnings-call-transcript"},
    )
    page = provider.discover(
        profile,
        TranscriptSeed(configured_provider, hint_kind, hint_value, "configured"),
        TranscriptAcquisitionTarget("oracle"),
    )
    representative = next((
        item for item in page.candidates
        if item.provenance.metadata.get("resolved_url")
        == "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
    ), None)
    direct: dict[str, object]
    if representative is None:
        direct = {"outcome": "not_discovered", "limitation": "archive layout changed"}
    else:
        try:
            result = provider.retrieve(profile, representative)
            direct = {
                "outcome": "validated",
                "requested_url": representative.provenance.metadata["requested_url"],
                "resolved_url": result.diagnostics.get("resolved_url"),
                "event_date": result.diagnostics.get("validated_event_date"),
                "speaker_turn_count": result.diagnostics.get("speaker_turn_count"),
                "speaker_turn_content_sha256": result.diagnostics.get(
                    "speaker_turn_content_sha256"
                ),
                "related_artifacts": [
                    {"artifact_kind": item.get("artifact_kind"),
                     "observed_url": item.get("observed_url")}
                    for item in result.diagnostics.get("related_artifacts", [])
                    if isinstance(item, dict)
                ],
                "learning_feedback": result.diagnostics.get("learning_feedback", []),
            }
        except Exception as error:  # bounded live evidence must retain access/layout failures
            direct = {
                "outcome": "blocked",
                "failure_type": error.__class__.__name__,
                "failure_code": getattr(error, "code", "live_provider_failure"),
                "limitation": str(error),
                "requested_url": representative.provenance.metadata["requested_url"],
            }
    evidence = {
        "configured_provider": configured_provider,
        "configured_hint": {"kind": hint_kind, "value": hint_value},
        "effective_provider_adapter": type(provider).__name__,
        "effective_policy": policy.__dict__,
        "constructed_archive_url": archive_url(hint_value),
        "archive_requested_url": page.diagnostics.get("requested_url"),
        "archive_resolved_url": page.diagnostics.get("resolved_url"),
        "candidate_order": [
            item.provenance.metadata.get("resolved_url") for item in page.candidates
        ],
        "representative_discovered": representative is not None,
        "direct_document": direct,
        "resource_usage": {
            "pages": transport.pages,
            "bytes": transport.bytes,
            "distinct_hosts": len(transport.hosts),
            "redirects": transport.redirects,
            "retries": provider.retry_count,
            "bounds_exhausted": transport.exhausted,
            "exhausted_budget": transport.exhausted_budget,
        },
        "search_engine_call_count": 0,
    }
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
