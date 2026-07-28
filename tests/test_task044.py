from __future__ import annotations

import urllib.error
import urllib.request

from tests.test_task014 import SourceProfileAdminTests


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):  # noqa: ANN001
        return None


class ConsolidatedFirmBrowserTests(SourceProfileAdminTests):
    """Focused TASK-044 UI and unchanged-contract evidence."""

    def test_firms_is_the_single_browser_with_collapsible_profile_inspection(self) -> None:
        status, html = self.request("/firms?firm_id=seagate&artifact_id=sec_10k")
        self.assertEqual(status, 200)
        for marker in (
            "Target Firms",
            'aria-label="Search firms"',
            'aria-label="Filter by status"',
            'aria-label="Filter by sector"',
            'aria-label="Filter by industry"',
            "Identity",
            "Names",
            "Classification",
            "Discovery",
            "Acquisition Profile",
            "Revision History",
            'details class="detail-section" open',
            'details class="acquisition-category"',
            "Profile-level operator notes",
            "External JSON filename",
            "Externally managed · read-only",
            "enabled-state",
            "disabled-state",
            "artifact.addressability",
            "profileSummary(item)",
            "Source-profile revision history",
            "showProfileRevision",
        ):
            self.assertIn(marker, html)
        self.assertNotIn('href="/source-profiles"', html)
        self.assertEqual(html.count('aria-current="page"'), 1)

    def test_existing_search_filter_metadata_and_profile_contracts_are_unchanged(self) -> None:
        status, firms = self.request(
            "/api/firms?q=STX&status=active&sector=Technology&industry=Data%20storage"
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["firm_id"] for item in firms["items"]], ["seagate"])
        firm = self.request("/api/firms/seagate")[1]
        self.assertEqual(firm["canonical_name"], "Seagate")
        self.assertTrue(firm["identifiers"])
        profile = self.request("/api/firms/seagate/source-profile")[1]
        self.assertTrue(any(item["enabled"] for item in profile["items"]))
        self.assertTrue(any(not item["enabled"] for item in profile["items"]))
        self.assertTrue(any(item["retrieval_candidates"] for item in profile["items"]))
        self.assertEqual(self.request("/api/firms/seagate/source-profile/history")[0], 200)

    def test_removed_route_redirects_intentionally_and_preserves_context(self) -> None:
        opener = urllib.request.build_opener(_NoRedirect())
        with self.assertRaises(urllib.error.HTTPError) as raised:
            opener.open(
                self.base + "/source-profiles?firm_id=seagate&artifact_id=sec_10k",
                timeout=3,
            )
        self.assertEqual(raised.exception.code, 308)
        self.assertEqual(
            raised.exception.headers["Location"],
            "/firms?firm_id=seagate&artifact_id=sec_10k",
        )
        raised.exception.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
