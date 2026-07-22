#!/usr/bin/env python3
"""Deterministic end-to-end proof for the TASK-028 operator workflow façade."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path

from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    ArchiveMessage,
    FixtureMailingListArchive,
    LinuxMailingListWorkflowService,
    MailingListQueryService,
    MailingListRepository,
    MailingListSource,
    MailingListSourceService,
)
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamRepository, StreamService

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/linux-block"


class ProofArchive(FixtureMailingListArchive):
    """Fixture transport with the same health-probe contract as Lore."""

    def probe(self) -> dict[str, str]:
        return {
            "title": "linux-block.vger.kernel.org archive mirror",
            "updated": "2026-07-20T12:00:00Z",
            "canonical_url": "https://lore.kernel.org/linux-block/",
        }


def archive_factory(_source: MailingListSource) -> ProofArchive:
    """Return the checked-in connected-discussion archive."""
    messages: dict[str, ArchiveMessage] = {}
    for path in sorted(FIXTURES.glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(
                raw, f"fixture:{path.name}"
            )
    return ProofArchive(messages)


def service(state: Path) -> LinuxMailingListWorkflowService:
    """Compose the façade over the production repositories and services."""
    repository = MailingListRepository(state)
    return LinuxMailingListWorkflowService(
        repository,
        MailingListSourceService(repository),
        StreamService(StreamRepository(state)),
        MailingListQueryService(repository),
        archive_factory=archive_factory,
        today=lambda: date(2026, 7, 20),
    )


def main() -> int:
    """Prove review isolation, creation, test evidence, and restart readiness."""
    with tempfile.TemporaryDirectory(prefix="rfi-task028-proof-") as temporary:
        state = Path(temporary) / "state"
        RepositoryDatabase.initialize(state)
        FirmRepository.initialize(state / "firm-catalog")
        workflow = service(state)
        draft = {
            "archive_url": "https://lore.kernel.org/linux-block/",
            "stream_name": "Linux Block Discussions",
            "description": "Bounded storage evidence",
            "date_from": "2026-07-16",
            "date_through": "2026-07-16",
            "keywords": ["deterministic queue"],
            "subjects": [],
            "participants": [],
            "seed_limit": 5,
            "total_limit": 20,
            "descendant_depth": 3,
        }
        review = workflow.review(draft)
        after_review = {
            "sources": len(workflow.repository.sources()),
            "streams": len(workflow.stream_service.list_streams()),
        }
        archive = workflow.validate_archive(draft)
        created = workflow.create(draft)
        if created.revision is None:
            raise RuntimeError(created.message)
        tested = workflow.test(created.revision.stream_id)
        acquisition = tested.acquisition
        if acquisition is None or isinstance(acquisition, dict):
            raise RuntimeError("successful proof did not return an acquisition manifest")
        exact = workflow.result(acquisition.run_id)
        restarted = service(state)
        saved = restarted.saved()[0]
        reasons = acquisition.inclusion_reasons
        result = {
            "result": "PASS",
            "operator_outcome": (
                "bounded Linux Block discussion evidence is durable, inspectable, and ready"
            ),
            "review": {
                "source_id": review.source.source_id,
                "stream_id": review.stream.stream_id,
                "records_to_create": review.records_to_create,
                "state_after_review": after_review,
            },
            "archive_validation": asdict(archive),
            "creation": {
                "status": created.status,
                "source_created": created.source_created,
                "revision_number": created.revision.revision_number,
            },
            "test": {
                "status": tested.status,
                "configuration_ready": tested.configuration_ready,
                "test_evidence_status": tested.test_evidence_status,
                "message_count": acquisition.message_count,
                "relationship_count": acquisition.relationship_count,
                "direct_matches": reasons.get("seed_match", 0),
                "context_only": sum(
                    count for reason, count in reasons.items() if reason != "seed_match"
                ),
                "connectivity_state": acquisition.state.value,
                "exact_run_messages": len(exact["messages"]),
                "all_have_lore_links": all(
                    item.source_link.startswith("https://lore.kernel.org/linux-block/")
                    for item in tested.messages
                ),
            },
            "restart": {
                "stream_id": saved.stream_id,
                "revision_number": saved.revision_number,
                "configuration_status": saved.configuration_status,
                "test_evidence_status": saved.test_evidence_status,
                "draft_equal": asdict(restarted.draft_for(saved.stream_id))
                == {
                    **draft,
                    "keywords": tuple(draft["keywords"]),
                    "subjects": (),
                    "participants": (),
                },
            },
        }
        checks = (
            after_review == {"sources": 0, "streams": 0},
            created.status == "created",
            tested.status == "ready",
            len(exact["messages"]) == acquisition.message_count,
            saved.configuration_status == "ready",
            saved.test_evidence_status == "complete_connected",
            result["restart"]["draft_equal"],
        )
        if not all(checks):
            result["result"] = "FAIL"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
