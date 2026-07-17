from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.admin.field_definitions import FIELD_DEFINITIONS  # noqa: E402
from rfi.concepts import ConceptRepository, sample_concepts  # noqa: E402
from rfi.firms import FirmRepository  # noqa: E402


class AdminEditorUsabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "catalog"
        repository = ConceptRepository.initialize(self.state)
        for draft in sample_concepts():
            repository.create(draft)
        FirmRepository.initialize(self.state / "firm-catalog")
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

    def request(
        self,
        path: str,
        method: str = "GET",
        payload: dict | None = None,
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

    def test_central_field_help_registry_is_served_and_behavioral(self) -> None:
        status, payload = self.request("/api/field-definitions")
        self.assertEqual(status, 200)
        self.assertEqual(payload["fields"], FIELD_DEFINITIONS)
        self.assertIn("not the revision creation timestamp", payload["fields"]["valid_from"])
        self.assertIn("not authoritative", payload["fields"]["samples"])
        for required in (
            "status",
            "result_shape",
            "scope",
            "effective_at",
            "period_start",
            "period_end",
            "units",
            "dimensions",
            "required_inputs",
            "comparison_semantics",
            "confidence_rules",
            "tolerance",
            "warnings",
        ):
            self.assertIn(required, payload["fields"])

    def test_shell_has_typed_workflow_accessibility_and_no_json_editor(self) -> None:
        status, shell = self.request("/concepts")
        self.assertEqual(status, 200)
        for proof in (
            "data-help",
            "aria-describedby",
            'popover="manual"',
            "showPopover",
            "beforeunload",
            "Preview new revision",
            "Save new revision",
            "method-card",
            "sample-family",
            "det-inputs",
            "error-summary",
            "move-up",
        ):
            self.assertIn(proof, shell)
        self.assertNotIn("Methods and derivations (JSON array)", shell)
        self.assertNotIn("Samples (JSON array)", shell)
        self.assertNotIn("name=\"methods\"", shell)

    def test_hamr_typed_revision_preserves_history_and_persists(self) -> None:
        current = self.request("/api/concepts/hamr-shipments")[1]
        payload = {
            key: value
            for key, value in current.items()
            if key
            not in {
                "revision_id",
                "revision_number",
                "created_at",
                "updated_at",
                "supersedes_revision_id",
            }
        }
        capacity = next(
            item
            for item in payload["methods"]
            if item["method_id"] == "capacity-shipped"
        )
        capacity["units"] = ["exabyte", "TB"]
        payload["samples"] = [
            {
                "effective_at": "2024-06-28",
                "event_type": "volume-shipments-started",
                "product_scope": "example-HAMR-platform",
            },
            {"period": "example quarter", "value": 1000, "unit": "unit"},
            {"period": "example quarter", "value": 250000, "unit": "TB"},
        ]
        status, revised = self.request(
            "/api/concepts/hamr-shipments",
            "PUT",
            {"expected_revision_id": current["revision_id"], "concept": payload},
        )
        self.assertEqual((status, revised["revision_number"]), (200, 2))
        self.assertEqual(revised["samples"][2]["unit"], "TB")
        history = self.request("/api/concepts/hamr-shipments/history")[1]["items"]
        self.assertEqual([item["revision_number"] for item in history], [1, 2])
        reopened = ConceptRepository.open(self.state).get("hamr-shipments")
        self.assertEqual(asdict(reopened)["samples"][2]["value"], 250000)

    def test_optimistic_conflict_has_focused_error_code(self) -> None:
        current = self.request("/api/concepts/revenue")[1]
        payload = {
            key: value
            for key, value in current.items()
            if key
            not in {
                "revision_id",
                "revision_number",
                "created_at",
                "updated_at",
                "supersedes_revision_id",
            }
        }
        first = self.request(
            "/api/concepts/revenue",
            "PUT",
            {"expected_revision_id": current["revision_id"], "concept": payload},
        )
        self.assertEqual(first[0], 200)
        status, conflict = self.request(
            "/api/concepts/revenue",
            "PUT",
            {"expected_revision_id": current["revision_id"], "concept": payload},
        )
        self.assertEqual(status, 400)
        self.assertEqual(conflict["error_code"], "revision_conflict")


if __name__ == "__main__":
    unittest.main()
