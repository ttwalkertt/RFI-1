#!/usr/bin/env python3
"""Credential-free native EDGAR lifecycle, rerun, replay, and integrity demonstration."""

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

from rfi.acquisition.edgar import EdgarAdapter, load_edgar_profiles  # noqa: E402
from rfi.acquisition.engine import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AdapterRegistry,
)
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402
from tests.test_edgar import EdgarFixtureTransport, FakeTime  # noqa: E402


def main() -> int:
    """Prove the native adapter contract with sanitized, non-live transport fixtures."""
    with tempfile.TemporaryDirectory(prefix="rfi-task-004-edgar-offline-") as temporary:
        repository = AcquisitionRepository(Path(temporary))
        profiles = load_edgar_profiles(ROOT)
        for profile in profiles:
            repository.register_source(profile)
        timing = FakeTime()
        adapter = EdgarAdapter(
            "RFI-1-fixture fixture-contact@example.invalid",
            EdgarFixtureTransport(),
            lambda: "2026-07-15T00:00:00Z",
            timing.monotonic,
            timing.sleep,
        )
        engine = AcquisitionEngine(
            repository,
            AdapterRegistry((adapter,)),
            lambda: "2026-07-15T00:00:00Z",
        )
        kernel = AcquisitionKernel(engine, repository)
        first = kernel.run_enabled("native-offline-first")
        index_before = repository.document_index()
        artifacts_before = repository.artifact_metadata()
        second = kernel.run_enabled("native-offline-second")
        identity_stable = index_before == repository.document_index()
        artifacts_stable = artifacts_before == repository.artifact_metadata()
        integrity_before = repository.verify_integrity()
        repository.delete_derived_state()
        with patch("socket.socket", side_effect=AssertionError("network creation blocked")):
            replay = repository.replay()
            integrity_after = repository.verify_integrity()
        passed = (
            all(result.status.value == "complete" for result in first + second)
            and identity_stable
            and artifacts_stable
            and integrity_before["result"] == "PASS"
            and integrity_after["result"] == "PASS"
        )
        output = {
            "mode": "offline-synthetic-native-edgar-transport",
            "native_edgar_live_evidence": False,
            "first_runs": [result.to_dict() for result in first],
            "second_runs": [result.to_dict() for result in second],
            "documents": len(repository.document_index()["documents"]),
            "artifacts": len(repository.artifact_metadata()),
            "identity_stable": identity_stable,
            "artifact_inventory_stable": artifacts_stable,
            "integrity_before": integrity_before,
            "integrity_after": integrity_after,
            "replay": replay.__dict__,
            "network_blocked_during_replay": True,
            "usage": adapter.usage(),
            "pacing_sleep_events": len(timing.sleeps),
            "result": "PASS" if passed else "FAIL",
        }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
