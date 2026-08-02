#!/usr/bin/env python3
"""Deterministic manual evidence for TASK-059 transcript selection."""

from __future__ import annotations

import json
from datetime import date

from rfi.acquisition import (
    EarningsTranscriptHttpResponse,
    SourceProfile,
    TranscriptAcquisitionSelection,
)
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)


class Search:
    endpoint = "https://search.example/results"

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        return DiscoverySearchResponse((), 0)


class Transport:
    def __init__(self, response: EarningsTranscriptHttpResponse) -> None:
        self.response = response
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return self.response


class LearnedSeeds:
    def discovery_anchors(
        self, firm_id: str, source_id: str, adapter_id: str
    ) -> tuple[dict[str, object], ...]:
        del firm_id, source_id, adapter_id
        return tuple(
            {"normalized_url": url, "requested_url": url, "resolved_url": None}
            for url in (
                "https://ir.example.com/archive-one",
                "https://ir.example.com/archive-two",
            )
        )


def policies() -> DiscoveryPolicyCatalog:
    return DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(2, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )


def proof() -> dict[str, object]:
    url = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
    profile = SourceProfile(
        "source-a", "Firm A transcripts", True, "earnings_transcript",
        {
            "mode": "discovery",
            "discovery_hints": [url],
            "discovery_class": "standard",
        },
        {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
    )
    response = EarningsTranscriptHttpResponse(
        url, 200, "text/html",
        b"<html>Firm A earnings call transcript April 30, 2026. Operator. CEO.</html>",
    )
    omitted_transport = Transport(response)
    explicit_transport = Transport(response)
    omitted = EarningsTranscriptPullAdapter(
        policies(), Search(), omitted_transport, lambda: "2026-08-01T00:00:00Z"
    )
    explicit = EarningsTranscriptPullAdapter(
        policies(), Search(), explicit_transport, lambda: "2026-08-01T00:00:00Z",
        selection=TranscriptAcquisitionSelection.latest(),
    )
    omitted_trial = omitted.acquisition_trials(profile)[0]
    explicit_trial = explicit.acquisition_trials(profile)[0]
    omitted_page = omitted.discover_trial(profile, omitted_trial)
    explicit_page = explicit.discover_trial(profile, explicit_trial)

    range_selection = TranscriptAcquisitionSelection.first_in_date_range(
        date(2025, 1, 1), date(2025, 12, 31)
    )
    learned = LearnedSeeds()
    range_adapter = EarningsTranscriptPullAdapter(
        policies(), Search(), Transport(response),
        repository=learned,  # type: ignore[arg-type]
        selection=range_selection,
    )
    trials = range_adapter.acquisition_trials(profile)
    target = trials[0].acquisition_target
    result = {
        "omitted_effective_selection": omitted_trial.acquisition_target.selection.to_dict(),
        "explicit_latest_selection": explicit_trial.acquisition_target.selection.to_dict(),
        "latest_candidate_projection_equal": (
            tuple(item.canonical() for item in omitted_page.candidates)
            == tuple(item.canonical() for item in explicit_page.candidates)
        ),
        "latest_request_order_equal": omitted_transport.requests == explicit_transport.requests,
        "trial_count": len(trials),
        "one_immutable_target_for_all_trials": all(
            item.acquisition_target is target for item in trials
        ),
        "only_starting_seed_varies": len({item.starting_seed for item in trials}) > 1,
        "range_is_inclusive": (
            range_selection.contains(date(2025, 1, 1))
            and range_selection.contains(date(2025, 12, 31))
            and not range_selection.contains(date(2024, 12, 31))
        ),
    }
    if not all((
        result["latest_candidate_projection_equal"],
        result["latest_request_order_equal"],
        result["one_immutable_target_for_all_trials"],
        result["only_starting_seed_varies"],
        result["range_is_inclusive"],
    )):
        raise RuntimeError("TASK-059 selection proof failed")
    return result


if __name__ == "__main__":
    print(json.dumps(proof(), indent=2, sort_keys=True))
