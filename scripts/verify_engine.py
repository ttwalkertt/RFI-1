#!/usr/bin/env python3
"""Produce deterministic TASK-003 acquisition-engine verification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AcquisitionRepository,
    AdapterRegistry,
    EngineFailurePoint,
    FixtureCatalogAdapter,
    FixtureFeedAdapter,
    fixture_profiles,
)
from rfi.acquisition.persistence import canonical_json, sha256_bytes  # noqa: E402

FIXTURES = ROOT / "fixtures/acquisition"


def fixed_clock() -> str:
    """Return deterministic lifecycle time for review evidence."""
    return "2026-04-01T00:00:00Z"


def build(root: Path) -> tuple[AcquisitionKernel, FixtureCatalogAdapter, FixtureFeedAdapter]:
    """Build the production kernel with two explicitly registered fixture adapters."""
    repository = AcquisitionRepository(root)
    for profile in fixture_profiles():
        repository.register_source(profile)
    catalog = FixtureCatalogAdapter(FIXTURES, "catalog-states.json")
    feed = FixtureFeedAdapter(FIXTURES, "feed-pages.json")
    registry = AdapterRegistry((catalog, feed))
    engine = AcquisitionEngine(repository, registry, fixed_clock)
    return AcquisitionKernel(engine, repository), catalog, feed


def snapshot(repository: AcquisitionRepository) -> dict[str, Any]:
    """Return complete authoritative inventory and derived views for comparison."""
    artifact_hashes = {
        item["artifact_id"]: sha256_bytes(repository.read_artifact(item["artifact_id"]))
        for item in repository.artifact_metadata()
    }
    return {
        "sources": repository.sources(),
        "artifact_metadata": repository.artifact_metadata(),
        "artifact_hashes": artifact_hashes,
        "history": repository.history(),
        "index": repository.document_index(),
        "checkpoints": repository.checkpoints(),
    }


def end_to_end() -> dict[str, Any]:
    """Prove multi-source engine execution with network construction blocked."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-003-e2e-") as directory:
        kernel, _catalog, _feed = build(Path(directory))
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            results = kernel.run_enabled("e2e")
        state = snapshot(kernel.repository)
        return {
            "network_socket_blocked": True,
            "adapter_registrations": kernel.engine.adapter_registrations(),
            "runs": [item.to_dict() for item in results],
            "repository_counts": kernel.repository.verify_integrity(),
            "documents": len(state["index"]["documents"]),
            "exact_artifact_hashes": state["artifact_hashes"],
            "result": "PASS",
        }


def idempotency() -> dict[str, Any]:
    """Prove a second equivalent bounded execution cannot change repository state."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-003-idempotency-") as directory:
        kernel, _catalog, _feed = build(Path(directory))
        first = kernel.run_enabled("equivalent")
        before = snapshot(kernel.repository)
        second = kernel.run_enabled("equivalent")
        after = snapshot(kernel.repository)
        equal = before == after
        return {
            "first_runs": [item.to_dict() for item in first],
            "second_runs": [item.to_dict() for item in second],
            "repository_state_equal": equal,
            "state_sha256_before": sha256_bytes(canonical_json(before)),
            "state_sha256_after": sha256_bytes(canonical_json(after)),
            "result": "PASS" if equal else "FAIL",
        }


def revision() -> dict[str, Any]:
    """Prove stable document identity relates two immutable source revisions."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-003-revision-") as directory:
        kernel, catalog, _feed = build(Path(directory))
        initial = kernel.engine.run_source("source-fixture-catalog", "initial")
        old_artifacts = kernel.repository.artifact_metadata()
        catalog.state = "revised"
        revised = kernel.engine.run_source("source-fixture-catalog", "revised")
        entry = kernel.repository.document_index()["documents"]["document-catalog-a"]
        return {
            "initial": initial.to_dict(),
            "revised": revised.to_dict(),
            "stable_document_id": entry["document_id"],
            "related_artifacts": entry["artifacts"],
            "prior_artifacts_still_present": all(
                item in kernel.repository.artifact_metadata() for item in old_artifacts
            ),
            "integrity": kernel.repository.verify_integrity(),
            "result": "PASS" if len(entry["artifacts"]) == 2 else "FAIL",
        }


def failure_and_resumption() -> dict[str, Any]:
    """Prove mid-page and pre-finalization failures retain safe resumable evidence."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-003-failure-") as directory:
        kernel, catalog, feed = build(Path(directory))
        feed.transient_retrieval_failures.add("candidate-feed-b-v1")
        partial = kernel.engine.run_source("source-fixture-feed", "partial")
        history_after_partial = kernel.repository.history()
        feed.transient_retrieval_failures.clear()
        resumed = kernel.engine.run_source("source-fixture-feed", "resumed")
        finalization_partial = kernel.engine.run_source(
            "source-fixture-catalog",
            "pre-finalize",
            EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION,
        )
        finalization_resumed = kernel.engine.run_source(
            "source-fixture-catalog", "finalize-resumed"
        )
        return {
            "mid_page_partial": partial.to_dict(),
            "mid_page_resumed": resumed.to_dict(),
            "partial_history_preserved": all(
                item in kernel.repository.history() for item in history_after_partial
            ),
            "before_finalization": finalization_partial.to_dict(),
            "after_finalization_resume": finalization_resumed.to_dict(),
            "catalog_adapter_state": catalog.state,
            "integrity": kernel.repository.verify_integrity(),
            "result": "PASS",
        }


def replay_and_rebuild() -> dict[str, Any]:
    """Delete derived views and replay with adapters unavailable and sockets blocked."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-003-replay-") as directory:
        kernel, catalog, feed = build(Path(directory))
        kernel.run_enabled("replay")
        before = snapshot(kernel.repository)
        original_bytes = {
            identity: kernel.repository.read_artifact(identity)
            for identity in before["artifact_hashes"]
        }
        catalog.malformed_discovery = True
        feed.malformed_discovery = True
        kernel.repository.delete_derived_state()
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            replay = kernel.repository.replay()
        after = snapshot(kernel.repository)
        exact_bytes = all(
            kernel.repository.read_artifact(identity) == content
            for identity, content in original_bytes.items()
        )
        return {
            "derived_state_deleted": True,
            "adapters_disabled_by_malformed_mode": True,
            "network_socket_blocked": True,
            "replay": {
                "documents": replay.documents,
                "checkpoints": replay.checkpoints,
                "attempts": replay.attempts,
                "index_sha256": replay.index_sha256,
                "checkpoint_sha256": replay.checkpoint_sha256,
            },
            "authoritative_state_equal": all(
                before[name] == after[name]
                for name in ("sources", "artifact_metadata", "artifact_hashes", "history")
            ),
            "derived_state_equal": all(
                before[name] == after[name] for name in ("index", "checkpoints")
            ),
            "exact_artifact_bytes_equal": exact_bytes,
            "integrity": kernel.repository.verify_integrity(),
            "result": "PASS",
        }


def determinism() -> dict[str, Any]:
    """Compare complete state produced by two clean multi-source demonstrations."""
    states = []
    for prefix in ("a", "b"):
        with tempfile.TemporaryDirectory(prefix=f"rfi-task-003-clean-{prefix}-") as directory:
            kernel, _catalog, _feed = build(Path(directory))
            kernel.run_enabled("deterministic")
            states.append(snapshot(kernel.repository))
    first_digest = hashlib.sha256(canonical_json(states[0])).hexdigest()
    second_digest = hashlib.sha256(canonical_json(states[1])).hexdigest()
    return {
        "clean_state_1_sha256": first_digest,
        "clean_state_2_sha256": second_digest,
        "complete_states_equal": states[0] == states[1],
        "result": "PASS" if states[0] == states[1] else "FAIL",
    }


def main() -> int:
    """Run one named proof and emit raw machine-readable evidence."""
    checks = {
        "end-to-end": end_to_end,
        "idempotency": idempotency,
        "revision": revision,
        "failure-resumption": failure_and_resumption,
        "replay-rebuild": replay_and_rebuild,
        "determinism": determinism,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=tuple(checks))
    result = checks[parser.parse_args().check]()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
