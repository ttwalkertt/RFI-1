"""Deterministic manual evidence for TASK-058 transcript orchestration."""

from __future__ import annotations

import json

from rfi.acquisition import EarningsTranscriptHttpResponse, SourceProfile
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
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return self.responses[url]


def response(url: str, body: str) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, 200, "text/html", f"<html>{body}</html>".encode()
    )


def policies() -> DiscoveryPolicyCatalog:
    return DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(2, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )


def proof() -> dict[str, object]:
    first = "https://ir.example.com/alias-a-2026-04-30-earnings-call-transcript"
    second = "https://ir.example.com/alias-b-2026-04-30-earnings-call-transcript"
    final = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
    body = (
        "Firm A quarterly earnings call transcript April 30, 2026. Operator. "
        "Chief Executive Officer. Prepared remarks."
    )
    configured = SourceProfile(
        "source-a", "Firm A transcripts", True, "earnings_transcript",
        {
            "mode": "discovery",
            "discovery_hints": [first, second],
            "discovery_class": "standard",
        },
        {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
    )

    legacy_transport = Transport({
        first: response(final, body),
        second: response(final, body),
        final: response(final, body),
    })
    legacy = EarningsTranscriptPullAdapter(
        policies(), Search(), legacy_transport, lambda: "2026-08-01T00:00:00Z"
    )
    legacy_page = legacy.discover(configured, None)

    trial_transport = Transport({
        first: response(final, body),
        second: response(final, body),
        final: response(final, body),
    })
    trial_adapter = EarningsTranscriptPullAdapter(
        policies(), Search(), trial_transport, lambda: "2026-08-01T00:00:00Z"
    )
    trials = trial_adapter.acquisition_trials(configured)
    trial_page = trial_adapter.discover_trial(configured, trials[0])

    ignored_diagnostics = {
        "trial_id", "starting_seed", "seed_kind", "seed_source", "trial_outcome",
        "effective_selection_mode", "requested_date_range",
    }
    legacy_diagnostics = {
        key: value for key, value in legacy_page.diagnostics.items()
        if key not in ignored_diagnostics
    }
    trial_diagnostics = {
        key: value for key, value in trial_page.diagnostics.items()
        if key not in ignored_diagnostics
    }
    candidate_match = tuple(
        candidate.canonical() for candidate in legacy_page.candidates
    ) == tuple(candidate.canonical() for candidate in trial_page.candidates)
    diagnostics_match = legacy_diagnostics == trial_diagnostics
    requests_match = legacy_transport.requests == trial_transport.requests
    aliases = trial_page.candidates[0].provenance.metadata["observed_aliases"]
    result = {
        "configured_fallback_trial_count": len(trials),
        "configured_fallback_seed_kind": trials[0].seed_kind,
        "legacy_requests": legacy_transport.requests,
        "trial_requests": trial_transport.requests,
        "candidate_projection_equal": candidate_match,
        "diagnostics_equal_excluding_trial_attribution": diagnostics_match,
        "request_order_equal": requests_match,
        "retained_aliases": aliases,
        "observable_behavior_unchanged": (
            candidate_match and diagnostics_match and requests_match
            and set(aliases) == {first, second, final}
        ),
    }
    if not result["observable_behavior_unchanged"]:
        raise RuntimeError("TASK-058 configured fallback compatibility proof failed")
    return result


if __name__ == "__main__":
    print(json.dumps(proof(), indent=2, sort_keys=True))
