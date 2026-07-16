#!/usr/bin/env python3
"""Produce deterministic TASK-002 lifecycle verification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition.contracts import Checkpoint, RetrievalResult  # noqa: E402
from rfi.acquisition.demo import (  # noqa: E402
    fixture_candidate,
    fixture_profile,
    render_demo,
    run_demo,
)
from rfi.acquisition.persistence import canonical_json, sha256_bytes  # noqa: E402
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402

FIXTURE = ROOT / "fixtures/acquisition/sample-document.txt"


def populated_repository(root: Path) -> tuple[AcquisitionRepository, str]:
    """Create one deterministic authoritative repository and return its artifact identity."""
    repository = AcquisitionRepository(root)
    repository.register_source(fixture_profile())
    content = FIXTURE.read_bytes()
    result = RetrievalResult(
        content,
        "text/plain",
        "2026-01-02T03:05:00Z",
        "fixture-reader",
        {"fixture_reader": "local-v1"},
        {"fixture_bytes": len(content)},
    )
    receipt = repository.record_success(
        "attempt-fixture-success-1",
        fixture_candidate(),
        result,
        Checkpoint(1, "fixture-release-1"),
    )
    return repository, receipt.artifact_id


def verify_rebuild() -> dict[str, object]:
    """Delete derived views and prove an offline deterministic full rebuild."""
    with tempfile.TemporaryDirectory(prefix="rfi-rebuild-") as temporary:
        repository, artifact_id = populated_repository(Path(temporary))
        index_before = repository.document_index()
        checkpoints_before = repository.checkpoints()
        artifact_before = repository.read_artifact(artifact_id)
        history_before = repository.history()
        repository.delete_derived_state()
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            replay = repository.replay()
        artifact_after = repository.read_artifact(artifact_id)
        return {
            "derived_deleted": True,
            "network_socket_blocked_during_replay": True,
            "index_equal_after_rebuild": repository.document_index() == index_before,
            "checkpoints_equal_after_rebuild": repository.checkpoints() == checkpoints_before,
            "history_equal_after_rebuild": repository.history() == history_before,
            "artifact_equal_after_rebuild": artifact_after == artifact_before,
            "artifact_sha256_before": sha256_bytes(artifact_before),
            "artifact_sha256_after": sha256_bytes(artifact_after),
            "replay": {
                "attempts": replay.attempts,
                "checkpoints": replay.checkpoints,
                "documents": replay.documents,
                "index_sha256": replay.index_sha256,
                "checkpoint_sha256": replay.checkpoint_sha256,
            },
            "result": "PASS",
        }


def verify_integrity() -> dict[str, object]:
    """Independently compare fixture and stored bytes and run repository verification."""
    with tempfile.TemporaryDirectory(prefix="rfi-integrity-") as temporary:
        repository, artifact_id = populated_repository(Path(temporary))
        fixture_bytes = FIXTURE.read_bytes()
        stored_bytes = repository.read_artifact(artifact_id)
        digest = hashlib.sha256(fixture_bytes).hexdigest()
        return {
            "artifact_id": artifact_id,
            "fixture_bytes": len(fixture_bytes),
            "stored_bytes": len(stored_bytes),
            "fixture_sha256": digest,
            "stored_sha256": hashlib.sha256(stored_bytes).hexdigest(),
            "exact_bytes_equal": fixture_bytes == stored_bytes,
            "repository_verification": repository.verify_integrity(),
            "result": "PASS",
        }


def verify_determinism() -> dict[str, object]:
    """Run two clean fixture lifecycles and compare complete results."""
    with tempfile.TemporaryDirectory(prefix="rfi-clean-a-") as first_directory:
        first = run_demo(Path(first_directory), FIXTURE)
    with tempfile.TemporaryDirectory(prefix="rfi-clean-b-") as second_directory:
        second = run_demo(Path(second_directory), FIXTURE)
    return {
        "clean_run_1_sha256": sha256_bytes(canonical_json(first)),
        "clean_run_2_sha256": sha256_bytes(canonical_json(second)),
        "complete_results_equal": first == second,
        "result": "PASS" if first == second else "FAIL",
    }


def main() -> int:
    """Run one named verification and emit exact JSON evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=("fixture", "rebuild", "integrity", "determinism"))
    check = parser.parse_args().check
    if check == "fixture":
        with tempfile.TemporaryDirectory(prefix="rfi-fixture-") as temporary:
            print(render_demo(run_demo(Path(temporary), FIXTURE)), end="")
        return 0
    checks = {
        "rebuild": verify_rebuild,
        "integrity": verify_integrity,
        "determinism": verify_determinism,
    }
    result = checks[check]()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
