#!/usr/bin/env python3
"""Run the bounded, transcript-text-free TASK-064 live acceptance check."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from rfi.acquisition import (
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptSeed,
)
from rfi.acquisition.earnings_transcripts import UrllibEarningsTranscriptTransport
from rfi.acquisition.providers.stockanalysis import StockAnalysisTranscriptProvider, archive_url
from rfi.discovery import (
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    TranscriptTerminalSelectionPolicy,
)

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_PATHS = {
    "provider": ROOT / "src/rfi/acquisition/providers/stockanalysis.py",
    "contracts": ROOT / "src/rfi/acquisition/contracts.py",
    "orchestrator": ROOT / "src/rfi/discovery.py",
    "engine": ROOT / "src/rfi/acquisition/engine.py",
    "live_validator": Path(__file__).resolve(),
}


def implementation_identity() -> dict[str, str]:
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(IDENTITY_PATHS.items())
    }


def verify_evidence(path: Path) -> dict[str, object]:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence.get("implementation_identity") != implementation_identity():
        raise ValueError("live evidence does not match the current TASK-064 implementation")
    usage = evidence.get("resource_usage")
    if not isinstance(usage, dict) or not isinstance(usage.get("bytes"), int):
        raise ValueError("live evidence has no authoritative byte count")
    if evidence.get("direct_document", {}).get("outcome") != "validated":
        raise ValueError("live evidence does not contain a validated direct document")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify is not None:
        evidence = verify_evidence(args.verify)
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    configured_provider = "stockanalysis"
    hint_kind = "provider_identifier"
    hint_value = "WDC"
    policy = DiscoveryPolicy(
        max_search_queries=0,
        max_results_per_query=1,
        max_unique_eligible_links_per_page=10,
        max_depth=1,
        max_pages=8,
        max_distinct_hosts=1,
        max_bytes=5_000_000,
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
        "source-task064-live", "Western Digital StockAnalysis live acceptance", True,
        "earnings_transcript",
        {
            "mode": "discovery", "provider": configured_provider,
            "discovery_hint_kind": hint_kind, "discovery_hint_value": hint_value,
            "discovery_class": "task064-live", "discovery_hints": [],
        },
        {"firm_id": "western-digital", "artifact_id": "earnings_transcript",
         "retrieval_adapter_id": "earnings-call-transcript"},
    )
    page = provider.discover(
        profile,
        TranscriptSeed(configured_provider, hint_kind, hint_value, "configured"),
        TranscriptAcquisitionTarget("western-digital"),
    )
    selection_policy = TranscriptTerminalSelectionPolicy(
        TranscriptAcquisitionSelection.first_in_date_range(
            date(2026, 4, 1),
            date(2026, 5, 1),
        )
    )
    representative = None
    result = None
    decision = None
    evaluated: list[dict[str, object]] = []
    failure: Exception | None = None
    for candidate in page.candidates:
        try:
            candidate_result = provider.retrieve(profile, candidate)
            candidate_decision = selection_policy.qualify(candidate, candidate_result)
            evaluated.append({
                "event_disposition": (
                    candidate_result.transcript_metadata_observation.event_disposition.value
                ),
                "trusted_event_date_present": (
                    candidate_result.trusted_event_date is not None
                ),
                "qualification_outcome": candidate_decision.validation_outcome,
            })
            if candidate_decision.qualifies:
                representative = candidate
                result = candidate_result
                decision = candidate_decision
                break
        except Exception as error:  # preserve bounded access/layout evidence
            evaluated.append({
                "failure_type": error.__class__.__name__,
                "failure_code": getattr(error, "code", "live_provider_failure"),
            })
            failure = error
    direct: dict[str, object]
    if representative is None or result is None or decision is None:
        direct = {
            "outcome": "not_qualified",
            "limitation": (
                str(failure) if failure is not None
                else "no substantial transcript had an artifact-local date in range"
            ),
            "candidate_evaluations": evaluated,
        }
    else:
        direct = {
            "outcome": "validated",
            "requested_url": representative.provenance.metadata["requested_url"],
            "resolved_url": result.diagnostics.get("resolved_url"),
            "event_date": (
                result.trusted_event_date.isoformat()
                if result.trusted_event_date else None
            ),
            "event_label": result.transcript_metadata_observation.event_label,
            "event_disposition": (
                result.transcript_metadata_observation.event_disposition.value
            ),
            "repository_qualification_outcome": decision.validation_outcome,
            "candidate_evaluations": evaluated,
            "substantial_transcript": result.diagnostics.get(
                "substantial_transcript"
            ),
            "transcript_word_count": result.diagnostics.get(
                "transcript_word_count"
            ),
            "speaker_turn_count": result.diagnostics.get("speaker_turn_count"),
            "speaker_turn_content_sha256": result.diagnostics.get(
                "speaker_turn_content_sha256"
            ),
            "related_artifacts": [
                {"artifact_kind": item.artifact_kind,
                 "observed_url": item.observed_url}
                for item in result.related_artifact_observations
            ],
            "learning_feedback": [
                item.to_dict() for item in result.transcript_learning_feedback
            ],
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
            {
                "url": item.provenance.metadata.get("resolved_url"),
                "event_disposition": (
                    item.transcript_metadata_observation.event_disposition.value
                    if item.transcript_metadata_observation is not None else "unknown"
                ),
            }
            for item in page.candidates
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
        "implementation_identity": implementation_identity(),
    }
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
