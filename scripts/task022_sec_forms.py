#!/usr/bin/env python3
"""Offline proof and explicitly gated TASK-022 live SEC pulls."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rfi.acquisition import (  # noqa: E402
    AcquisitionRepository,
    SecForm10QAdapter,
    SecForm20FAdapter,
    SecForm6KAdapter,
    SecForm8KAdapter,
    SecProviderClient,
)
from rfi.acquisition.edgar import (  # noqa: E402
    USER_AGENT_VARIABLE,
    user_agent_from_environment,
)
from rfi.acquisition.runtime_config import load_runtime_configuration  # noqa: E402
from rfi.artifacts import ArtifactQuery, ArtifactQueryService  # noqa: E402
from rfi.concepts import ConceptRepository  # noqa: E402
from rfi.firms import (  # noqa: E402
    FirmDraft,
    FirmIdentifier,
    FirmRepository,
    FirmStatus,
    sample_firms,
)
from rfi.pull import (  # noqa: E402
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

POLICIES = (
    (SecForm10QAdapter, "sec_10q", "10-Q", "seagate", "CIK:0001137789"),
    (SecForm8KAdapter, "sec_8k", "8-K", "seagate", "CIK:0001137789"),
    (SecForm20FAdapter, "sec_20f", "20-F", "asml", "CIK:0000937966"),
    (SecForm6KAdapter, "sec_6k", "6-K", "asml", "CIK:0000937966"),
)


def clock() -> str:
    return datetime.now(UTC).isoformat()


def runtime_user_agent() -> str:
    runtime = load_runtime_configuration(ROOT)
    return user_agent_from_environment(f"env:{USER_AGENT_VARIABLE}", runtime)


def initialize_state(state: Path) -> tuple[Any, Any, Any]:
    """Create fresh domestic/foreign firm profiles using public contracts."""
    if state.exists():
        raise RuntimeError(f"refusing to reuse existing TASK-022 state: {state}")
    ConceptRepository.initialize(state)
    firms = FirmRepository.initialize(state / "firm-catalog")
    firms.create(sample_firms()[0])
    firms.create(
        FirmDraft(
            "asml",
            "ASML",
            "2020-01-01",
            legal_name="ASML Holding N.V.",
            identifiers=(FirmIdentifier("cik", "0000937966", "SEC"),),
            domains=("asml.com",),
            jurisdiction="Netherlands",
            sector="Technology",
            industry="Semiconductor equipment",
            status=FirmStatus.ACTIVE,
        )
    )
    template = load_canonical_template()
    profiles = SourceProfileRepository.initialize(state / "source-profiles", template)
    for firm_id in ("seagate", "asml"):
        policies = {item[1]: item for item in POLICIES if item[3] == firm_id}
        items = tuple(
            SourceProfileItem(
                artifact.artifact_id,
                artifact.artifact_id in policies,
                (
                    RetrievalCandidate(
                        "identifier", 1, locator=policies[artifact.artifact_id][4]
                    ),
                )
                if artifact.artifact_id in policies
                else (),
            )
            for artifact in template.artifacts
        )
        profiles.publish(SourceProfileDraft(firm_id, items), None)
    return firms, profiles, template


def execute(state: Path, provider: SecProviderClient) -> dict[str, object]:
    firms, profiles, template = initialize_state(state)
    adapters = tuple(policy[0](provider, clock) for policy in POLICIES)
    registry = RetrievalAdapterRegistry(
        tuple(
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability(
                    adapter.adapter_id,
                    adapter.artifact_ids,
                    adapter.retrieval_modes,
                ),
                adapter,
            )
            for adapter in adapters
        )
    )
    identifiers = iter(f"task022{index}" for index in range(20))
    workflow = PullWorkflow(
        firms,
        profiles,
        template,
        AcquisitionRepository(state / "acquisition"),
        registry,
        PullRunRepository(state / "pull-workflows"),
        clock,
        identifiers.__next__,
    )
    readiness = tuple(asdict(item) for item in workflow.configured_firms())
    first = workflow.run(PullRequest(("seagate", "asml")))
    repeat = workflow.run(PullRequest(("seagate", "asml")))
    repository = AcquisitionRepository(state / "acquisition")
    service = ArtifactQueryService(repository, firms, template)
    summaries = service.query(ArtifactQuery(limit=10)).items
    inventory = repository.artifact_metadata()
    evidence_by_form: dict[str, dict[str, object]] = {}
    for _adapter, artifact_id, form, firm_id, locator in POLICIES:
        first_item = next(
            item
            for firm in first.firms
            if firm.firm_id == firm_id
            for item in firm.artifacts
            if item.artifact_id == artifact_id
        )
        repeat_item = next(
            item
            for firm in repeat.firms
            if firm.firm_id == firm_id
            for item in firm.artifacts
            if item.artifact_id == artifact_id
        )
        summary = next(
            (
                item
                for item in summaries
                if item.firm_id == firm_id
                and item.canonical_artifact_id == artifact_id
            ),
            None,
        )
        if summary is None:
            evidence_by_form[form] = {
                "firm_id": firm_id,
                "issuer_cik": locator.removeprefix("CIK:").lstrip("0"),
                "artifact_id": artifact_id,
                "first_outcome": first_item.outcome.value,
                "rerun_outcome": repeat_item.outcome.value,
                "query_visible": False,
                "browser_contract_visible": False,
                "diagnostic": first_item.diagnostic,
            }
            continue
        detail = service.detail(summary.document_id)
        content = service.content(summary.document_id).content
        evidence_by_form[form] = {
            "firm_id": firm_id,
            "issuer_cik": locator.removeprefix("CIK:").lstrip("0"),
            "artifact_id": artifact_id,
            "adapter_id": detail.retrieval_adapter_id,
            "accession": detail.observation.provider_identifiers["sec_accession"],
            "primary_document": detail.observation.provider_identifiers[
                "sec_primary_document"
            ],
            "filing_date": detail.observation.metadata["filing_date"],
            "acceptance_datetime": detail.observation.metadata[
                "acceptance_datetime"
            ],
            "period_of_report": detail.observation.metadata["period_of_report"],
            "document_id": summary.document_id,
            "artifact_id_sha256": summary.artifact_id,
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "content_bytes": len(content),
            "first_outcome": first_item.outcome.value,
            "rerun_outcome": repeat_item.outcome.value,
            "query_visible": True,
            "browser_contract_visible": True,
        }
    before = tuple(summaries)
    with patch.object(socket, "socket", side_effect=AssertionError("network blocked")):
        restarted_repository = AcquisitionRepository(state / "acquisition")
        restarted = ArtifactQueryService(restarted_repository, firms, template)
        after = restarted.query(ArtifactQuery(limit=10)).items
        integrity = restarted_repository.verify_integrity()
    checks = {
        "four_forms": set(evidence_by_form) == {"10-Q", "8-K", "20-F", "6-K"},
        "first_success": len(evidence_by_form) == 4
        and all(
            item["first_outcome"] == "success" for item in evidence_by_form.values()
        ),
        "rerun_no_change": len(evidence_by_form) == 4
        and all(
            item["rerun_outcome"] == "no_change" for item in evidence_by_form.values()
        ),
        "four_artifacts": len(inventory) == 4,
        "four_observations": len(repository.observations()) == 4,
        "restart_equivalent": after == before,
        "integrity": integrity["result"] == "PASS",
    }
    return {
        "mode": "production-pull-workflow",
        "readiness": readiness,
        "adapter_capabilities": workflow.adapter_capabilities(),
        "first_pull": asdict(first),
        "repeat_pull": asdict(repeat),
        "forms": evidence_by_form,
        "artifact_inventory": inventory,
        "provider_usage": provider.usage(),
        "network_blocked_restart": True,
        "integrity": integrity,
        "checks": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
    }


def fixture_proof() -> int:
    """Run the deterministic acceptance suite as the ordinary offline proof."""
    import unittest

    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_task022")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def live_config() -> int:
    runtime_user_agent()
    print(
        json.dumps(
            {
                "result": "PASS",
                "network_activity": False,
                "runtime_identity_present": True,
                "runtime_identity_emitted": False,
                "forms": [item[2] for item in POLICIES],
                "firms": {"seagate": "1137789", "asml": "937966"},
                "amendment_policy": "exact base form only",
                "expected_operations": 12,
                "maximum_attempts_per_operation": 2,
                "combined_attempt_ceiling": 24,
                "timeout_seconds_per_attempt": 20,
                "minimum_request_interval_seconds": 0.5,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def live_pull(state: Path, evidence: Path, confirmed: bool) -> int:
    if not confirmed:
        raise RuntimeError("live SEC access requires --confirm-live-sec")
    if evidence.exists():
        raise RuntimeError(f"refusing to replace existing live evidence: {evidence}")
    runtime_user_agent()
    result = execute(state, SecProviderClient(runtime_user_agent))
    result["mode"] = "gated-live-sec-edgar"
    result["runtime_identity_present"] = True
    result["runtime_identity_emitted"] = False
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fixture-proof")
    commands.add_parser("live-config")
    live = commands.add_parser("live-pull")
    live.add_argument("--state", type=Path, required=True)
    live.add_argument("--evidence", type=Path, required=True)
    live.add_argument("--confirm-live-sec", action="store_true")
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        with tempfile.TemporaryDirectory(prefix="task022-fixture-"):
            return fixture_proof()
    if arguments.command == "live-config":
        return live_config()
    return live_pull(arguments.state, arguments.evidence, arguments.confirm_live_sec)


if __name__ == "__main__":
    raise SystemExit(main())
