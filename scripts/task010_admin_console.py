#!/usr/bin/env python3
"""Deterministic TASK-010 schema-aware editor proof."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin.field_definitions import FIELD_DEFINITIONS  # noqa: E402
from rfi.concepts import ConceptRepository, ConceptService, sample_concepts  # noqa: E402


def fixture_proof() -> dict[str, object]:
    """Prove public-contract revision behavior and inspectable GUI capabilities."""
    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "catalog"
        repository = ConceptRepository.initialize(state)
        for draft in sample_concepts():
            repository.create(draft)
        service = ConceptService(repository)
        current = service.detail("hamr-shipments")
        methods = list(current.methods)
        capacity_index = next(
            index
            for index, method in enumerate(methods)
            if method.method_id == "capacity-shipped"
        )
        methods[capacity_index] = replace(
            methods[capacity_index],
            units=("exabyte", "TB"),
        )
        payload = asdict(ConceptRepository.to_draft(current))
        payload["methods"] = [asdict(method) for method in methods]
        payload["samples"] = [
            {
                "effective_at": "2024-06-28",
                "event_type": "volume-shipments-started",
                "product_scope": "example-HAMR-platform",
            },
            {"period": "example quarter", "value": 1000, "unit": "unit"},
            {"period": "example quarter", "value": 250000, "unit": "TB"},
        ]
        revised = service.revise(current.concept_id, payload, current.revision_id)
        reopened = ConceptRepository.open(state)
        persisted = reopened.get(current.concept_id)
        console = (ROOT / "src/rfi/admin/console.html").read_text(encoding="utf-8")
        checks = {
            "central_help_registry": len(FIELD_DEFINITIONS) >= 25,
            "no_raw_json_editor": "JSON array" not in console,
            "typed_method_editor": "method-card" in console and "det-inputs" in console,
            "typed_sample_editor": all(
                marker in console for marker in ("quantity", "event", "state")
            ),
            "inline_and_summary_validation": all(
                marker in console for marker in ("error-summary", "data-error")
            ),
            "revision_preview": "Review immutable revision" in console,
            "unsaved_change_protection": "beforeunload" in console,
            "immutable_revision": revised.revision_number == 2
            and len(reopened.history(current.concept_id)) == 2,
            "restart_persistence": persisted.samples[2]["unit"] == "TB",
        }
        if not all(checks.values()):
            raise RuntimeError(f"TASK-010 fixture proof failed: {checks}")
        return {
            "result": "PASS",
            "checks": checks,
            "hamr_revision": {
                "revision_number": persisted.revision_number,
                "samples": list(persisted.samples),
                "capacity_units": list(persisted.methods[capacity_index].units),
            },
            "field_help_entries": len(FIELD_DEFINITIONS),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("fixture-proof",))
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        print(json.dumps(fixture_proof(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
