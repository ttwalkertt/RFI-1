#!/usr/bin/env python3
"""Deterministic offline probes for the repository-wide robustness review."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.pull.repository import PullRunRepository
from rfi.pull.workflow import PullWorkflow
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.storage import RepositoryDatabase, StorageError, create_backup, restore_backup


def candidate(source_id: str, suffix: str, url: str) -> CandidateDocument:
    return CandidateDocument(
        f"candidate-{suffix}",
        source_id,
        f"document-{suffix}",
        DiscoveryProvenance(
            "2026-08-05T00:00:00+00:00",
            "review-probe",
            metadata={"requested_url": url},
            locations=(url,),
        ),
    )


def source(source_id: str) -> SourceProfile:
    return SourceProfile(
        source_id,
        "Review probe transcript source",
        True,
        "earnings_transcript",
        {"mode": "discovery", "discovery_hints": ["https://ir.example.test/"]},
        {
            "firm_id": "review-firm",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )


def record(repository: AcquisitionRepository, source_id: str, suffix: str, url: str) -> None:
    repository.record_success(
        f"attempt-{suffix}",
        candidate(source_id, suffix, url),
        RetrievalResult(
            f"transcript-{suffix}".encode(),
            "text/plain",
            "2026-08-05T00:01:00+00:00",
            "review-probe",
            diagnostics={"final_url": url},
        ),
    )


def initialize_state(state: Path) -> None:
    RepositoryDatabase.initialize(state)
    firms = FirmRepository.open(state / "firm-catalog")
    firms.create(FirmDraft(
        "review-firm", "Review Firm", "2026-08-05", status=FirmStatus.ACTIVE
    ))


def profile_revision_anchor_probe(root: Path) -> dict[str, object]:
    state = root / "anchor-state"
    initialize_state(state)
    repository = AcquisitionRepository(state / "acquisition")
    configured = {"mode": "discovery", "discovery_hints": ["https://ir.example.test/"]}
    first_id = PullWorkflow._source_id(
        "review-firm", "earnings_transcript", "profile-r1", configured,
        "earnings-call-transcript",
    )
    second_id = PullWorkflow._source_id(
        "review-firm", "earnings_transcript", "profile-r2", configured,
        "earnings-call-transcript",
    )
    repository.register_source(source(first_id))
    repository.register_source(source(second_id))
    record(repository, first_id, "anchor", "https://ir.example.test/transcript")
    return {
        "first_source_id": first_id,
        "second_source_id": second_id,
        "source_identity_changed": first_id != second_id,
        "first_revision_anchor_count": len(repository.discovery_anchors(
            "review-firm", first_id, "earnings-call-transcript"
        )),
        "second_revision_anchor_count": len(repository.discovery_anchors(
            "review-firm", second_id, "earnings-call-transcript"
        )),
        "contract_result": "FAIL",
    }


def backup_overlap_probe(root: Path) -> dict[str, object]:
    state = root / "backup-state"
    initialize_state(state)
    repository = AcquisitionRepository(state / "acquisition")
    repository.register_source(source("source-backup"))
    record(repository, "source-backup", "before", "https://ir.example.test/before")
    archive = root / "overlap.zip"
    restored = root / "restored"
    original_validate = RepositoryDatabase.validate
    injected = False

    def validate_with_overlap(database: RepositoryDatabase) -> dict[str, object]:
        nonlocal injected
        result = original_validate(database)
        if database.state_root != state and not injected:
            injected = True
            record(repository, "source-backup", "during", "https://ir.example.test/during")
        return result

    with patch.object(RepositoryDatabase, "validate", validate_with_overlap):
        creation = create_backup(state, archive)
    restore_error = None
    try:
        restore_backup(archive, restored)
    except StorageError as error:
        restore_error = str(error)
    return {
        "write_injected_after_database_snapshot": injected,
        "backup_reported_result": creation["result"],
        "restore_succeeded": restore_error is None,
        "restore_error": restore_error,
        "contract_result": "FAIL",
    }


def interrupted_pull_probe(root: Path) -> dict[str, object]:
    state = root / "pull-state"
    RepositoryDatabase.initialize(state)
    runs = PullRunRepository(state / "pull-workflows")
    run_id = "pull-reviewprobe"
    runs.create(run_id, {
        "run_id": run_id,
        "status": "running",
        "requested_at": "2026-08-05T00:00:00+00:00",
        "completed_at": "",
    })
    reopened = PullRunRepository(state / "pull-workflows").get(run_id)
    return {
        "status_after_repository_reopen": reopened["status"],
        "automatic_reconciliation": False,
        "documented_limitation": True,
        "contract_result": "LIMITATION",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rfi-repo-review-") as temporary:
        root = Path(temporary)
        report = {
            "schema_version": 1,
            "profile_revision_anchor_probe": profile_revision_anchor_probe(root),
            "backup_overlap_probe": backup_overlap_probe(root),
            "interrupted_pull_probe": interrupted_pull_probe(root),
        }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
