#!/usr/bin/env python3
"""Produce bounded live evidence for TASK-052 configured transcript hints."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from rfi.acquisition import SourceProfile
from rfi.discovery import EarningsTranscriptPullAdapter, load_discovery_policies
from rfi.firm_configuration import prepare_firm_configuration
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase


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
            "source-task052-amazon", "Amazon transcript live proof", True,
            "earnings_transcript", configuration,
            {"firm_id": "amazon", "artifact_id": "earnings_transcript"},
        )
        policies = load_discovery_policies()
        evidence: dict[str, object] = {
            "task": "TASK-052",
            "firm_id": "amazon",
            "adapter_id": EarningsTranscriptPullAdapter.adapter_id,
            "configured_hint": candidate.discovery_hints[0],
            "adapter_request_hint": configuration["discovery_hints"][0],
            "discovery_class": candidate.discovery_class,
            "policy": asdict(policies.resolve(candidate.discovery_class)),
        }
        try:
            adapter = EarningsTranscriptPullAdapter(policies)
            page = adapter.discover(profile, None)
            evidence.update({
                "result": "acquired" if page.candidates else "rejected",
                "candidate_count": len(page.candidates),
                "diagnostics": page.diagnostics,
            })
        except Exception as error:
            evidence.update({
                "result": "adapter_failure",
                "failure_type": error.__class__.__name__,
                "failure": str(error),
            })
        print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


def main() -> int:
    return live_proof()


if __name__ == "__main__":
    raise SystemExit(main())
