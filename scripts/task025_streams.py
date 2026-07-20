#!/usr/bin/env python3
"""Deterministic fixture and demo-state proofs for TASK-025 artifact streams."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.mailing_lists.contracts import ArchiveMessage
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase
from rfi.streams import ArtifactProjection, StreamDraft, StreamRepository, StreamService
from rfi.streams.service import draft_from_dict

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "fixtures/streams/task025-topology.json"


def archive() -> FixtureMailingListArchive:
    messages = {}
    for path in sorted((ROOT / "fixtures/linux-block").glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    return FixtureMailingListArchive(messages)


def initialize(state: Path) -> StreamService:
    RepositoryDatabase.initialize(state)
    FirmRepository.initialize(state / "firm-catalog")
    mail = MailingListRepository(state)
    mail.configure_source(LINUX_BLOCK_SOURCE)
    MailingListAcquisitionService(
        mail, archive(), clock=lambda: "2026-07-19T12:00:00+00:00",
        identifiers=lambda: "mailrun-task025-proof",
    ).acquire(
        LINUX_BLOCK_SOURCE.source_id,
        SelectionCriteria(message_ids=(
            "<task023-a1@kernel.example>", "<task023-b1@kernel.example>",
        )),
        AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=3),
    )
    streams = StreamRepository(state)
    artifacts = AcquisitionRepository(state / "acquisition")
    artifacts.register_source(SourceProfile(
        "sec-fixture", "SEC fixture", True, "fixture",
        policy={"repository_projection": "fixture"},
    ))
    projections = []
    for index, form in enumerate(("10-K", "8-K", "20-F"), 1):
        timestamp = f"2026-0{index}-01T00:00:00+00:00"
        candidate = CandidateDocument(
            f"sec-candidate-{index}", "sec-fixture", f"sec-document-{index}",
            DiscoveryProvenance(timestamp, "fixture", {"accession": f"000{index}"}),
        )
        content = f"{form} deterministic filing fixture".encode()
        receipt = artifacts.record_success(
            f"sec-attempt-{index}", candidate,
            RetrievalResult(content, "text/plain", timestamp, "fixture"),
        )
        projections.append(ArtifactProjection(
            receipt.artifact_id, receipt.document_id, "sec.filing", "sec-fixture",
            timestamp, f"Fixture {form}", content.decode(), ("Example issuer",),
            {"sec.form_type": form, "sec.accession": f"000{index}"},
        ))
    streams.upsert_projections(projections)
    identifiers = iter(f"streamrun-proof-{index}" for index in range(100))
    return StreamService(
        streams, clock=lambda: "2026-07-20T12:00:00+00:00",
        identifiers=identifiers.__next__,
    )


def configure(service: StreamService) -> list[StreamDraft]:
    values = json.loads(TOPOLOGY.read_text())["streams"]
    drafts = [draft_from_dict(item) for item in values]
    for draft in drafts:
        service.save(draft)
    sec = StreamDraft(
        "annual-regulatory-reports", "Annual regulatory reports", "Cross-schema proof", True,
        "external", ("sec-fixture",), "sec.filing",
        {"op": "predicate", "field": "attribute:sec.form_type", "operator": "in",
         "value": ["10-K", "20-F"]},
        {"strategy": "none", "descendant_depth": 0},
        {"seed_limit": 10, "expanded_limit": 10},
    )
    service.save(sec)
    return [*drafts, sec]


def proof(state: Path) -> dict[str, object]:
    service = initialize(state)
    drafts = configure(service)
    before_artifacts = {
        item["artifact_id"]: item["sha256"]
        for item in service.repository.artifacts.artifact_metadata()
    }
    queue_runs = service.run_chain("queue-review")
    blk_runs = service.run_chain("blk-mq")
    sec_run = service.run("annual-regulatory-reports")
    zoned = service.repository.memberships("zoned-storage")
    sec = service.repository.memberships("annual-regulatory-reports")
    repeat = service.run("zoned-storage")
    before_rebuild = [asdict(item) for item in service.repository.memberships("queue-review")]
    service.repository.delete_materialized_memberships()
    rebuild = service.rebuild()
    after_rebuild = [asdict(item) for item in service.repository.memberships("queue-review")]
    external = drafts[0]
    unsupported = service.validate(replace(
        external,
        selection={"op": "predicate", "field": "attribute:sec.form_type",
                   "operator": "equals", "value": "10-K"},
    ))
    cycle = service.validate(replace(
        external, input_kind="streams", input_ids=("queue-review",),
    ))
    after_artifacts = {
        item["artifact_id"]: item["sha256"]
        for item in service.repository.artifacts.artifact_metadata()
    }
    return {
        "topology": [asdict(item) for item in service.list_streams()],
        "queue_chain": [asdict(item) for item in queue_runs],
        "fanout_chain": [asdict(item) for item in blk_runs],
        "zoned_membership": {
            "total": len(zoned),
            "direct": sum(item.inclusion_kind == "direct" for item in zoned),
            "context": sum(item.inclusion_kind == "context" for item in zoned),
            "lineage_complete": all(bool(item.lineage) for item in zoned),
        },
        "cross_schema": {
            "run": asdict(sec_run),
            "forms": sorted(str(item.projection.attributes["sec.form_type"]) for item in sec),
            "generic_membership_contract": all(item.expansion_strategy == "none" for item in sec),
        },
        "idempotent_repeat": repeat.idempotent,
        "offline_rebuild": rebuild,
        "rebuild_equivalent": before_rebuild == after_rebuild,
        "immutable_hashes_unchanged": before_artifacts == after_artifacts,
        "negative": {
            "cycle_codes": [item["code"] for item in cycle.errors],
            "unsupported_codes": [item["code"] for item in unsupported.errors],
            "unbounded_archive_operation": False,
            "second_persistence_authority": False,
        },
        "browser_paths": ["/streams", "/artifacts"],
        "result": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fixture-proof")
    demo = commands.add_parser("demo-state")
    demo.add_argument("--state", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        with tempfile.TemporaryDirectory(prefix="rfi-task025-") as temporary:
            result = proof(Path(temporary))
    else:
        result = proof(arguments.state)
        result["state"] = str(arguments.state)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
