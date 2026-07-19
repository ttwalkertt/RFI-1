from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.firms import FirmRepository, sample_firms
from rfi.source_profiles import (
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)


class PullConfigurationNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        ConceptRepository.initialize(self.state)
        firms = FirmRepository.initialize(self.state / "firm-catalog")
        firms.create(sample_firms()[0])
        template = load_canonical_template()
        profiles = SourceProfileRepository.initialize(
            self.state / "source-profiles", template
        )
        profiles.publish(
            SourceProfileDraft(
                "seagate", (SourceProfileItem("sec_10q", True, ()),)
            ),
            None,
        )
        self.server = create_admin_server(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def get_json(self, path: str) -> dict[str, object]:
        with urllib.request.urlopen(self.base + path, timeout=3) as response:
            self.assertEqual(response.status, 200)
            return json.load(response)

    def test_pull_results_api_supplies_exact_navigation_identity(self) -> None:
        request = urllib.request.Request(
            self.base + "/api/pulls",
            data=json.dumps({"firm_ids": ["seagate"]}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 202)
            initiated = json.load(response)
        status: dict[str, object] = {"status": "running"}
        for _ in range(100):
            status = self.get_json(str(initiated["status_url"]))
            if status["status"] != "running":
                break
            time.sleep(0.01)
        self.assertEqual(status["status"], "failed")
        results = self.get_json(str(initiated["results_url"]))
        firm = results["firms"][0]  # type: ignore[index]
        artifact = next(
            item for item in firm["artifacts"] if item["artifact_id"] == "sec_10q"
        )
        self.assertEqual(firm["firm_id"], "seagate")
        self.assertEqual(artifact["artifact_id"], "sec_10q")
        self.assertEqual(artifact["outcome"], "configuration_problem")
        self.assertGreaterEqual(
            results["summary"]["configuration_problem"], 1  # type: ignore[index]
        )

    def test_production_browser_renderer_links_only_actionable_statuses(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", "tests/task024_browser_harness.js", self.base],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["result"], "PASS")
        self.assertEqual(evidence["actionableLinks"], 1)
        self.assertTrue(evidence["nonActionableStatusesUnchanged"])
        self.assertFalse(evidence["popupOrModal"])

    def test_source_profile_deep_link_contract_is_read_only_and_reveals_target(self) -> None:
        with urllib.request.urlopen(self.base + "/source-profiles", timeout=3) as response:
            html = response.read().decode()
        for marker in (
            "requestedParams.get('firm_id')",
            "requestedParams.get('artifact_id')",
            "validRequest?requestedFirm:remembered",
            "category.open=true",
            "target.open=true",
            "scrollIntoView({block:'center'})",
            "focus({preventScroll:true})",
            "classList.add('targeted')",
        ):
            self.assertIn(marker, html)
        for forbidden in (
            "window.open(",
            "history.replaceState",
            "history.pushState",
            'role="dialog"',
        ):
            self.assertNotIn(forbidden, html)


if __name__ == "__main__":
    unittest.main()
