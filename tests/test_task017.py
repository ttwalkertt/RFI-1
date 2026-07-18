from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.firms import FirmRepository, sample_firms
from rfi.source_profiles import (
    SourceProfileDraft,
    SourceProfileRepository,
    load_canonical_template,
)


class AdminPreferenceProductionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        ConceptRepository.initialize(self.state)
        firms = FirmRepository.initialize(self.state / "firm-catalog")
        for draft in sample_firms()[:2]:
            firms.create(draft)
        template = load_canonical_template()
        profiles = SourceProfileRepository.initialize(self.state / "source-profiles", template)
        profiles.publish(SourceProfileDraft("seagate", ()), None)
        profiles.publish(SourceProfileDraft("western-digital", ()), None)
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

    def test_shared_module_is_packaged_and_served(self) -> None:
        with urllib.request.urlopen(
            self.base + "/admin/admin_preferences.js", timeout=3
        ) as response:
            source = response.read().decode()
            self.assertEqual(
                response.headers["Content-Type"], "text/javascript; charset=utf-8"
            )
        self.assertIn("rfi.admin.preferences.v1", source)
        for page in ("/source-profiles", "/pull-sources"):
            with urllib.request.urlopen(self.base + page, timeout=3) as response:
                html = response.read().decode()
            self.assertIn('<script src="/admin/admin_preferences.js"></script>', html)
            self.assertNotIn("localStorage", html)

    def test_production_page_scripts_restore_without_authority_writes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        profiles_before = tuple(
            path.read_bytes()
            for path in sorted((self.state / "source-profiles").rglob("*"))
            if path.is_file()
        )
        result = subprocess.run(
            [
                "node",
                "tests/task017_browser_harness.js",
                self.base,
                str(root / "src/rfi/admin/admin_preferences.js"),
            ],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["result"], "PASS")
        self.assertEqual(evidence["profilePutCount"], 0)
        self.assertEqual(evidence["implicitPullPostCount"], 0)
        profiles_after = tuple(
            path.read_bytes()
            for path in sorted((self.state / "source-profiles").rglob("*"))
            if path.is_file()
        )
        self.assertEqual(profiles_after, profiles_before)


class EmptyFirmProductionTests(unittest.TestCase):
    def test_both_production_pages_remain_usable_with_empty_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state"
            ConceptRepository.initialize(state)
            FirmRepository.initialize(state / "firm-catalog")
            server = create_admin_server(state, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            root = Path(__file__).resolve().parents[1]
            try:
                result = subprocess.run(
                    [
                        "node",
                        "tests/task017_browser_harness.js",
                        f"http://{host}:{port}",
                        str(root / "src/rfi/admin/admin_preferences.js"),
                        "--empty",
                    ],
                    cwd=root,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertTrue(json.loads(result.stdout)["emptyFirmLists"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
