from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.admin.server import OPERATOR_NAVIGATION  # noqa: E402
from rfi.cli import initialize  # noqa: E402


class RemovedExternalSourcesPresentationCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        initialize(self.state)
        self.server = create_admin_server(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def get(self, path: str) -> tuple[int, str, dict[str, str]]:
        try:
            response = urllib.request.urlopen(self.base + path, timeout=3)
        except urllib.error.HTTPError as error:
            body = error.read().decode()
            headers = dict(error.headers.items())
            error.close()
            return error.code, body, headers
        with response:
            return response.status, response.read().decode(), dict(response.headers.items())

    def test_removed_route_has_ordinary_unknown_browser_response(self) -> None:
        removed = self.get("/external-sources")
        unknown = self.get("/ordinary-unknown-route")
        self.assertEqual(removed[0], unknown[0])
        self.assertEqual(removed[1], unknown[1])
        self.assertEqual(removed[2]["Content-Type"], unknown[2]["Content-Type"])
        self.assertEqual(removed[2]["Cache-Control"], unknown[2]["Cache-Control"])
        self.assertEqual(removed[0], 404)
        self.assertNotIn("Location", removed[2])

    def test_navigation_and_all_operator_pages_have_no_management_surface(self) -> None:
        expected_paths = {
            "/concepts", "/firms", "/pull-sources", "/feeds", "/linux-mailing-lists",
            "/streams", "/artifacts",
        }
        self.assertEqual({path for path, _label in OPERATOR_NAVIGATION}, expected_paths)
        forbidden = (
            'href="/external-sources"', "Save governed source", "Validate profile",
            "Clone as new source", "Minimum request interval", "Maximum concurrency",
        )
        for path in expected_paths:
            with self.subTest(path=path):
                status, body, _headers = self.get(path)
                self.assertEqual(status, 200)
                self.assertNotIn("External Sources", body)
                for text in forbidden:
                    self.assertNotIn(text, body)

    def test_external_source_api_list_contract_remains_available(self) -> None:
        status, body, headers = self.get("/api/external-sources")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"items": []})
        self.assertTrue(headers["Content-Type"].startswith("application/json"))

    def test_streams_still_load_sources_from_existing_api(self) -> None:
        status, body, _headers = self.get("/streams")
        self.assertEqual(status, 200)
        self.assertIn("api('/api/external-sources')", body)
        self.assertIn("Repository-provided governed source", body)
        self.assertNotIn('href="/external-sources"', body)


if __name__ == "__main__":
    unittest.main()
