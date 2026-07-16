"""Deterministic local demonstration of the acquisition substrate lifecycle."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from rfi.acquisition.contracts import (
    CandidateDocument,
    Checkpoint,
    ConflictError,
    DiscoveryProvenance,
    RetrievalOutcome,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.repository import AcquisitionRepository


def fixture_candidate() -> CandidateDocument:
    """Return the stable fixture candidate used by tests and operator demonstration."""
    return CandidateDocument(
        candidate_id="candidate-fixture-release-1",
        source_id="source-fixture-publications",
        document_id="document-fixture-release-1",
        provenance=DiscoveryProvenance(
            discovered_at="2026-01-02T03:04:05Z",
            discovery_method="fixture-manifest",
            provider_identifiers={"fixture_catalog": "release-1"},
            locations=("fixture://acquisition/sample-document.txt",),
            metadata={"sequence": 1},
        ),
    )


def fixture_profile() -> SourceProfile:
    """Return a generic governed profile with no real source-specific behavior."""
    return SourceProfile(
        source_id="source-fixture-publications",
        name="Local fixture publications",
        enabled=True,
        mechanism="fixture-reader",
        configuration={"manifest": "fixtures/acquisition/source-profile.json"},
        policy={"checkpoint_order": "monotonic_position"},
    )


def run_demo(state_root: Path, fixture_path: Path) -> dict[str, Any]:
    """Exercise storage, history, indexing, progress, idempotency, conflict, and replay."""
    repository = AcquisitionRepository(state_root)
    repository.register_source(fixture_profile())
    candidate = fixture_candidate()
    content = fixture_path.read_bytes()
    result = RetrievalResult(
        content=content,
        media_type="text/plain",
        retrieved_at="2026-01-02T03:05:00Z",
        mechanism="fixture-reader",
        provider_identifiers={"fixture_reader": "local-v1"},
        diagnostics={"fixture_bytes": len(content)},
    )
    checkpoint = Checkpoint(position=1, cursor="fixture-release-1")
    receipt = repository.record_success("attempt-fixture-success-1", candidate, result, checkpoint)
    repeated = repository.record_success("attempt-fixture-success-1", candidate, result, checkpoint)
    conflict_detected = False
    try:
        conflicting = RetrievalResult(
            content=b"different bytes\n",
            media_type="text/plain",
            retrieved_at=result.retrieved_at,
            mechanism=result.mechanism,
        )
        repository.record_success(
            "attempt-fixture-success-1", candidate, conflicting, checkpoint
        )
    except ConflictError:
        conflict_detected = True
    repository.record_outcome(
        "attempt-fixture-failure-1",
        candidate,
        RetrievalOutcome.FAILED,
        "2026-01-02T03:06:00Z",
        "fixture-reader",
        {"error_type": "FixtureUnavailable", "message": "simulated retrieval failure"},
    )
    before = repository.verify_integrity()
    exact_bytes_preserved = repository.read_artifact(receipt.artifact_id) == content
    repository.delete_derived_state()
    replay = repository.replay()
    after = repository.verify_integrity()
    return {
        "artifact_id": receipt.artifact_id,
        "checkpoint": repository.checkpoints()["sources"][candidate.source_id],
        "conflict_detected": conflict_detected,
        "document_id": receipt.document_id,
        "exact_bytes_preserved": exact_bytes_preserved,
        "failed_attempt_diagnostics": next(
            record["diagnostics"]
            for record in repository.history()
            if record.get("attempt_id") == "attempt-fixture-failure-1"
        ),
        "idempotent_repeat": repeated.idempotent,
        "integrity_after_replay": after,
        "integrity_before_replay": before,
        "replay": {
            "documents": replay.documents,
            "checkpoints": replay.checkpoints,
            "attempts": replay.attempts,
            "index_sha256": replay.index_sha256,
            "checkpoint_sha256": replay.checkpoint_sha256,
        },
        "result": "PASS"
        if all((conflict_detected, exact_bytes_preserved, repeated.idempotent))
        else "FAIL",
    }


def isolated_demo(fixture_path: Path) -> dict[str, Any]:
    """Run the demonstration in a fresh temporary repository."""
    with tempfile.TemporaryDirectory(prefix="rfi-acquisition-demo-") as temporary:
        return run_demo(Path(temporary), fixture_path)


def render_demo(result: dict[str, Any]) -> str:
    """Render stable machine-readable demonstration output."""
    return json.dumps(result, indent=2, sort_keys=True) + "\n"
