from __future__ import annotations

import json
import shutil
import socket
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
from rfi.concepts import (  # noqa: E402
    CalculationError,
    ConceptDraft,
    ConceptError,
    ConceptRepository,
    ConceptService,
    ConceptStatus,
    MethodKind,
    ObservationMethod,
    ObservationOrigin,
    ObservationService,
    sample_concepts,
)
from rfi.firms import FirmRepository  # noqa: E402


class ConceptCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "catalog"
        self.repository = ConceptRepository.initialize(self.state)
        for draft in sample_concepts():
            self.repository.create(draft)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def generic(self, concept_id: str = "generic-proof") -> ConceptDraft:
        return ConceptDraft(
            concept_id=concept_id,
            display_name="Generic Proof",
            definition="A deliberately generic multi-shaped proof concept.",
            comments="Initial comment",
            aliases=("proof signal",),
            hints=("generic hint",),
            status=ConceptStatus.DRAFT,
            tags=("generic", "proof"),
            classifications={"family": "generic"},
            valid_from="2024-01-01",
            sample_date="2024-02-02",
            methods=(
                ObservationMethod(
                    method_id="extracted-proof",
                    kind=MethodKind.EXTRACTED,
                    name="Extracted proof",
                    result_shape="structured",
                    configuration={"shape_version": 1},
                ),
            ),
            samples=({"example": "value"},),
        )

    def test_lifecycle_revision_validity_retirement_and_restart(self) -> None:
        first = self.repository.create(self.generic())
        revised = replace(
            self.generic(),
            comments="Revised comment",
            valid_through="2026-12-31",
            status=ConceptStatus.ACTIVE,
        )
        second = self.repository.revise(first.concept_id, revised, first.revision_id)
        retired = self.repository.retire(first.concept_id, second.revision_id)
        self.assertEqual(
            [item.revision_number for item in self.repository.history(first.concept_id)],
            [1, 2, 3],
        )
        self.assertEqual(retired.status, ConceptStatus.RETIRED)
        self.assertEqual(self.repository.get(first.concept_id, first.revision_id).comments,
                         "Initial comment")
        reopened = ConceptRepository.open(self.state)
        self.assertEqual(reopened.get(first.concept_id).revision_id, retired.revision_id)
        self.assertEqual(reopened.verify()["result"], "PASS")

    def test_lookup_by_id_name_alias_keyword_tag_status_and_validity(self) -> None:
        self.assertEqual(self.repository.lookup("gross-margin")[0].concept_id, "gross-margin")
        self.assertEqual(self.repository.lookup("Gross Margin")[0].concept_id, "gross-margin")
        self.assertEqual(self.repository.lookup("GM")[0].concept_id, "gross-margin")
        self.assertEqual(
            self.repository.lookup("customer acceptance")[0].concept_id,
            "hamr-qualification",
        )
        self.assertEqual(
            self.repository.lookup(tag="multi-shaped")[0].concept_id,
            "hamr-shipments",
        )
        self.assertTrue(self.repository.lookup(status=ConceptStatus.ACTIVE))
        self.assertTrue(self.repository.lookup(valid_on="2024-06-28"))
        self.assertFalse(self.repository.lookup(valid_on="2019-12-31"))

    def test_validation_failures_append_nothing(self) -> None:
        count = len(self.repository.lookup())
        with self.assertRaisesRegex(ConceptError, "invalid concept identifier"):
            self.repository.create(self.generic("../unsafe"))
        with self.assertRaisesRegex(ConceptError, "duplicate concept"):
            self.repository.create(replace(self.generic(), concept_id="revenue"))
        with self.assertRaisesRegex(ConceptError, "validity interval"):
            self.repository.create(
                replace(self.generic("bad-date"), valid_through="2023-12-31")
            )
        with self.assertRaisesRegex(ConceptError, "unknown method kind"):
            self.repository.create(
                replace(
                    self.generic("bad-kind"),
                    methods=(
                        ObservationMethod(
                            method_id="bad-kind",
                            kind="unknown",
                            name="Unknown",
                            result_shape="structured",
                        ),
                    ),
                )
            )
        self.assertEqual(len(self.repository.lookup()), count)

    def test_stale_revision_historical_mutation_and_corruption_fail_closed(self) -> None:
        first = self.repository.create(self.generic())
        second = self.repository.revise(
            first.concept_id,
            replace(self.generic(), comments="second"),
            first.revision_id,
        )
        with self.assertRaisesRegex(ConceptError, "current revision has changed"):
            self.repository.revise(first.concept_id, self.generic(), first.revision_id)
        with self.assertRaisesRegex(ConceptError, "historical mutation"):
            self.repository._write_revision(replace(first, comments="rewritten"))
        self.assertEqual(self.repository.get(first.concept_id).revision_id, second.revision_id)
        corrupt = self.root / "corrupt"
        shutil.copytree(self.state, corrupt)
        (corrupt / "catalog.json").write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(ConceptError, "cannot read catalog"):
            ConceptRepository.open(corrupt)

    def test_interrupted_write_does_not_publish(self) -> None:
        with self.assertRaisesRegex(ConceptError, "interrupted write"):
            self.repository.create(self.generic(), fail_before_publish=True)
        with self.assertRaisesRegex(ConceptError, "unknown concept"):
            self.repository.get("generic-proof")
        self.assertEqual(self.repository.verify()["result"], "PASS")

    def test_registered_extension_kind_and_shape_remain_opaque(self) -> None:
        repository = ConceptRepository.initialize(
            self.root / "extensions",
            extension_method_kinds=("extension:example/custom",),
        )
        method = ObservationMethod(
            method_id="example/custom",
            kind="extension:example/custom",
            name="Example future method",
            result_shape="extension:example/matrix",
            configuration={"future_contract": {"axes": ["a", "b"]}},
        )
        revision = repository.create(replace(self.generic(), methods=(method,)))
        self.assertEqual(
            revision.methods[0].configuration["future_contract"]["axes"],
            ["a", "b"],
        )

    def financial_inputs(self):
        service = ObservationService()
        common = {
            "unit": "USD",
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "scope": "consolidated",
            "dimensions": {"entity": "example"},
        }
        revenue = service.observe(
            self.repository.get("revenue"), "reported-revenue", 1000, **common
        )
        profit = service.observe(
            self.repository.get("gross-profit"), "reported-gross-profit", 400, **common
        )
        cost = service.observe(
            self.repository.get("cost-of-revenue"),
            "reported-cost-of-revenue",
            600,
            **common,
        )
        return service, revenue, profit, cost

    def test_extracted_and_two_calculated_margins_coexist_with_lineage(self) -> None:
        service, revenue, profit, cost = self.financial_inputs()
        gross_margin = self.repository.get("gross-margin")
        reported = service.observe(
            gross_margin,
            "reported-gross-margin",
            40.1,
            unit="percent",
            period_start=revenue.period_start,
            period_end=revenue.period_end,
            scope=revenue.scope,
            dimensions=revenue.dimensions,
        )
        first = service.calculate(
            gross_margin,
            "gross-profit-over-revenue",
            {"gross_profit": profit, "revenue": revenue},
        )
        second = service.calculate(
            gross_margin,
            "revenue-less-cost-over-revenue",
            {"revenue": revenue, "cost_of_revenue": cost},
        )
        self.assertEqual((reported.origin, first.origin, second.origin), (
            ObservationOrigin.EXTRACTED,
            ObservationOrigin.CALCULATED,
            ObservationOrigin.CALCULATED,
        ))
        self.assertEqual((first.value, second.value), (40.0, 40.0))
        self.assertEqual({item.role for item in first.lineage}, {"gross_profit", "revenue"})
        comparison = service.reconcile(reported, first, 0.2)
        self.assertTrue(comparison.within_tolerance)
        self.assertNotEqual(reported.observation_id, first.observation_id)

    def test_calculation_preconditions_are_visible(self) -> None:
        service, revenue, profit, _ = self.financial_inputs()
        margin = self.repository.get("gross-margin")
        with self.assertRaisesRegex(CalculationError, "missing required inputs"):
            service.calculate(margin, "gross-profit-over-revenue", {})
        with self.assertRaisesRegex(CalculationError, "incompatible input unit"):
            service.calculate(
                margin,
                "gross-profit-over-revenue",
                {"gross_profit": profit, "revenue": replace(revenue, unit="EUR")},
            )
        with self.assertRaisesRegex(CalculationError, "incompatible input periods"):
            service.calculate(
                margin,
                "gross-profit-over-revenue",
                {
                    "gross_profit": profit,
                    "revenue": replace(revenue, period_start="2023-01-01"),
                },
            )
        with self.assertRaisesRegex(CalculationError, "calculation failure"):
            service.calculate(
                margin,
                "gross-profit-over-revenue",
                {"gross_profit": profit, "revenue": replace(revenue, value=0)},
            )

    def test_stateful_and_event_multi_shape_observations(self) -> None:
        service = ObservationService()
        state = service.observe(
            self.repository.get("hamr-qualification"),
            "qualification-state",
            {"state": "qualified", "customer_scope": "customer-a"},
            scope="customer-a/product-a",
        )
        event = service.observe(
            self.repository.get("hamr-shipments"),
            "shipment-milestone",
            {"event_type": "volume-shipments-started"},
            effective_at="2024-06-28",
        )
        quantity = service.observe(
            self.repository.get("hamr-shipments"),
            "units-shipped",
            1000,
            unit="unit",
        )
        self.assertEqual(state.result_shape, "state")
        self.assertEqual((event.result_shape, quantity.result_shape), ("event", "quantity"))


class AdminConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        repository = ConceptRepository.initialize(self.root / "catalog")
        for draft in sample_concepts():
            repository.create(draft)
        FirmRepository.initialize(self.root / "catalog/firm-catalog")
        self.server = create_admin_server(self.root / "catalog", port=0)
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
    ) -> tuple[int, dict | str, dict[str, str]]:
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
                result = (
                    json.loads(content)
                    if "json" in response.headers["Content-Type"]
                    else content
                )
                return response.status, result, dict(response.headers)
        except urllib.error.HTTPError as error:
            result = error.code, json.loads(error.read()), dict(error.headers)
            error.close()
            return result

    def test_shell_lookup_detail_history_and_security_headers(self) -> None:
        status, shell, headers = self.request("/concepts")
        self.assertEqual(status, 200)
        self.assertIn("RFI Admin Console", shell)
        self.assertIn("Concept Catalog", shell)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        status, result, _ = self.request("/api/concepts?q=HAMR&valid_on=2024-06-28")
        self.assertEqual(status, 200)
        self.assertEqual(len(result["items"]), 2)
        detail = self.request("/api/concepts/gross-margin")[1]
        self.assertEqual(len(detail["methods"]), 3)
        history = self.request("/api/concepts/gross-margin/history")[1]
        self.assertEqual(len(history["items"]), 1)

    def test_create_validate_edit_retire_and_persist_through_public_api(self) -> None:
        payload = asdict(ConceptCatalogTests.generic(self, "browser-created"))
        status, validation, _ = self.request(
            "/api/concepts/validate", "POST", payload
        )
        self.assertEqual((status, validation["valid"]), (200, True))
        status, created, _ = self.request("/api/concepts", "POST", payload)
        self.assertEqual(status, 201)
        payload["comments"] = "Edited through HTTP service contract"
        status, revised, _ = self.request(
            "/api/concepts/browser-created",
            "PUT",
            {"expected_revision_id": created["revision_id"], "concept": payload},
        )
        self.assertEqual((status, revised["revision_number"]), (200, 2))
        status, retired, _ = self.request(
            "/api/concepts/browser-created/retire",
            "POST",
            {"expected_revision_id": revised["revision_id"]},
        )
        self.assertEqual((status, retired["status"]), (200, "retired"))
        history = self.request("/api/concepts/browser-created/history")[1]["items"]
        self.assertEqual(len(history), 3)
        self.assertEqual(
            ConceptRepository.open(self.root / "catalog").get("browser-created").status,
            ConceptStatus.RETIRED,
        )

    def test_invalid_requests_forms_and_paths_are_visible(self) -> None:
        self.assertEqual(self.request("/api/missing")[0], 404)
        self.assertEqual(self.request("/api/%2e%2e/catalog.json")[0], 400)
        status, result, _ = self.request(
            "/api/concepts",
            "POST",
            {"concept_id": "../unsafe"},
        )
        self.assertEqual(status, 400)
        self.assertIn("invalid concept identifier", result["error"])
        status, result, _ = self.request(
            "/api/concepts/validate",
            "POST",
            {"concept_id": "bad", "methods": "not-an-array"},
        )
        self.assertEqual(status, 200)
        self.assertFalse(result["valid"])

    def test_default_local_binding_and_unavailable_port_failure(self) -> None:
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        try:
            with self.assertRaises(OSError):
                create_admin_server(self.root / "catalog", port=port)
        finally:
            blocker.close()

    def test_console_adapter_uses_service_not_persistence_files(self) -> None:
        source = (SRC / "rfi/admin/server.py").read_text(encoding="utf-8")
        for forbidden in ("revisions_root", "catalog.json", "write_text", "write_bytes"):
            self.assertNotIn(forbidden, source)
        service = ConceptService(ConceptRepository.open(self.root / "catalog"))
        self.assertEqual(service.detail("revenue").concept_id, "revenue")


if __name__ == "__main__":
    unittest.main()
