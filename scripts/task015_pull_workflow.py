#!/usr/bin/env python3
"""Deterministically prove the TASK-015 Pull Workflow architecture and outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition import (  # noqa: E402
    AcquisitionRepository,
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    FailureClass,
    RetrievalResult,
)
from rfi.acquisition.contracts import DiscoveryProvenance, SourceProfile  # noqa: E402
from rfi.firms import FirmRepository, sample_firms  # noqa: E402
from rfi.pull import (  # noqa: E402
    ArtifactOutcome,
    PullRequest,
    PullRunRepository,
    PullStage,
    PullStatus,
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


def clock() -> str:
    """Return deterministic proof time."""
    return "2026-07-18T12:00:00Z"


class ProofAdapter:
    """Exact-byte deterministic adapter exercising the production engine boundary."""

    mechanism = "direct_url"

    def __init__(self, content: dict[str, bytes], failures: set[str]) -> None:
        self.content = content
        self.failures = failures

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        if continuation is not None:
            raise RuntimeError("proof direct adapter received continuation")
        digest = hashlib.sha256(profile.source_id.encode()).hexdigest()
        return DiscoveryPage(
            (
                AdapterCandidate(
                    f"candidate-{digest[:20]}",
                    str(profile.policy["document_id"]),
                    1,
                    f"revision-{digest[20:40]}",
                    DiscoveryProvenance(
                        clock(),
                        self.mechanism,
                        locations=(str(profile.configuration["url"]),),
                    ),
                ),
            ),
            None,
        )

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        del candidate
        url = str(profile.configuration["url"])
        if url in self.failures:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"proof retrieval failure: {url}",
                False,
            )
        return RetrievalResult(
            self.content[url],
            "text/plain",
            clock(),
            self.mechanism,
        )


def direct(url: str) -> tuple[RetrievalCandidate, ...]:
    """Create one priority-one direct URL retrieval candidate."""
    return (RetrievalCandidate("direct_url", 1, url=url),)


def draft(
    firm_id: str,
    template: Any,
    configured: dict[str, tuple[bool, tuple[RetrievalCandidate, ...]]],
) -> SourceProfileDraft:
    """Disable unlisted artifacts so proof outcomes remain explicit."""
    return SourceProfileDraft(
        firm_id,
        tuple(
            SourceProfileItem(
                artifact.artifact_id,
                configured.get(artifact.artifact_id, (False, ()))[0],
                configured.get(artifact.artifact_id, (False, ()))[1],
            )
            for artifact in template.artifacts
        ),
    )


def fixture_proof() -> dict[str, Any]:
    """Prove stage, revision, failure isolation, outcome, and ingress semantics."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        template = load_canonical_template()
        firms = FirmRepository.initialize(root / "firm-catalog")
        for value in sample_firms()[:2]:
            firms.create(value)
        profiles = SourceProfileRepository.initialize(root / "source-profiles", template)
        acquisition = AcquisitionRepository(root / "acquisition")
        exact_bytes = b"TASK-015 authoritative whole artifact\n"
        adapter = ProofAdapter(
            {
                "https://proof.test/shared": exact_bytes,
                "https://proof.test/later": exact_bytes,
            },
            {"https://proof.test/fail"},
        )
        identifiers = iter((f"proof{index}" for index in range(10)))
        workflow = PullWorkflow(
            firms,
            profiles,
            template,
            acquisition,
            RetrievalAdapterRegistry(
                (
                    RetrievalAdapterRegistration(
                        RetrievalAdapterCapability(
                            "direct-url", (), ("direct_url",)
                        ),
                        adapter,
                    ),
                )
            ),
            PullRunRepository(root / "pull-workflows"),
            clock,
            identifiers.__next__,
        )
        seagate_revision = profiles.publish(
            draft(
                "seagate",
                template,
                {
                    "annual_report": (True, direct("https://proof.test/fail")),
                    "earnings_release": (True, direct("https://proof.test/later")),
                    "press_release": (
                        True,
                        (RetrievalCandidate("feed", 1, url="https://proof.test/feed"),),
                    ),
                    "corporate_news": (True, ()),
                },
            ),
            None,
        )
        western_revision = profiles.publish(
            draft(
                "western-digital",
                template,
                {"annual_report": (True, direct("https://proof.test/shared"))},
            ),
            None,
        )
        partial = workflow.run(PullRequest(("seagate", "western-digital")))
        repeat = workflow.run(PullRequest(("western-digital",)))
        failed_revision = profiles.publish(
            draft(
                "seagate",
                template,
                {"annual_report": (True, direct("https://proof.test/fail"))},
            ),
            seagate_revision.source_profile_revision_id,
        )
        failed = workflow.run(PullRequest(("seagate",)))
        partial_outcomes = {
            artifact.outcome
            for firm in partial.firms
            for artifact in firm.artifacts
        }
        stored_ids = partial.firms[0].artifacts[1].attempts[0].artifact_ids
        durable = workflow.results(partial.run_id)
        checks = {
            "documented_stage_order": partial.completed_stages == tuple(PullStage),
            "multiple_firms": [item.firm_id for item in partial.firms]
            == ["seagate", "western-digital"],
            "snapshotted_revisions": [
                item["source_profile_revision_id"]
                for item in durable["profile_snapshots"]
            ]
            == [
                seagate_revision.source_profile_revision_id,
                western_revision.source_profile_revision_id,
            ],
            "independent_artifacts": partial.firms[0].status == PullStatus.PARTIAL
            and partial.summary.success == 1,
            "independent_firms": partial.firms[1].status == PullStatus.COMPLETED,
            "all_primary_outcomes": partial_outcomes
            == {
                ArtifactOutcome.SUCCESS,
                ArtifactOutcome.DUPLICATE,
                ArtifactOutcome.SKIPPED,
                ArtifactOutcome.CONFIGURATION_PROBLEM,
                ArtifactOutcome.RETRIEVAL_FAILURE,
            },
            "no_change": repeat.summary.no_change == 1,
            "partial_workflow": partial.status == PullStatus.PARTIAL,
            "successful_workflow": repeat.status == PullStatus.COMPLETED,
            "failed_workflow": failed.status == PullStatus.FAILED
            and failed.firms[0].source_profile_revision_id
            == failed_revision.source_profile_revision_id,
            "existing_ingress_exact_bytes": len(stored_ids) == 1
            and acquisition.read_artifact(stored_ids[0]) == exact_bytes,
            "repository_integrity": acquisition.verify_integrity()["result"] == "PASS",
            "unsupported_mode_stub": "No adapter available"
            in partial.firms[0].artifacts[2].diagnostic,
        }
        if not all(checks.values()):
            raise RuntimeError(f"TASK-015 workflow proof failed: {checks}")
        return {
            "result": "PASS",
            "checks": checks,
            "partial_run": partial.run_id,
            "partial_summary": as_json(partial.summary),
            "repeat_summary": as_json(repeat.summary),
            "failed_summary": as_json(failed.summary),
            "stage_order": [item.value for item in partial.completed_stages],
            "snapshotted_revision_ids": [
                seagate_revision.source_profile_revision_id,
                western_revision.source_profile_revision_id,
            ],
        }


def as_json(value: Any) -> dict[str, Any]:
    """Convert one dataclass to deterministic JSON without importing private helpers."""
    return json.loads(json.dumps(value.__dict__))


def main() -> int:
    """Run the requested deterministic proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("fixture-proof",))
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        print(json.dumps(fixture_proof(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
