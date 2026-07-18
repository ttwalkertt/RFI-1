from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.concepts import ConceptRepository  # noqa: E402
from rfi.firms import FirmRepository, sample_firms  # noqa: E402
from rfi.source_profiles import (  # noqa: E402
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRepository,
    SourceProfileService,
    canonical_template_path,
    load_canonical_template,
    validate_canonical_template,
)

CONSERVATIVE_DEFAULTS = {
    "annual_report",
    "corporate_news",
    "earnings_release",
    "press_release",
    "product_page",
}
JURISDICTION_SPECIFIC_FILINGS = {
    "ownership_insider",
    "proxy_statement",
    "sec_10k",
    "sec_10q",
    "sec_20f",
    "sec_6k",
    "sec_8k",
}


def configured_draft(firm_id: str = "seagate") -> SourceProfileDraft:
    return SourceProfileDraft(
        firm_id,
        (
            SourceProfileItem(
                "engineering_blog",
                True,
                (
                    RetrievalCandidate(
                        "discovery",
                        2,
                        preferred_domains=("blog.example.com",),
                        discovery_hints=("storage engineering",),
                        operator_notes="Fallback bounded discovery.",
                    ),
                    RetrievalCandidate(
                        "feed",
                        1,
                        url="https://blog.example.com/feed.xml",
                        parser_hint="atom",
                    ),
                ),
                "Prefer posts authored by named engineers.",
            ),
            SourceProfileItem(
                "press_release",
                True,
                (
                    RetrievalCandidate(
                        "listing_page",
                        1,
                        url="https://example.com/news/",
                        preferred_domains=("example.com",),
                    ),
                ),
            ),
            SourceProfileItem(
                "sec_10k",
                True,
                (RetrievalCandidate("identifier", 1, locator="CIK:0001137789"),),
            ),
        ),
        "Firm-owned configuration, not source evidence.",
    )


class CanonicalTemplateTests(unittest.TestCase):
    def test_exact_conservative_default_policy_and_specific_filings_off(self) -> None:
        template = load_canonical_template()
        enabled = {
            item.artifact_id for item in template.artifacts if item.default_enabled
        }
        self.assertEqual(enabled, CONSERVATIVE_DEFAULTS)
        by_id = {item.artifact_id: item for item in template.artifacts}
        self.assertTrue(
            all(not by_id[item].default_enabled for item in JURISDICTION_SPECIFIC_FILINGS)
        )
        for item in (
            "earnings_transcript",
            "prepared_remarks",
            "supplemental_tables",
        ):
            self.assertFalse(by_id[item].default_enabled)

    def test_packaged_template_is_complete_unique_and_deterministic(self) -> None:
        template = load_canonical_template()
        self.assertEqual(len(template.categories), 7)
        self.assertGreaterEqual(len(template.artifacts), 40)
        ids = [item.artifact_id for item in template.artifacts]
        names = [item.short_name.casefold() for item in template.artifacts]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(
            all(
                item.short_name and len(item.short_name) <= 32
                for item in template.artifacts
            )
        )
        self.assertEqual(
            [category.order for category in template.categories],
            sorted(category.order for category in template.categories),
        )
        for category in template.categories:
            self.assertEqual(
                [item.order for item in category.items],
                sorted(item.order for item in category.items),
            )

    def test_malformed_duplicate_and_invalid_order_templates_fail_closed(self) -> None:
        with self.assertRaisesRegex(SourceProfileError, "malformed"):
            validate_canonical_template({"schema_version": 999})
        value = yaml.safe_load(canonical_template_path().read_text(encoding="utf-8"))
        value["categories"][0]["items"][1]["id"] = value["categories"][0]["items"][
            0
        ]["id"]
        with self.assertRaisesRegex(SourceProfileError, "duplicate canonical artifact"):
            validate_canonical_template(value)
        value = yaml.safe_load(canonical_template_path().read_text(encoding="utf-8"))
        value["categories"][0]["items"][1]["short_name"] = value["categories"][0][
            "items"
        ][0]["short_name"]
        with self.assertRaisesRegex(SourceProfileError, "duplicate canonical short"):
            validate_canonical_template(value)
        value = yaml.safe_load(canonical_template_path().read_text(encoding="utf-8"))
        value["categories"][0]["order"] = 999
        with self.assertRaisesRegex(SourceProfileError, "ordering is not deterministic"):
            validate_canonical_template(value)

    def test_canonical_catalog_has_no_parallel_python_or_ui_item_list(self) -> None:
        for relative in (
            "src/rfi/source_profiles/contracts.py",
            "src/rfi/source_profiles/template.py",
            "src/rfi/source_profiles/service.py",
            "src/rfi/admin/source_profiles.html",
        ):
            content = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("sec_10k", content)
            self.assertNotIn("earnings_transcript", content)


class SourceProfileRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.firms = FirmRepository.initialize(self.root / "firms")
        for draft in sample_firms():
            self.firms.create(draft)
        self.template = load_canonical_template()
        self.repository = SourceProfileRepository.initialize(
            self.root / "profiles", self.template
        )
        self.service = SourceProfileService(self.repository, self.firms, self.template)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_defaults_first_second_history_and_aggregate_independence(self) -> None:
        default = self.service.detail("seagate")
        self.assertTrue(default.is_default)
        self.assertEqual(default.revision_number, 0)
        self.assertEqual(default.source_profile_revision_id, None)
        self.assertEqual(
            [item.enabled for item in default.items],
            [item.default_enabled for item in self.template.artifacts],
        )
        self.assertEqual(
            {item.artifact_id for item in default.items if item.enabled},
            CONSERVATIVE_DEFAULTS,
        )
        firm_before = self.firms.get("seagate")
        first = self.repository.publish(configured_draft(), None)
        self.assertEqual(first.revision_number, 1)
        self.assertEqual(self.firms.get("seagate").revision_id, firm_before.revision_id)
        configured_filing = next(
            item for item in first.items if item.artifact_id == "sec_10k"
        )
        self.assertTrue(configured_filing.enabled)
        self.assertEqual(configured_filing.retrieval_candidates[0].locator, "CIK:0001137789")
        engineering = next(item for item in first.items if item.artifact_id == "engineering_blog")
        self.assertEqual(
            [candidate.priority for candidate in engineering.retrieval_candidates], [1, 2]
        )
        second_draft = replace(
            configured_draft(), operator_notes="Second independently published profile."
        )
        second = self.repository.publish(second_draft, first.source_profile_revision_id)
        self.assertEqual(second.revision_number, 2)
        self.assertEqual(second.operator_notes, "Second independently published profile.")
        self.assertEqual(second.supersedes_revision_id, first.source_profile_revision_id)
        self.assertEqual(
            [item.revision_number for item in self.repository.history("seagate")], [1, 2]
        )
        firm_second = self.firms.revise(
            "seagate",
            replace(
                FirmRepository.to_draft(firm_before), notes="Identity-only revision."
            ),
            firm_before.revision_id,
        )
        self.assertEqual(firm_second.revision_number, firm_before.revision_number + 1)
        self.assertEqual(
            self.repository.get("seagate").source_profile_revision_id,
            second.source_profile_revision_id,
        )
        reopened = SourceProfileRepository.open(self.root / "profiles", self.template)
        self.assertEqual(reopened.verify()["result"], "PASS")

    def test_failed_publication_rolls_back_and_profiles_are_isolated(self) -> None:
        first = self.repository.publish(configured_draft(), None)
        before_files = tuple((self.root / "profiles/revisions").iterdir())
        with self.assertRaisesRegex(SourceProfileError, "interrupted write"):
            self.repository.publish(
                replace(configured_draft(), operator_notes="Must roll back."),
                first.source_profile_revision_id,
                fail_before_publish=True,
            )
        self.assertEqual(
            self.repository.get("seagate").source_profile_revision_id,
            first.source_profile_revision_id,
        )
        self.assertEqual(tuple((self.root / "profiles/revisions").iterdir()), before_files)
        other = self.repository.publish(configured_draft("western-digital"), None)
        self.assertEqual(other.revision_number, 1)
        self.assertEqual(len(self.repository.history("seagate")), 1)
        self.assertEqual(len(self.repository.history("western-digital")), 1)

    def test_retrieval_shapes_unknown_items_and_invalid_candidates_are_rejected(self) -> None:
        self.repository.validate(configured_draft())
        invalid = SourceProfileDraft(
            "seagate", (SourceProfileItem("not_canonical", True),)
        )
        with self.assertRaisesRegex(SourceProfileError, "unknown canonical"):
            self.repository.validate(invalid)
        invalid = SourceProfileDraft(
            "seagate",
            (
                SourceProfileItem(
                    "sec_10k",
                    True,
                    (RetrievalCandidate("identifier", 1, locator=""),),
                ),
            ),
        )
        with self.assertRaisesRegex(SourceProfileError, "requires fields: locator"):
            self.repository.validate(invalid)
        invalid = SourceProfileDraft(
            "seagate",
            (
                SourceProfileItem(
                    "press_release",
                    True,
                    (RetrievalCandidate("listing_page", 1, url="file:///tmp/news"),),
                ),
            ),
        )
        with self.assertRaisesRegex(SourceProfileError, "invalid retrieval URL"):
            self.repository.validate(invalid)
        duplicate_priority = replace(
            configured_draft(),
            items=(
                SourceProfileItem(
                    "engineering_blog",
                    True,
                    (
                        RetrievalCandidate("feed", 1, url="https://example.com/a.xml"),
                        RetrievalCandidate("feed", 1, url="https://example.com/b.xml"),
                    ),
                ),
            ),
        )
        with self.assertRaisesRegex(SourceProfileError, "priorities must be unique"):
            self.repository.validate(duplicate_priority)


class SourceProfileAdminTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "state"
        ConceptRepository.initialize(self.root)
        firms = FirmRepository.initialize(self.root / "firm-catalog")
        for draft in sample_firms():
            firms.create(draft)
        self.server = create_admin_server(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def request(
        self, path: str, method: str = "GET", payload: dict | None = None
    ) -> tuple[int, dict | str]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                content = response.read().decode()
                value = (
                    json.loads(content)
                    if "json" in response.headers["Content-Type"]
                    else content
                )
                return response.status, value
        except urllib.error.HTTPError as error:
            value = json.loads(error.read())
            error.close()
            return error.code, value

    def test_template_driven_accordion_and_profile_revision_api(self) -> None:
        status, html = self.request("/source-profiles?firm_id=seagate")
        self.assertEqual(status, 200)
        for marker in (
            "Firm Source Profiles",
            'details class="category"',
            'details class="artifact"',
            "artifact.short_name",
            "artifact.label",
            "artifact.addressability",
            "Add prioritized retrieval candidate",
            "candidate-fields",
            "item-summary",
            "/api/source-profile-template",
            "event.stopPropagation()",
            "function captureOpenState()",
            "openState.categories.has(categoryIndex)",
            "openState.artifacts.has(artifact.artifact_id)",
            "function compareFirms(a,b)",
            "sortedFirms=[...firms.items].sort(compareFirms)",
            'id="save" class="primary" disabled',
            "function profileSnapshot()",
            "function updateDirtyState()",
            "profileSnapshot()===cleanProfile",
            "cleanProfile=profileSnapshot()",
        ):
            self.assertIn(marker, html)
        self.assertNotIn("sec_10k", html)
        template = self.request("/api/source-profile-template")[1]
        self.assertGreaterEqual(len(template["categories"]), 7)
        default = self.request("/api/firms/seagate/source-profile")[1]
        firm_before = self.request("/api/firms/seagate")[1]
        self.assertTrue(default["is_default"])
        self.assertEqual(
            {
                item["artifact_id"]
                for item in default["items"]
                if item["enabled"]
            },
            CONSERVATIVE_DEFAULTS,
        )
        payload = asdict(configured_draft())
        payload.pop("firm_id")
        invalid_payload = json.loads(json.dumps(payload))
        invalid_filing = next(
            item
            for item in invalid_payload["items"]
            if item["artifact_id"] == "sec_10k"
        )
        invalid_filing["retrieval_candidates"][0]["locator"] = ""
        status, invalid = self.request(
            "/api/firms/seagate/source-profile/validate", "POST", invalid_payload
        )
        self.assertEqual((status, invalid["valid"]), (200, False))
        self.assertIn("requires fields: locator", invalid["errors"][0])
        status, valid = self.request(
            "/api/firms/seagate/source-profile/validate", "POST", payload
        )
        self.assertEqual((status, valid["valid"]), (200, True))
        status, first = self.request(
            "/api/firms/seagate/source-profile",
            "PUT",
            {"expected_revision_id": None, "profile": payload},
        )
        self.assertEqual((status, first["revision_number"]), (200, 1))
        self.assertEqual(
            self.request("/api/firms/seagate")[1]["revision_id"],
            firm_before["revision_id"],
        )
        payload["operator_notes"] = "Second UI revision."
        status, second = self.request(
            "/api/firms/seagate/source-profile",
            "PUT",
            {
                "expected_revision_id": first["source_profile_revision_id"],
                "profile": payload,
            },
        )
        self.assertEqual((status, second["revision_number"]), (200, 2))
        reloaded = self.request("/api/firms/seagate/source-profile")[1]
        self.assertEqual(reloaded["operator_notes"], "Second UI revision.")
        history = self.request("/api/firms/seagate/source-profile/history")[1]
        self.assertEqual([item["revision_number"] for item in history["items"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
