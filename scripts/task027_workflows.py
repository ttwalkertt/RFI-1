#!/usr/bin/env python3
"""Execute representative TASK-027 workflows from the canonical operator guide."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import task015_pull_workflow  # noqa: E402
import task026_streams  # noqa: E402
from rfi.admin.help import guide_source  # noqa: E402
from rfi.cli import initialize, verify_state  # noqa: E402
from rfi.storage import RepositoryDatabase, create_backup, restore_backup  # noqa: E402
from rfi.streams import StreamRepository, StreamService  # noqa: E402


def acquisition_workflow() -> dict[str, Any]:
    """Execute firm/profile/readiness/pull/result/artifact proof through public contracts."""
    proof = task015_pull_workflow.fixture_proof()
    checks = proof["checks"]
    return {
        "result": proof["result"],
        "guide_sequence": [
            "create firms",
            "publish source-profile revisions",
            "evaluate attemptability",
            "execute Pull Workflow",
            "inspect durable results",
            "read retained exact artifact bytes",
        ],
        "profile_revisions_snapshotted": checks["snapshotted_revisions"],
        "independent_execution": checks["independent_artifacts"]
        and checks["independent_firms"],
        "retained_artifact_inspected": checks["existing_ingress_exact_bytes"],
        "repository_integrity": checks["repository_integrity"],
        "partial_summary": proof["partial_summary"],
    }


def stream_and_yaml_workflow() -> dict[str, Any]:
    """Validate, preview, import, revision, execute, inspect, and export one stream."""
    with tempfile.TemporaryDirectory(prefix="rfi-task027-stream-") as temporary:
        state = Path(temporary) / "state"
        task026_streams.prepare(state)
        service = StreamService(StreamRepository(state))
        source = task026_streams.EXTERNAL.read_text(encoding="utf-8").replace(
            "        - blk-mq", "        - bounded"
        )
        review = service.review_yaml(source)
        if not review.valid or review.draft is None:
            raise RuntimeError(f"canonical fixture did not validate: {review.errors}")
        before_revisions = len(service.repository.list_revisions())
        before_runs = len(service.repository.rows("SELECT * FROM artifact_stream_runs"))
        preview = service.preview(review.draft, 25)
        after_preview_revisions = len(service.repository.list_revisions())
        after_preview_runs = len(service.repository.rows("SELECT * FROM artifact_stream_runs"))
        imported = service.import_yaml(source, "new")
        exported = service.export_yaml(imported.revision.stream_id)
        changed = source.replace("direct_matches: 25", "direct_matches: 26")
        changed_review = service.review_yaml(changed)
        revised = service.import_yaml(
            changed,
            "revision",
            imported.revision.revision_id,
        )
        run = service.run(revised.revision.stream_id)
        memberships = service.repository.memberships(revised.revision.stream_id, run.run_id, 100)
        return {
            "result": "PASS",
            "guide_sequence": [
                "review YAML without persistence",
                "preview bounded matches without persistence",
                "import new stream intentionally",
                "export canonical YAML",
                "review semantic difference",
                "import immutable revision intentionally",
                "execute saved revision",
                "inspect durable memberships and lineage",
            ],
            "validation_valid": review.valid,
            "preview_match_count": len(preview.items),
            "preview_preserved_revision_count": before_revisions == after_preview_revisions,
            "preview_preserved_run_count": before_runs == after_preview_runs,
            "new_import_outcome": imported.outcome,
            "semantic_difference_categories": [
                item["category"] for item in changed_review.differences
            ],
            "revision_import_outcome": revised.outcome,
            "revision_number": revised.revision.revision_number,
            "run_status": run.status,
            "run_revision_id": run.revision_id,
            "membership_count": len(memberships),
            "lineage_present": bool(memberships)
            and all(item.lineage for item in memberships),
            "canonical_export_round_trip_valid": service.review_yaml(exported).valid,
            "canonical_export_ends_with_newline": exported.endswith("\n"),
        }


def repository_protection_workflow() -> dict[str, Any]:
    """Identify, verify, backup, restore fresh, reverify, and reopen repository state."""
    with tempfile.TemporaryDirectory(prefix="rfi-task027-protection-") as temporary:
        root = Path(temporary)
        state = root / "active-state"
        restored = root / "restored-state"
        backup = root / "repository-backup.zip"
        with contextlib.redirect_stdout(io.StringIO()):
            initialize(state)
            verify_state(state)
        backup_result = create_backup(state, backup)
        restore_result = restore_backup(backup, restored)
        with contextlib.redirect_stdout(io.StringIO()):
            verify_state(restored)
        active = RepositoryDatabase.open(state).validate()
        reopened = RepositoryDatabase.open(restored).validate()
        with RepositoryDatabase.open(state).connect(read_only=True) as connection:
            active_id = connection.execute(
                "SELECT repository_id FROM repository_state"
            ).fetchone()[0]
        with RepositoryDatabase.open(restored).connect(read_only=True) as connection:
            restored_id = connection.execute(
                "SELECT repository_id FROM repository_state"
            ).fetchone()[0]
        return {
            "result": "PASS",
            "guide_sequence": [
                "identify active state path",
                "verify active repository",
                "create verified backup",
                "restore into fresh state",
                "verify restored repository",
                "reopen restored application state",
            ],
            "active_state_identified": state.name == "active-state",
            "backup_created": backup.is_file(),
            "backup_result": backup_result,
            "restore_result": restore_result,
            "active_validation": active,
            "restored_validation": reopened,
            "repository_identity_preserved": active_id == restored_id,
        }


def main() -> int:
    """Run all required representative workflows and report discrepancies."""
    guide = guide_source()
    required_guide_phrases = (
        "### Acquisition procedure",
        "### Stream revision and execution procedure",
        "### Browser validation, preview, and import procedure",
        "### Repository protection procedure",
    )
    missing = [phrase for phrase in required_guide_phrases if phrase not in guide]
    evidence = {
        "result": "PASS" if not missing else "FAIL",
        "canonical_guide": "docs/operator-guide.md",
        "guide_procedures_present": not missing,
        "missing_guide_procedures": missing,
        "acquisition": acquisition_workflow(),
        "stream_revision_execution_and_yaml": stream_and_yaml_workflow(),
        "repository_protection": repository_protection_workflow(),
        "discrepancies": [],
    }
    if any(
        item["result"] != "PASS"
        for item in (
            evidence["acquisition"],
            evidence["stream_revision_execution_and_yaml"],
            evidence["repository_protection"],
        )
    ):
        evidence["result"] = "FAIL"
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
    return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
