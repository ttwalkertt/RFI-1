#!/usr/bin/env python3
"""Produce bounded live TASK-048 acquisition evidence."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    EarningsCallTranscriptAcquisition,
    IntervalAcquisitionRequest,
    IntervalAcquisitionService,
    SourceProfile,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.source_profiles import load_canonical_template


LIVE_CASES = (
    {
        "firm_id": "microsoft",
        "name": "Microsoft",
        "source_id": "source-microsoft-earnings-transcripts",
        "listing": "https://www.microsoft.com/en-us/investor/events",
        "candidate": "https://www.microsoft.com/en-us/investor/events/fy-2025/earnings-fy-2025-q4",
        "label": "Microsoft quarterly earnings call transcript July 30, 2025",
        "allowed_hosts": ["www.microsoft.com"],
    },
    {
        "firm_id": "coca-cola",
        "name": "The Coca-Cola Company",
        "source_id": "source-coca-cola-earnings-transcripts",
        "listing": "https://investors.coca-colacompany.com/financial-information",
        "candidate": (
            "https://investors.coca-colacompany.com/_assets/"
            "_483d853425f10cfb63422955b5e941e6/cocacolacompany/db/880/11064/"
            "webcast_transcript/CORRECTED+TRANSCRIPT_+The+Coca-Cola+Co."
            "%28KO-US%29%2C+Q2+2025+Earnings+Call%2C+22-July-2025+8_30+AM+ET.pdf"
        ),
        "label": "Coca-Cola Q2 2025 earnings call transcript July 22, 2025",
        "allowed_hosts": ["investors.coca-colacompany.com"],
    },
)


def live_proof() -> int:
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        firms = FirmRepository.initialize(root / "firms")
        repository = AcquisitionRepository(root / "acquisition")
        service = IntervalAcquisitionService(firms, load_canonical_template(), repository)
        for case in LIVE_CASES:
            firms.create(FirmDraft(
                case["firm_id"], case["name"], "2025-01-01", status=FirmStatus.ACTIVE
            ))
            profile = SourceProfile(
                case["source_id"], f"{case['name']} official transcript proof", True,
                "earnings_transcript",
                configuration={
                    "listing_urls": [case["listing"]],
                    "allowed_hosts": case["allowed_hosts"],
                    # A search-located proposal proves useful acquisition, but cannot prove the
                    # listing spans the interval. Coverage must therefore remain indeterminate.
                    "authoritative_listing": False,
                    "discover_listing_links": False,
                    "candidate_proposals": [{"url": case["candidate"], "label": case["label"]}],
                },
                policy={"firm_id": case["firm_id"], "artifact_id": "earnings_transcript"},
            )
            repository.register_source(profile)
            request = IntervalAcquisitionRequest(
                case["firm_id"], "earnings_transcript", date(2025, 7, 1), date(2025, 8, 1)
            )
            acquired = EarningsCallTranscriptAcquisition(profile).acquire(request)
            receipt = service.record(request, acquired)
            results.append({
                "firm_id": case["firm_id"],
                "listing_url": case["listing"],
                "candidate_url": case["candidate"],
                "coverage": acquired.coverage.value,
                "coverage_rationale": (
                    "A genuine official transcript was acquired and validated, but a "
                    "search-located candidate plus a non-authoritative listing does not "
                    "establish full interval coverage."
                ),
                "artifact_dates": [item.artifact_date.isoformat() for item in acquired.artifacts],
                "media_types": [item.retrieval.media_type for item in acquired.artifacts],
                "exact_byte_sizes": [len(item.retrieval.content) for item in acquired.artifacts],
                "failures": [item.to_dict() for item in acquired.failures],
                "repository_artifact_ids": [item.artifact_id for item in receipt.artifacts],
            })
        evidence = {
            "task": "TASK-048",
            "requested_interval": "[2025-07-01, 2025-08-01)",
            "cases": results,
            "repository_integrity": repository.verify_integrity(),
        }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if all(item["artifact_dates"] for item in results) else 1


def main() -> int:
    if sys.argv[1:] != ["live-proof"]:
        print("usage: task048_earnings_transcripts.py live-proof", file=sys.stderr)
        return 2
    return live_proof()


if __name__ == "__main__":
    raise SystemExit(main())
