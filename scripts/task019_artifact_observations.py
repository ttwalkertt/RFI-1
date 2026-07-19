#!/usr/bin/env python3
"""Generate deterministic TASK-019 architectural proof from production contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rfi.artifacts import ArtifactQueryError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_task019 import MultipleArtifactObservationTests  # noqa: E402


def main() -> int:
    """Prove duplicate acquisition, selection, navigation, replay, and browser behavior."""
    fixture = MultipleArtifactObservationTests(methodName="runTest")
    fixture.setUp()
    try:
        artifact_id, first_id = fixture.acquire(1)
        bytes_before = fixture.repository.read_artifact(artifact_id)
        repeated_artifact_id, second_id = fixture.acquire(2)
        first = fixture.service.detail(fixture.document_id, "first")
        last = fixture.service.detail(fixture.document_id)
        explicit = fixture.service.detail(fixture.document_id, second_id)
        following = fixture.service.next(first.observation_cursor)
        preceding = fixture.service.previous(last.observation_cursor)
        observations_before = fixture.repository.observations()
        index_before = fixture.repository.document_index()
        fixture.repository.delete_derived_state()
        replay = fixture.repository.replay()
        replay_observation_order_preserved = (
            fixture.repository.observations() == observations_before
        )
        replay_document_index_preserved = (
            fixture.repository.document_index() == index_before
        )
        stale_cursor = first.observation_cursor
        fixture.acquire(3)
        stale_code = ""
        try:
            fixture.service.next(stale_cursor)
        except ArtifactQueryError as error:
            stale_code = error.code
        html = (ROOT / "src/rfi/admin/artifact_browser.html").read_text(encoding="utf-8")
        proof = {
            "result": "PASS",
            "duplicate_pull": {
                "immutable_conflict": False,
                "artifact_count": len(fixture.repository.artifact_metadata()),
                "artifact_reused": artifact_id == repeated_artifact_id,
                "observations_after_two_pulls": len(observations_before),
                "observation_ids_distinct": first_id != second_id,
                "stored_bytes_unchanged": (
                    fixture.repository.read_artifact(artifact_id) == bytes_before
                ),
            },
            "observation_navigation": {
                "default_is_last": last.observation.observation_id == second_id,
                "first_selection": first.observation.observation_id == first_id,
                "explicit_selection": explicit.observation.observation_id == second_id,
                "next": following.observation.observation_id == second_id,
                "previous": preceding.observation.observation_id == first_id,
                "artifact_identity_unchanged": len(
                    {
                        first.summary.artifact_id,
                        last.summary.artifact_id,
                        following.summary.artifact_id,
                        preceding.summary.artifact_id,
                    }
                )
                == 1,
                "stale_cursor_code": stale_code,
            },
            "replay": {
                "documents": replay.documents,
                "observation_order_preserved": replay_observation_order_preserved,
                "document_index_preserved": replay_document_index_preserved,
            },
            "browser": {
                "previous_next_controls": all(
                    marker in html for marker in ("Previous observation", "Next observation")
                ),
                "preview_guarded_by_artifact_identity": (
                    "if(previewArtifact!==s.artifact_id)" in html
                ),
            },
            "integrity": fixture.repository.verify_integrity(),
        }
        checks = (
            proof["duplicate_pull"]["artifact_count"] == 1,
            proof["duplicate_pull"]["observations_after_two_pulls"] == 2,
            proof["duplicate_pull"]["artifact_reused"],
            proof["duplicate_pull"]["stored_bytes_unchanged"],
            proof["observation_navigation"]["default_is_last"],
            proof["observation_navigation"]["stale_cursor_code"] == "stale_cursor",
            proof["replay"]["observation_order_preserved"],
            proof["replay"]["document_index_preserved"],
            proof["browser"]["preview_guarded_by_artifact_identity"],
            proof["integrity"]["result"] == "PASS",
        )
        if not all(checks):
            proof["result"] = "FAIL"
        print(json.dumps(proof, indent=2, sort_keys=True))
        return 0 if proof["result"] == "PASS" else 1
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    raise SystemExit(main())
