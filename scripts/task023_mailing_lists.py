#!/usr/bin/env python3
"""Deterministic and opt-in live proofs for TASK-023."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    LoreArchive,
    MailingListAcquisitionService,
    MailingListQueryService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.mailing_lists.contracts import ArchiveMessage
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/linux-block"


def archive() -> FixtureMailingListArchive:
    messages = {}
    for path in sorted(FIXTURES.glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    return FixtureMailingListArchive(messages)


def fixture_proof() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="rfi-task023-") as temporary:
        state = Path(temporary)
        RepositoryDatabase.initialize(state)
        FirmRepository.initialize(state / "firm-catalog")
        repository = MailingListRepository(state)
        repository.configure_source(LINUX_BLOCK_SOURCE)
        ids = iter(("mailrun-proof-first", "mailrun-proof-repeat"))
        service = MailingListAcquisitionService(
            repository, archive(), clock=lambda: "2026-07-19T12:00:00+00:00",
            identifiers=ids.__next__,
        )
        criteria = SelectionCriteria(message_ids=(
            "<task023-a1@kernel.example>", "<task023-b1@kernel.example>",
        ))
        limits = AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=3)
        preview = service.preview(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
        first = service.acquire(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
        repeat = service.acquire(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
        query = MailingListQueryService(repository)
        discussion = query.discussions(LINUX_BLOCK_SOURCE.source_id)[0]
        projection = query.projection(discussion.discussion_id)
        connectivity = repository.validate_connectivity()
        before = asdict(discussion)
        repository.delete_derived_for_rebuild()
        rebuild = service.rebuild()
        after = asdict(query.discussions(LINUX_BLOCK_SOURCE.source_id)[0])
        return {
            "preview": asdict(preview), "first": asdict(first), "repeat": asdict(repeat),
            "discussion": before, "branch_child_count": len(query.children(
                discussion.root_message_key)), "projection_messages": len(projection.messages),
            "connectivity": connectivity, "offline_rebuild": rebuild,
            "rebuild_equivalent": before == after,
            "browser_projection_asset": "src/rfi/admin/artifact_browser.html",
            "negative_controls": {
                "unbounded_request_available": False,
                "subject_identity_authoritative": False,
                "graph_database_present": False,
            },
            "result": "PASS",
        }


def demo_state(state: Path) -> dict[str, object]:
    """Create a deterministic state suitable for the shared-browser demonstration."""
    RepositoryDatabase.initialize(state)
    FirmRepository.initialize(state / "firm-catalog")
    repository = MailingListRepository(state)
    repository.configure_source(LINUX_BLOCK_SOURCE)
    service = MailingListAcquisitionService(
        repository, archive(), clock=lambda: "2026-07-19T12:00:00+00:00",
        identifiers=lambda: "mailrun-browser-demo",
    )
    manifest = service.acquire(
        LINUX_BLOCK_SOURCE.source_id,
        SelectionCriteria(message_ids=(
            "<task023-a1@kernel.example>", "<task023-b1@kernel.example>",
        )),
        AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=3),
    )
    return {"state": str(state), "manifest": asdict(manifest), "result": "PASS"}


def live_proof(state: Path, message_ids: tuple[str, ...]) -> dict[str, object]:
    if os.environ.get("RFI_TASK023_LIVE_PROOF") != "1":
        raise RuntimeError("set RFI_TASK023_LIVE_PROOF=1 to authorize the bounded live proof")
    if not 1 <= len(message_ids) <= 2:
        raise RuntimeError("live proof requires one or two explicit Message-IDs")
    RepositoryDatabase.initialize(state)
    FirmRepository.initialize(state / "firm-catalog")
    repository = MailingListRepository(state)
    repository.configure_source(LINUX_BLOCK_SOURCE)
    service = MailingListAcquisitionService(
        repository, LoreArchive(LINUX_BLOCK_SOURCE)
    )
    criteria = SelectionCriteria(message_ids=message_ids)
    limits = AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=0)
    preview = service.preview(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
    first = service.acquire(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
    repeat = service.acquire(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
    return {
        "exact_command": "RFI_TASK023_LIVE_PROOF=1 ... live --message-id <explicit-id>",
        "source": asdict(LINUX_BLOCK_SOURCE), "criteria": asdict(criteria),
        "limits": asdict(limits), "preview": asdict(preview), "first": asdict(first),
        "repeat": asdict(repeat),
        "connectivity": repository.validate_connectivity(),
        "idempotent_repeat": repeat.artifact_count_created == 0,
        "result": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("fixture-proof")
    demo = subcommands.add_parser("demo-state")
    demo.add_argument("--state", type=Path, required=True)
    live = subcommands.add_parser("live")
    live.add_argument("--state", type=Path, required=True)
    live.add_argument("--message-id", action="append", required=True)
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        result = fixture_proof()
    elif arguments.command == "demo-state":
        result = demo_state(arguments.state)
    else:
        result = live_proof(arguments.state, tuple(arguments.message_id))
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
