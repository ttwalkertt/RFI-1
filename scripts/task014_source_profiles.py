#!/usr/bin/env python3
"""Deterministically prove TASK-014 canonical template and profile behavior."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.firms import FirmRepository, sample_firms  # noqa: E402
from rfi.source_profiles import (  # noqa: E402
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRepository,
    SourceProfileService,
    load_canonical_template,
)

CONSERVATIVE_DEFAULTS = {
    "annual_report",
    "corporate_news",
    "earnings_release",
    "press_release",
    "product_page",
}


def proof_draft(firm_id: str) -> SourceProfileDraft:
    """Return deterministic, semi-deterministic, and discovery configuration."""
    return SourceProfileDraft(
        firm_id,
        (
            SourceProfileItem(
                "sec_10k",
                True,
                (RetrievalCandidate("identifier", 1, locator="CIK:0001137789"),),
            ),
            SourceProfileItem(
                "press_release",
                True,
                (
                    RetrievalCandidate(
                        "listing_page", 1, url="https://example.com/news/"
                    ),
                ),
            ),
            SourceProfileItem(
                "engineering_blog",
                True,
                (
                    RetrievalCandidate(
                        "discovery",
                        2,
                        preferred_domains=("engineering.example.com",),
                        discovery_hints=("storage architecture",),
                    ),
                    RetrievalCandidate(
                        "feed", 1, url="https://engineering.example.com/feed.xml"
                    ),
                ),
                "Prefer attributable technical authors.",
            ),
        ),
        "Acquisition configuration only.",
    )


def fixture_proof() -> dict[str, Any]:
    """Exercise template, revision, rollback, isolation, rendering, and rejection evidence."""
    template = load_canonical_template()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        firms = FirmRepository.initialize(root / "firms")
        for draft in sample_firms():
            firms.create(draft)
        profiles = SourceProfileRepository.initialize(root / "profiles", template)
        service = SourceProfileService(profiles, firms, template)
        default = service.detail("seagate")
        firm_revision = firms.get("seagate").revision_id
        first = profiles.publish(proof_draft("seagate"), None)
        second = profiles.publish(
            replace(proof_draft("seagate"), operator_notes="Second revision."),
            first.source_profile_revision_id,
        )
        prior_history = tuple(profiles.history("seagate"))
        rollback_error = ""
        try:
            profiles.publish(
                replace(proof_draft("seagate"), operator_notes="Interrupted revision."),
                second.source_profile_revision_id,
                fail_before_publish=True,
            )
        except SourceProfileError as error:
            rollback_error = str(error)
        other = profiles.publish(proof_draft("western-digital"), None)
        unknown_error = ""
        try:
            profiles.validate(
                SourceProfileDraft(
                    "seagate", (SourceProfileItem("unknown_artifact", True),)
                )
            )
        except SourceProfileError as error:
            unknown_error = str(error)
        engineering = next(
            item for item in second.items if item.artifact_id == "engineering_blog"
        )
        default_enabled = {
            item.artifact_id for item in template.artifacts if item.default_enabled
        }
        unsaved_enabled = {
            item.artifact_id for item in default.items if item.enabled
        }
        ui = (ROOT / "src/rfi/admin/source_profiles.html").read_text(encoding="utf-8")
        checks = {
            "template_loads": len(template.artifacts) == 48,
            "canonical_identifiers_unique": len(
                {item.artifact_id for item in template.artifacts}
            )
            == len(template.artifacts),
            "short_names_unique": len(
                {item.short_name.casefold() for item in template.artifacts}
            )
            == len(template.artifacts),
            "defaults_without_revision": default.is_default
            and default.revision_number == 0,
            "exact_conservative_defaults": default_enabled == CONSERVATIVE_DEFAULTS,
            "unsaved_profile_matches_defaults": unsaved_enabled == default_enabled,
            "first_and_second_revision": first.revision_number == 1
            and second.revision_number == 2,
            "firm_revision_unaffected": firms.get("seagate").revision_id
            == firm_revision,
            "history_readable": len(profiles.history("seagate")) == 2,
            "rollback_preserved_current": profiles.get("seagate")
            == second
            and tuple(profiles.history("seagate")) == prior_history,
            "rollback_was_injected": "interrupted write" in rollback_error,
            "cross_firm_isolation": other.revision_number == 1
            and len(profiles.history("western-digital")) == 1,
            "candidate_priority_order": [
                candidate.priority for candidate in engineering.retrieval_candidates
            ]
            == [1, 2],
            "deterministic_semi_discovery_modes": {
                candidate.mode
                for item in second.items
                for candidate in item.retrieval_candidates
            }
            >= {"identifier", "listing_page", "discovery"},
            "unknown_item_rejected": "unknown canonical" in unknown_error,
            "template_driven_ui": all(
                marker in ui
                for marker in (
                    "template.categories.map",
                    "artifact.short_name",
                    "artifact.addressability",
                    "mode.supported_fields.map",
                )
            ),
            "no_hardcoded_ui_catalog": "sec_10k" not in ui,
            "repository_integrity": profiles.verify()["result"] == "PASS",
        }
        if not all(checks.values()):
            raise RuntimeError(f"TASK-014 fixture proof failed: {checks}")
        return {
            "result": "PASS",
            "canonical_categories": len(template.categories),
            "canonical_artifacts": len(template.artifacts),
            "retrieval_modes": [item.mode for item in template.retrieval_modes],
            "default_enabled_artifacts": sorted(default_enabled),
            "checks": checks,
        }


def main() -> int:
    """Run one deterministic proof command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("fixture-proof",))
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        print(json.dumps(fixture_proof(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
