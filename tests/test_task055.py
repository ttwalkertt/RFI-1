"""TASK-055 external firm-configuration divergence acceptance tests."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from rfi.admin import create_admin_server
from rfi.cli import initialize
from rfi.firm_configuration import (
    firm_configuration_fingerprint,
    inspect_firm_configuration_status,
    prepare_firm_configuration,
)
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/microsoft.firm-config.example.json"


class Task055Case(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.directory = self.state / "firm-config"
        self.directory.mkdir(parents=True)
        self.path = self.directory / "microsoft.firm-config.json"
        self.path.write_bytes(EXAMPLE.read_bytes())
        initialize(self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def durable_snapshot(self) -> tuple[tuple[str, tuple[tuple[object, ...], ...]], ...]:
        database = RepositoryDatabase.open(self.state)
        with database.connect(read_only=True) as connection:
            tables = tuple(str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ))
            return tuple((table, tuple(tuple(row) for row in connection.execute(
                f'SELECT * FROM "{table}"'
            ))) for table in tables)

    def test_unchanged_is_current_and_timestamp_only_is_ignored(self) -> None:
        current = inspect_firm_configuration_status(self.state)
        self.assertEqual(current.status, "current")
        self.assertEqual(current.imported_fingerprint, current.external_fingerprint)
        stat = self.path.stat()
        os.utime(self.path, (stat.st_atime + 100, stat.st_mtime + 100))
        timestamp_only = inspect_firm_configuration_status(self.state)
        self.assertEqual(timestamp_only.status, "current")
        self.assertEqual(timestamp_only.external_fingerprint, current.external_fingerprint)

    def test_add_remove_rename_and_byte_changes_are_detected(self) -> None:
        imported = firm_configuration_fingerprint(self.state)
        added = self.directory / "extra.firm-config.json"
        added.write_bytes(b"{}")
        self.assertNotEqual(firm_configuration_fingerprint(self.state), imported)
        added.unlink()
        self.assertEqual(firm_configuration_fingerprint(self.state), imported)
        renamed = self.path.with_name("renamed.firm-config.json")
        self.path.rename(renamed)
        self.assertNotEqual(firm_configuration_fingerprint(self.state), imported)
        renamed.rename(self.path)
        self.path.write_bytes(self.path.read_bytes() + b" ")
        self.assertEqual(inspect_firm_configuration_status(self.state).status,
                         "changes_available")
        self.path.unlink()
        self.assertEqual(inspect_firm_configuration_status(self.state).status,
                         "changes_available")

    def test_detection_does_not_parse_and_inspection_failure_is_explicit(self) -> None:
        self.path.write_bytes(b"{ definitely not JSON")
        self.assertEqual(inspect_firm_configuration_status(self.state).status,
                         "changes_available")
        with patch("pathlib.Path.read_bytes", side_effect=OSError("permission denied")):
            failure = inspect_firm_configuration_status(self.state)
        self.assertEqual(failure.status, "inspection_failure")
        self.assertIsNone(failure.external_fingerprint)
        self.assertIn("permission denied", failure.diagnostic or "")

    def test_startup_detection_is_write_free_and_changes_do_not_block_startup(self) -> None:
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        before = self.durable_snapshot()
        server = create_admin_server(self.state, port=0)
        try:
            self.assertEqual(server.firm_configuration_status.status, "changes_available")
            self.assertEqual(self.durable_snapshot(), before)
        finally:
            server.server_close()

    def test_reload_records_fingerprint_atomically_and_clears_status(self) -> None:
        value = json.loads(self.path.read_text(encoding="utf-8"))
        value["comments"] = "TASK-055 changed bytes"
        self.path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        before = inspect_firm_configuration_status(self.state)
        self.assertEqual(before.status, "changes_available")
        imported_before = before.imported_fingerprint
        with self.assertRaisesRegex(RuntimeError, "injected materialization failure"):
            prepare_firm_configuration(self.state, fail_after_firms=1)
        failed = inspect_firm_configuration_status(self.state)
        self.assertEqual(failed.imported_fingerprint, imported_before)
        self.assertEqual(failed.status, "changes_available")
        prepare_firm_configuration(self.state)
        current = inspect_firm_configuration_status(self.state)
        self.assertEqual(current.status, "current")
        self.assertEqual(current.imported_fingerprint, current.external_fingerprint)


class Task055AdminCase(Task055Case):
    def setUp(self) -> None:
        super().setUp()
        self.server = create_admin_server(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        super().tearDown()

    def request(self, path: str) -> dict[str, object] | str:
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            content = response.read().decode()
            if "json" in response.headers["Content-Type"]:
                return json.loads(content)
            return content

    def test_target_firms_status_endpoint_refreshes_external_state(self) -> None:
        self.assertEqual(self.request("/api/firm-configurations/status")["status"], "current")
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        refreshed = self.request("/api/firm-configurations/status")
        self.assertEqual(refreshed["status"], "changes_available")
        html = self.request("/firms")
        assert isinstance(html, str)
        self.assertIn("refreshConfigurationStatus()", html)
        self.assertIn("External changes available", html)
        self.assertIn("Use Reload Firm Profiles", html)

    def test_status_indicators_have_semantic_colors_and_text(self) -> None:
        firms = self.request("/firms")
        pulls = self.request("/pull-sources")
        assert isinstance(firms, str) and isinstance(pulls, str)
        for marker in ("configuration-current", "configuration-changes_available",
                       "configuration-inspection_failure", "role=\"status\""):
            self.assertIn(marker, firms)
        for marker in ("outcome-success", "outcome-duplicate", "outcome-indeterminate",
                       "outcome-configuration_problem", "data-outcome"):
            self.assertIn(marker, pulls)

