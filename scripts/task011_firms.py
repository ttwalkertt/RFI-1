#!/usr/bin/env python3
"""Operate and deterministically prove the TASK-011 target-firm catalog."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin.field_definitions import FIELD_DEFINITIONS  # noqa: E402
from rfi.firms import (  # noqa: E402
    FirmDraft,
    FirmError,
    FirmIdentifier,
    FirmReference,
    FirmRepository,
    FirmService,
    FirmStatus,
    SourceDiscoveryHint,
    sample_firms,
)


def seed(repository: FirmRepository) -> list[str]:
    """Create missing sample firms through the catalog public contract."""
    existing = {item.firm_id for item in repository.lookup()}
    created: list[str] = []
    for draft in sample_firms():
        if draft.firm_id not in existing:
            repository.create(draft)
            created.append(draft.firm_id)
    return created


def fixture_proof() -> dict[str, Any]:
    """Prove consulting seeds, revision safety, conflicts, restart, and integration references."""
    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "firm-catalog"
        repository = FirmRepository.initialize(state)
        seeded = seed(repository)
        service = FirmService(repository)
        draft = FirmDraft(
            firm_id="proof-storage",
            canonical_name="Proof Storage",
            aliases=("ProofCo",),
            identifiers=(FirmIdentifier("ticker", "PRF", "NASDAQ"),),
            domains=("proof-storage.example",),
            sector="Technology",
            industry="Data storage",
            technology_focus=("hard disk drives",),
            source_hints=(SourceDiscoveryHint("investor-relations", "ir.proof.example"),),
            notes="Created through the public firm service.",
            status=FirmStatus.ACTIVE,
            valid_from="2024-01-01",
        )
        created = service.create(asdict(draft))
        revised_draft = replace(
            draft,
            aliases=("ProofCo", "Proof Storage Systems"),
            notes="Updated through immutable revision semantics.",
        )
        revised = service.revise(created.firm_id, asdict(revised_draft), created.revision_id)
        conflict = replace(
            draft,
            firm_id="conflicting-proof",
            identifiers=(FirmIdentifier("ticker", "STX", "NASDAQ"),),
            domains=("conflicting-proof.example",),
        )
        try:
            service.create(asdict(conflict))
        except FirmError as error:
            conflict_message = str(error)
        else:
            raise RuntimeError("expected identifier conflict was not detected")
        reopened = FirmRepository.open(state)
        persisted = reopened.get(created.firm_id)
        reference = FirmReference(persisted.firm_id, persisted.revision_id)
        console = (ROOT / "src/rfi/admin/firms.html").read_text(encoding="utf-8")
        checks = {
            "seeded_consulting_firms": seeded == ["seagate", "western-digital", "toshiba"],
            "search_and_filters": len(reopened.lookup("storage", sector="Technology")) >= 3,
            "typed_browser_editor": all(
                marker in console
                for marker in ("identifiers", "relationships", "source_hints", "repeat-row")
            ),
            "central_field_help": all(
                name in FIELD_DEFINITIONS
                for name in ("firm_id", "identifiers", "domains", "relationships", "source_hints")
            ),
            "input_preservation_and_dirty_protection": all(
                marker in console for marker in ("beforeunload", "Your draft remains open")
            ),
            "identifier_conflict": "conflicting firm identifier" in conflict_message,
            "immutable_revision": revised.revision_number == 2
            and len(reopened.history(created.firm_id)) == 2,
            "restart_persistence": persisted.aliases[-1] == "Proof Storage Systems",
            "stable_integration_reference": reference.firm_id == persisted.firm_id,
            "integrity": reopened.verify()["result"] == "PASS",
        }
        if not all(checks.values()):
            raise RuntimeError(f"TASK-011 fixture proof failed: {checks}")
        return {
            "result": "PASS",
            "checks": checks,
            "seeded_firms": [asdict(service.detail(item)) for item in seeded],
            "created_and_revised": asdict(persisted),
            "conflict": conflict_message,
            "integration_reference": asdict(reference),
        }


def main() -> int:
    """Run one deterministic task proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("fixture-proof",))
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        print(json.dumps(fixture_proof(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
