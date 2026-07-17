from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.firms import (  # noqa: E402
    FirmDraft,
    FirmError,
    FirmIdentifier,
    FirmReference,
    FirmRelationship,
    FirmRepository,
    FirmService,
    FirmStatus,
    SourceDiscoveryHint,
    sample_firms,
)


class FirmCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "firm-catalog"
        self.repository = FirmRepository.initialize(self.state)
        for draft in sample_firms():
            self.repository.create(draft)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def generic(self, firm_id: str = "example-storage") -> FirmDraft:
        identifier = "EXM" if firm_id == "example-storage" else firm_id.upper()
        domain = "example-storage.com" if firm_id == "example-storage" else f"{firm_id}.com"
        return FirmDraft(
            firm_id=firm_id,
            canonical_name="Example Storage",
            legal_name="Example Storage Corporation",
            aliases=("ExampleCo",),
            identifiers=(FirmIdentifier("ticker", identifier, "NASDAQ"),),
            domains=(domain,),
            headquarters="Example City",
            jurisdiction="Delaware, United States",
            sector="Technology",
            industry="Data storage",
            technology_focus=("hard disk drives",),
            relationships=(FirmRelationship("competitor", "seagate"),),
            source_hints=(
                SourceDiscoveryHint("investor-relations", "ir.example-storage.com"),
            ),
            notes="Illustrative operator context, not extracted knowledge.",
            status=FirmStatus.ACTIVE,
            valid_from="2024-01-01",
        )

    def test_seeded_hdd_firms_are_searchable_with_recognition_metadata(self) -> None:
        self.assertEqual(
            {item.firm_id for item in self.repository.lookup()},
            {"seagate", "toshiba", "western-digital"},
        )
        self.assertEqual(self.repository.lookup("STX")[0].firm_id, "seagate")
        self.assertEqual(self.repository.lookup("westerndigital.com")[0].firm_id, "western-digital")
        self.assertEqual(self.repository.lookup("6502")[0].firm_id, "toshiba")
        self.assertEqual(len(self.repository.lookup(sector="tech", industry="storage")), 3)

    def test_create_revise_retire_history_restart_and_integrity(self) -> None:
        first = self.repository.create(self.generic())
        second = self.repository.revise(
            first.firm_id,
            replace(self.generic(), aliases=("ExampleCo", "EXM Storage")),
            first.revision_id,
        )
        retired = self.repository.retire(second.firm_id, second.revision_id)
        self.assertEqual([item.revision_number for item in self.repository.history(first.firm_id)],
                         [1, 2, 3])
        self.assertEqual(self.repository.get(first.firm_id, first.revision_id).aliases,
                         ("ExampleCo",))
        reopened = FirmRepository.open(self.state)
        self.assertEqual(reopened.get(first.firm_id).status, FirmStatus.RETIRED)
        self.assertEqual(reopened.verify()["result"], "PASS")

    def test_conflicting_identifiers_domains_and_invalid_values_append_nothing(self) -> None:
        before = len(self.repository.lookup())
        with self.assertRaisesRegex(FirmError, "conflicting firm identifier"):
            self.repository.create(
                replace(
                    self.generic("ticker-conflict"),
                    identifiers=(FirmIdentifier("ticker", "STX", "NASDAQ"),),
                )
            )
        with self.assertRaisesRegex(FirmError, "conflicting firm domain"):
            self.repository.create(
                replace(self.generic("domain-conflict"), domains=("seagate.com",))
            )
        with self.assertRaisesRegex(FirmError, "invalid domain"):
            self.repository.create(
                replace(self.generic("bad-domain"), domains=("https://example.com/path",))
            )
        with self.assertRaisesRegex(FirmError, "cannot reference itself"):
            self.repository.create(
                replace(
                    self.generic("self-related"),
                    relationships=(FirmRelationship("parent", "self-related"),),
                )
            )
        self.assertEqual(len(self.repository.lookup()), before)

    def test_optimistic_conflict_interruption_and_corruption_fail_closed(self) -> None:
        first = self.repository.create(self.generic())
        second = self.repository.revise(
            first.firm_id,
            replace(self.generic(), notes="second"),
            first.revision_id,
        )
        with self.assertRaisesRegex(FirmError, "current firm revision has changed"):
            self.repository.revise(first.firm_id, self.generic(), first.revision_id)
        with self.assertRaisesRegex(FirmError, "interrupted write"):
            self.repository.create(self.generic("interrupted"), fail_before_publish=True)
        self.assertEqual(self.repository.get(first.firm_id).revision_id, second.revision_id)
        corrupt = self.root / "corrupt"
        shutil.copytree(self.state, corrupt)
        (corrupt / "catalog.json").write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(FirmError, "cannot read firm catalog"):
            FirmRepository.open(corrupt)

    def test_public_service_and_reference_do_not_couple_future_persistence(self) -> None:
        service = FirmService(self.repository)
        seagate = service.detail("seagate")
        reference = FirmReference(seagate.firm_id, seagate.revision_id)
        self.assertEqual(asdict(reference)["firm_id"], "seagate")
        payload = asdict(self.generic("service-created"))
        self.assertTrue(service.validate(payload)["valid"])
        created = service.create(payload)
        self.assertEqual(service.detail(created.firm_id).revision_id, created.revision_id)
        contracts = (SRC / "rfi/firms/contracts.py").read_text(encoding="utf-8")
        for forbidden in ("rfi.acquisition", "rfi.knowledge", "rfi.source_objects", "Path"):
            self.assertNotIn(forbidden, contracts)


class FirmAdminConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.server = create_admin_server(self.root / "concept-catalog", port=0)
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

    def test_browser_reuses_typed_revision_help_and_dirty_state_patterns(self) -> None:
        status, shell = self.request("/firms")
        self.assertEqual(status, 200)
        for marker in (
            "Target Firms",
            "data-help",
            "beforeunload",
            "Preview new revision",
            "Save new revision",
            "repeat-row",
            "identifiers",
            "relationships",
            "source_hints",
            "error-summary",
        ):
            self.assertIn(marker, shell)
        self.assertNotIn("JSON array", shell)
        self.assertNotIn("name=\"identifiers\"", shell)

    def test_seeded_list_detail_search_filters_and_history_api(self) -> None:
        status, result = self.request("/api/firms?q=STX&status=active&sector=Technology")
        self.assertEqual(status, 200)
        self.assertEqual([item["firm_id"] for item in result["items"]], ["seagate"])
        detail = self.request("/api/firms/western-digital")[1]
        self.assertEqual(detail["identifiers"][0]["value"], "WDC")
        history = self.request("/api/firms/toshiba/history")[1]
        self.assertEqual(len(history["items"]), 1)

    def test_create_validate_revise_conflict_and_restart_through_public_api(self) -> None:
        payload = asdict(FirmCatalogTests.generic(self, "browser-firm"))
        status, validation = self.request("/api/firms/validate", "POST", payload)
        self.assertEqual((status, validation["valid"]), (200, True))
        status, created = self.request("/api/firms", "POST", payload)
        self.assertEqual((status, created["revision_number"]), (201, 1))
        payload["aliases"] = [*payload["aliases"], "Browser Storage"]
        status, revised = self.request(
            "/api/firms/browser-firm",
            "PUT",
            {"expected_revision_id": created["revision_id"], "firm": payload},
        )
        self.assertEqual((status, revised["revision_number"]), (200, 2))
        conflict = dict(payload)
        conflict["firm_id"] = "conflicting-browser-firm"
        conflict["identifiers"] = [
            {"kind": "ticker", "value": "CFB", "market": "NASDAQ"}
        ]
        conflict["domains"] = ["seagate.com"]
        status, invalid = self.request("/api/firms/validate", "POST", conflict)
        self.assertEqual((status, invalid["valid"]), (200, False))
        self.assertIn("conflicting firm domain", invalid["errors"][0])
        reopened = FirmRepository.open(self.root / "concept-catalog" / "firm-catalog")
        self.assertEqual(reopened.get("browser-firm").aliases[-1], "Browser Storage")


if __name__ == "__main__":
    unittest.main()
