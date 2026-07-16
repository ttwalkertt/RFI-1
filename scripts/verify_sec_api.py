#!/usr/bin/env python3
"""Credential-free TASK-004 adapter, engine, replay, and integrity demonstration."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rfi.acquisition.engine import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AdapterRegistry,
)
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402
from rfi.acquisition.sec_api import SecApiAdapter, load_live_profiles  # noqa: E402
from tests.test_sec_api import FixtureTransport  # noqa: E402


def main() -> int:
    """Run two bounded fixture-transport acquisitions and offline-only reconstruction."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-004-offline-") as temporary:
        repository = AcquisitionRepository(Path(temporary))
        profiles = load_live_profiles(ROOT)
        for profile in profiles:
            repository.register_source(profile)
        adapter = SecApiAdapter(
            "offline-fixture-credential",
            FixtureTransport(),
            lambda: "2026-07-15T00:00:00Z",
            sleeper=lambda _seconds: None,
        )
        engine = AcquisitionEngine(
            repository, AdapterRegistry((adapter,)), lambda: "2026-07-15T00:00:00Z"
        )
        kernel = AcquisitionKernel(engine, repository)
        first = kernel.run_enabled("offline-first")
        first_index = repository.document_index()
        first_artifacts = repository.artifact_metadata()
        second = kernel.run_enabled("offline-second")
        identity_stable = first_index == repository.document_index()
        artifact_inventory_stable = first_artifacts == repository.artifact_metadata()
        integrity_before = repository.verify_integrity()
        repository.delete_derived_state()
        with patch("socket.socket", side_effect=AssertionError("network creation blocked")):
            replay = repository.replay()
            integrity_after = repository.verify_integrity()
        result = {
            "mode": "offline-sanitized-transport-fixture",
            "live_provider_evidence": False,
            "first_runs": [item.to_dict() for item in first],
            "second_runs": [item.to_dict() for item in second],
            "documents": len(repository.document_index()["documents"]),
            "artifacts": len(repository.artifact_metadata()),
            "identity_stable": identity_stable,
            "artifact_inventory_stable": artifact_inventory_stable,
            "integrity_before": integrity_before,
            "integrity_after": integrity_after,
            "replay": replay.__dict__,
            "network_blocked_during_replay": True,
            "usage": adapter.usage(),
        }
        passed = (
            all(item.status.value == "complete" for item in (*first, *second))
            and identity_stable
            and artifact_inventory_stable
            and integrity_before["result"] == "PASS"
            and integrity_after["result"] == "PASS"
        )
        result["result"] = "PASS" if passed else "FAIL"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
