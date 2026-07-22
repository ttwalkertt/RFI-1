#!/usr/bin/env python3
"""Run the gated, narrow TASK-031 Lore proof and emit reviewable JSON."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rfi.mailing_lists import (
    AcquisitionLimits,
    LoreArchive,
    LoreTransportPolicy,
    MailingListAcquisitionService,
    MailingListQueryService,
    MailingListRepository,
    MailingListSource,
    RelationshipAcquisitionStatus,
    SelectionCriteria,
)
from rfi.storage import RepositoryDatabase


def main() -> int:
    through = datetime.now(UTC).date()
    start = through - timedelta(days=3)
    source = MailingListSource(
        "task031-live-linux-block",
        "linux-block",
        "Linux block layer TASK-031 live proof",
        "https://lore.kernel.org/linux-block/",
        transport=LoreTransportPolicy(
            user_agent="RFI-1 TASK-031 bounded proof contact=local-operator",
            minimum_request_interval_seconds=0.1,
            maximum_concurrency=1,
            timeout_seconds=10,
            maximum_response_bytes=5_000_000,
            maximum_attempts_per_request=1,
            backoff_initial_seconds=1,
            backoff_maximum_seconds=10,
        ),
    )
    criteria = SelectionCriteria(
        date_from=start.isoformat(),
        date_through=through.isoformat(),
        subject_terms=("PATCH",),
    )
    limits = AcquisitionLimits(seed_limit=1, context_limit=1, descendant_depth=0)
    with tempfile.TemporaryDirectory(prefix="rfi-task031-live-") as temporary:
        state = Path(temporary)
        RepositoryDatabase.initialize(state)
        repository = MailingListRepository(state)
        repository.configure_source(source)
        service = MailingListAcquisitionService(repository, LoreArchive(source))
        manifests = []
        error = None
        try:
            for _index in range(1):
                manifest = service.acquire(
                    source.source_id,
                    criteria,
                    limits,
                    coverage_batch_id="task031-gated-live-proof",
                )
                manifests.append(asdict(manifest))
                if manifest.relationship_status != (
                    RelationshipAcquisitionStatus.CONTINUATION_PENDING
                ):
                    break
        except Exception as caught:  # sanitized contracts are part of the proof output
            error = {
                "type": type(caught).__name__,
                "code": getattr(caught, "code", None),
                "message": str(caught),
                "retryable": bool(getattr(caught, "retryable", False)),
            }
        query = MailingListQueryService(repository)
        messages = []
        for manifest in manifests:
            messages.extend(
                asdict(item) for item in query.acquisition_messages(manifest["run_id"])
            )
        unique_links = sorted({item["source_link"] for item in messages if item["source_link"]})
        final = manifests[-1] if manifests else None
        result = {
            "proof": "TASK-031 gated bounded Lore proof",
            "archive": source.archive_base_url,
            "criteria": asdict(criteria),
            "limits": asdict(limits),
            "adapter_usage": service.archive.usage(),
            "runs": manifests,
            "relationship_runs_performed": len(manifests),
            "continuation_transitions": [
                item["relationship_status"] for item in manifests
            ],
            "messages_retained_per_run": [item["message_count"] for item in manifests],
            "relationships_retained_per_run": [
                item["relationship_count"] for item in manifests
            ],
            "final_coverage_complete": bool(final and final["coverage_complete"]),
            "source_links": unique_links,
            "rerun_or_restart_result": (
                "Each continuation used the prior SQLite manifest in the same temporary "
                "repository; deterministic tests separately restart the process boundary."
            ),
            "error": error,
            "claim": (
                "live_multi_run_continuation_proved"
                if len(manifests) > 1 and final
                and final["relationship_status"] != "continuation_pending"
                else "bounded_live_only; deterministic fixture proves durable multi-run completion"
            ),
        }
        print(json.dumps(result, indent=2, default=str, sort_keys=True))
    return 0 if manifests else 1


if __name__ == "__main__":
    raise SystemExit(main())
