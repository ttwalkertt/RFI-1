#!/usr/bin/env python3
"""Produce bounded live evidence for TASK-053 traversal-budget semantics."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from rfi.acquisition import (
    EarningsTranscriptHttpResponse,
    SourceProfile,
    UrllibEarningsTranscriptTransport,
)
from rfi.discovery import EarningsTranscriptPullAdapter, load_discovery_policies
from rfi.firm_configuration import prepare_firm_configuration
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase


class RecordingLiveTransport(UrllibEarningsTranscriptTransport):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return super().get(url)


def live_proof() -> int:
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory)
        RepositoryDatabase.initialize(state)
        configured = state / "firm-config"
        configured.mkdir()
        configured.joinpath("amazon.firm-config.json").write_text(
            Path("docs/amazon.firm-config.example.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        prepare_firm_configuration(state)
        revision = SourceProfileRepository.open(
            state / "source-profiles", load_canonical_template()
        ).get("amazon")
        item = next(
            value for value in revision.items
            if value.artifact_id == "earnings_transcript"
        )
        candidate = item.retrieval_candidates[0]
        configuration = json.loads(json.dumps(asdict(candidate)))
        profile = SourceProfile(
            "source-task053-amazon", "Amazon transcript live proof", True,
            "earnings_transcript", configuration,
            {"firm_id": "amazon", "artifact_id": "earnings_transcript"},
        )
        policies = load_discovery_policies()
        selected_policy = policies.resolve(candidate.discovery_class)
        configured_hint = candidate.discovery_hints[0]
        transport = RecordingLiveTransport()
        evidence: dict[str, object] = {
            "task": "TASK-053",
            "firm_id": "amazon",
            "adapter_id": EarningsTranscriptPullAdapter.adapter_id,
            "configured_hint": configured_hint,
            "adapter_request_hint": configuration["discovery_hints"][0],
            "discovery_class": candidate.discovery_class,
            "policy": asdict(selected_policy),
        }
        try:
            page = EarningsTranscriptPullAdapter(
                policies, transport=transport
            ).discover(profile, None)
            traversed = int(page.diagnostics.get("traversed_hyperlinks", 0))
            evidence.update({
                "result": "acquired" if page.candidates else "rejected",
                "candidate_count": len(page.candidates),
                "first_request": transport.requests[0] if transport.requests else "",
                "configured_hint_fetched_first": bool(
                    transport.requests and transport.requests[0] == configured_hint
                ),
                "eligible_traversal_within_limit": (
                    traversed <= selected_policy.max_unique_eligible_links_per_page
                ),
                "diagnostics": page.diagnostics,
            })
        except Exception as error:
            evidence.update({
                "result": "adapter_failure",
                "first_request": transport.requests[0] if transport.requests else "",
                "configured_hint_fetched_first": bool(
                    transport.requests and transport.requests[0] == configured_hint
                ),
                "failure_type": error.__class__.__name__,
                "failure": str(error),
            })
        print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


def main() -> int:
    return live_proof()


if __name__ == "__main__":
    raise SystemExit(main())
