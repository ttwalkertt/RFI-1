#!/usr/bin/env python3
"""Offline and explicitly gated live TASK-016 vertical-slice proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rfi.acquisition import AcquisitionRepository  # noqa: E402
from rfi.acquisition.edgar import (  # noqa: E402
    USER_AGENT_VARIABLE,
    user_agent_from_environment,
)
from rfi.acquisition.runtime_config import load_runtime_configuration  # noqa: E402
from rfi.acquisition.sec_form_10k import SecForm10KAdapter  # noqa: E402
from rfi.acquisition.sec_provider import SecProviderClient  # noqa: E402
from rfi.concepts import ConceptRepository  # noqa: E402
from rfi.firms import FirmRepository, sample_firms  # noqa: E402
from rfi.pull import (  # noqa: E402
    ArtifactOutcome,
    PullRequest,
    PullRunRepository,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.source_profiles import (  # noqa: E402
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)
from tests.test_task016 import FakeTime, SecFixtureTransport  # noqa: E402


def clock() -> str:
    """Return a stable fixture time; live retrieval timestamps remain explicit proof metadata."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def runtime_user_agent() -> str:
    """Resolve governed local/environment runtime identity without printing its value."""
    runtime = load_runtime_configuration(ROOT)
    return user_agent_from_environment(f"env:{USER_AGENT_VARIABLE}", runtime)


def initialize_state(state: Path) -> tuple[Any, Any, Any, Any]:
    """Create one isolated configured Seagate Form 10-K application state."""
    if state.exists():
        raise RuntimeError(f"refusing to reuse existing TASK-016 state: {state}")
    ConceptRepository.initialize(state)
    firms = FirmRepository.initialize(state / "firm-catalog")
    firms.create(sample_firms()[0])
    template = load_canonical_template()
    profiles = SourceProfileRepository.initialize(state / "source-profiles", template)
    items = tuple(
        SourceProfileItem(
            artifact.artifact_id,
            artifact.artifact_id == "sec_10k",
            (
                RetrievalCandidate("identifier", 1, locator="CIK:0001137789"),
            )
            if artifact.artifact_id == "sec_10k"
            else (),
        )
        for artifact in template.artifacts
    )
    revision = profiles.publish(SourceProfileDraft("seagate", items), None)
    return firms, profiles, template, revision


def workflow(
    state: Path,
    firms: Any,
    profiles: Any,
    template: Any,
    provider: SecProviderClient,
    identifiers: Callable[[], str],
) -> PullWorkflow:
    """Compose the same production boundaries with an injectable provider transport."""
    adapter = SecForm10KAdapter(provider, clock)
    adapters = RetrievalAdapterRegistry(
        (
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability(
                    adapter.adapter_id,
                    adapter.artifact_ids,
                    adapter.retrieval_modes,
                ),
                adapter,
            ),
        )
    )
    return PullWorkflow(
        firms,
        profiles,
        template,
        AcquisitionRepository(state / "acquisition"),
        adapters,
        PullRunRepository(state / "pull-workflows"),
        clock,
        identifiers,
    )


def execute_proof(state: Path, provider: SecProviderClient) -> dict[str, Any]:
    """Run first/repeat pulls and provider-disabled replay, rebuild, and integrity."""
    firms, profiles, template, revision = initialize_state(state)
    identifiers = iter(("task016first", "task016repeat"))
    pull = workflow(state, firms, profiles, template, provider, identifiers.__next__)
    readiness = pull.configured_firms()[0]
    first = pull.run(PullRequest(("seagate",)))
    second = pull.run(PullRequest(("seagate",)))
    repository = AcquisitionRepository(state / "acquisition")
    metadata = repository.artifact_metadata()
    documents = repository.document_index()["documents"]
    exact = repository.read_artifact(metadata[0]["artifact_id"]) if metadata else b""
    integrity_before = repository.verify_integrity()
    repository.delete_derived_state()
    with patch("socket.socket", side_effect=AssertionError("network unavailable")):
        replay = repository.replay()
        integrity_after = repository.verify_integrity()
    first_artifact = first.firms[0].artifacts[0]
    second_artifact = second.firms[0].artifacts[0]
    checks = {
        "profile_revision_snapshotted": (
            first.firms[0].source_profile_revision_id
            == revision.source_profile_revision_id
        ),
        "readiness_runnable": (
            readiness.enabled_artifacts == readiness.runnable_artifacts == 1
        ),
        "first_success": first_artifact.outcome == ArtifactOutcome.SUCCESS,
        "repeat_no_change": second_artifact.outcome == ArtifactOutcome.NO_CHANGE,
        "one_artifact": len(metadata) == 1,
        "one_document": len(documents) == 1,
        "exact_checksum": bool(exact)
        and metadata[0]["sha256"] == hashlib.sha256(exact).hexdigest(),
        "integrity_before": integrity_before["result"] == "PASS",
        "replay_network_unavailable": replay.documents == 1,
        "integrity_after": integrity_after["result"] == "PASS",
    }
    return {
        "mode": "production-pull-workflow",
        "adapter_capabilities": pull.adapter_capabilities(),
        "source_profile_revision_id": revision.source_profile_revision_id,
        "readiness": asdict(readiness),
        "first_pull": asdict(first),
        "repeat_pull": asdict(second),
        "artifact_inventory": metadata,
        "artifact_sha256": hashlib.sha256(exact).hexdigest() if exact else None,
        "artifact_bytes": len(exact),
        "document_ids": sorted(documents),
        "integrity_before": integrity_before,
        "replay": asdict(replay),
        "integrity_after": integrity_after,
        "network_unavailable_during_replay": True,
        "provider_usage": provider.usage(),
        "checks": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
    }


def fixture_proof() -> int:
    """Run complete deterministic production-contract proof with checked-in fixtures."""
    with tempfile.TemporaryDirectory(prefix="rfi-task016-fixture-") as temporary:
        timing = FakeTime()
        provider = SecProviderClient(
            lambda: "RFI-1-task016 fixture-contact@example.invalid",
            SecFixtureTransport(),
            minimum_request_interval_seconds=0.1,
            monotonic=timing.monotonic,
            sleeper=timing.sleep,
        )
        result = execute_proof(Path(temporary) / "state", provider)
        result["mode"] = "offline-sec-fixture-production-contracts"
        result["fixture_paths"] = [
            "fixtures/sec-10k/CIK0001137789.json",
            "fixtures/sec-10k/stx-2025-10k.htm",
        ]
        result["pacing_sleep_events"] = len(timing.sleeps)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result["result"] == "PASS" else 1


def live_config() -> int:
    """Validate live prerequisites and print bounded scope without network activity."""
    runtime_user_agent()
    print(
        json.dumps(
            {
                "result": "PASS",
                "network_activity": False,
                "runtime_identity_present": True,
                "runtime_identity_emitted": False,
                "issuer_cik": "1137789",
                "artifact": "sec_10k",
                "eligible_form": "10-K",
                "amendment_policy": "exclude",
                "first_pull_expected_operations": [
                    "one SEC submissions request",
                    "one SEC primary-document request",
                ],
                "repeat_pull_expected_operations": ["one SEC submissions request"],
                "maximum_attempts_per_operation": 2,
                "combined_live_attempt_ceiling": 6,
                "timeout_seconds_per_attempt": 20,
                "minimum_request_interval_seconds": 0.5,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def live_pull(state: Path, evidence: Path, confirmed: bool) -> int:
    """Execute the explicitly confirmed bounded live pull and equivalent rerun."""
    if not confirmed:
        raise RuntimeError("live SEC access requires --confirm-live-sec")
    if evidence.exists():
        raise RuntimeError(f"refusing to replace existing live evidence: {evidence}")
    runtime_user_agent()
    provider = SecProviderClient(runtime_user_agent)
    result = execute_proof(state, provider)
    result["mode"] = "gated-live-sec-edgar"
    result["runtime_identity_present"] = True
    result["runtime_identity_emitted"] = False
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["result"] == "PASS" else 1


def parser() -> argparse.ArgumentParser:
    """Build explicit offline/config/live operator commands."""
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("fixture-proof")
    commands.add_parser("live-config")
    live = commands.add_parser("live-pull")
    live.add_argument("--state", type=Path, required=True)
    live.add_argument("--evidence", type=Path, required=True)
    live.add_argument("--confirm-live-sec", action="store_true")
    return value


def main() -> int:
    """Dispatch one bounded TASK-016 proof operation."""
    arguments = parser().parse_args()
    if arguments.command == "fixture-proof":
        return fixture_proof()
    if arguments.command == "live-config":
        return live_config()
    return live_pull(arguments.state, arguments.evidence, arguments.confirm_live_sec)


if __name__ == "__main__":
    raise SystemExit(main())
