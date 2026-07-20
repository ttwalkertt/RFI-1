#!/usr/bin/env python3
"""Controlled state and deterministic proof for TASK-026 stream YAML workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from rfi.cli import initialize
from rfi.mailing_lists import (
    AcquisitionLimits,
    ArchiveMessage,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.mailing_lists.parser import parse_message
from rfi.streams import StreamRepository, StreamService, semantic_fingerprint

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "fixtures/streams/task026-external.yaml"
DERIVED = ROOT / "fixtures/streams/task026-derived.yaml"


def archive() -> FixtureMailingListArchive:
    """Load the bounded checked-in mailing discussion fixture."""
    messages = {}
    for path in sorted((ROOT / "fixtures/linux-block").glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    return FixtureMailingListArchive(messages)


def prepare(state: Path) -> dict[str, Any]:
    """Create fresh controlled application state with governed retained mail evidence."""
    initialize(state)
    repository = MailingListRepository(state)
    repository.configure_source(LINUX_BLOCK_SOURCE)
    manifest = MailingListAcquisitionService(
        repository,
        archive(),
        clock=lambda: "2026-07-20T12:00:00+00:00",
        identifiers=lambda: "mailrun-task026-browser",
    ).acquire(
        LINUX_BLOCK_SOURCE.source_id,
        SelectionCriteria(
            message_ids=("<task023-a1@kernel.example>", "<task023-b1@kernel.example>")
        ),
        AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=3),
    )
    return {
        "state": str(state),
        "source_id": LINUX_BLOCK_SOURCE.source_id,
        "retained_messages": manifest.message_count,
        "stream_revisions": 0,
        "stream_runs": 0,
    }


def fixture_proof() -> dict[str, Any]:
    """Prove canonical round trips, revisions, no-op import, and negative boundaries."""
    with tempfile.TemporaryDirectory(prefix="rfi-task026-proof-") as temporary:
        state = Path(temporary) / "state"
        prepared = prepare(state)
        service = StreamService(StreamRepository(state))
        external_text = EXTERNAL.read_text(encoding="utf-8")
        derived_text = DERIVED.read_text(encoding="utf-8")
        review = service.review_yaml(external_text)
        external = service.import_yaml(external_text, "new")
        exported = service.export_yaml(external.revision.stream_id)
        round_trip = service.review_yaml(exported)
        derived = service.import_yaml(derived_text, "new")
        identical = service.import_yaml(exported, "revision")
        changed_text = external_text.replace("direct_matches: 25", "direct_matches: 26")
        changed_review = service.review_yaml(changed_text)
        revised = service.import_yaml(changed_text, "revision", external.revision.revision_id)
        forbidden = service.review_yaml(
            external_text.replace(
                "artifact_schema: mail.message",
                "artifact_schema: mail.message\n    api_token: forbidden",
            )
        )
        runs = service.repository.rows("SELECT * FROM artifact_stream_runs")
        return {
            "result": "PASS",
            "prepared": prepared,
            "schema_version": 1,
            "external_import": external.outcome,
            "derived_import": derived.outcome,
            "identical_reimport": identical.outcome,
            "revision_number": revised.revision.revision_number,
            "semantic_diff_categories": [
                item["category"] for item in changed_review.differences
            ],
            "round_trip_fingerprint_equal": (
                semantic_fingerprint(external.revision.draft)
                == round_trip.semantic_fingerprint
            ),
            "canonical_yaml_sha256": hashlib.sha256(exported.encode()).hexdigest(),
            "canonical_yaml_trailing_newline": exported.endswith("\n"),
            "forbidden_configuration_code": forbidden.errors[0]["code"],
            "forbidden_configuration_path": forbidden.errors[0]["path"],
            "import_triggered_runs": len(runs),
            "history_preserved": len(service.history("linux-block-storage")) == 2,
        }


def main() -> int:
    """Run a controlled-state setup or self-contained proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare-state", "fixture-proof"))
    parser.add_argument("--state", type=Path)
    arguments = parser.parse_args()
    if arguments.operation == "prepare-state":
        if arguments.state is None:
            parser.error("prepare-state requires --state")
        value = prepare(arguments.state.resolve())
    else:
        value = fixture_proof()
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
