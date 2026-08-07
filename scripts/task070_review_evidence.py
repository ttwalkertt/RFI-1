#!/usr/bin/env python3
"""Generate deterministic TASK-070 classification and repository evidence."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rfi.acquisition import (
    TranscriptAcquisitionSelection,
    TranscriptEventDisposition,
    TranscriptMetadataObservation,
)
from rfi.acquisition.transcript_classification import classify_transcript_event
from rfi.artifacts import ArtifactQuery, ArtifactQueryService
from rfi.pull import PullRequest
from tests.test_task070 import CONFERENCE_URL, Transport, configured_workflow

def classification_evidence() -> list[dict[str, str]]:
    """Return the exact deterministic classification table used by the review."""
    titles = (
        "Earnings Call: Q4 2025",
        "Citi's Global TMT Conference 2024",
        "UBS Global Technology and AI Conference",
        "Wells Fargo 8th Annual TMT Summit",
        "Investor Day 2025",
        "Executive Fireside Chat",
        "Annual Analyst Briefing",
        "Management discussion",
    )
    evidence = []
    for title in titles:
        result = classify_transcript_event(TranscriptMetadataObservation(
            title,
            date(2025, 1, 1),
            TranscriptEventDisposition.UNKNOWN,
        ))
        evidence.append({
            "title": title,
            "observed_event_disposition": "unknown",
            "canonical_artifact_id": result.canonical_artifact_id,
            "transcript_event_kind": result.event_kind.value,
            "classification_basis": result.basis,
        })
    return evidence


def repository_evidence() -> dict[str, object]:
    """Prove alternate retention and repeated historical earnings advancement."""
    with tempfile.TemporaryDirectory() as directory:
        transport = Transport()
        workflow, repository, firms, template = configured_workflow(
            Path(directory), transport
        )
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        request = PullRequest(("oracle",), False, selection)
        pulls = (workflow.run(request), workflow.run(request))
        service = ArtifactQueryService(repository, firms, template)
        earnings = service.query(ArtifactQuery(
            firm_ids=("oracle",),
            canonical_artifact_ids=("earnings_transcript",),
        ))
        management = service.query(ArtifactQuery(
            firm_ids=("oracle",),
            canonical_artifact_ids=("management_transcript",),
        ))
        management_detail = service.detail(management.items[0].document_id)
        history = [
            item for item in repository.history() if item.get("outcome") == "success"
        ]
        selected_dates = []
        for pull in pulls:
            engine = pull.firms[0].artifacts[0].attempts[0].details
            assert engine is not None
            terminal = next(
                item for item in engine["engine_diagnostics"]
                if item.get("terminal_selection_outcome") == "selected"
            )
            selected_dates.append(terminal["selected_validated_event_date"])
        return {
            "pull_summaries": [pull.summary.__dict__ for pull in pulls],
            "selected_earnings_dates": selected_dates,
            "earnings_document_ids": [item.document_id for item in earnings.items],
            "management_document_ids": [item.document_id for item in management.items],
            "management_observation": {
                "canonical_artifact_id": (
                    management_detail.summary.canonical_artifact_id
                ),
                "artifact_id": management_detail.summary.artifact_id,
                "diagnostics": management_detail.observation.diagnostics,
                "provenance_locations": [
                    item.location
                    for item in management_detail.observation.provenance_locations
                ],
            },
            "conference_request_count": transport.requests.count(CONFERENCE_URL),
            "content_addressed_artifact_ids": sorted({
                str(item["artifact_id"]) for item in history
            }),
            "canonical_success_counts": {
                kind: sum(item.get("canonical_artifact_id") == kind for item in history)
                for kind in ("earnings_transcript", "management_transcript")
            },
            "checkpoint": next(iter(repository.checkpoints()["sources"].values())),
            "source_policy": next(iter(repository.sources()))["policy"],
            "integrity": repository.verify_integrity(),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".artifacts/task070-validation"
    )
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    payload = {
        "classifications": classification_evidence(),
        "repository": repository_evidence(),
    }
    target = arguments.output / "classification-and-retention.json"
    target.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
