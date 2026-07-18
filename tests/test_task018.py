from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.admin import create_admin_server
from rfi.artifacts import ArtifactOrder, ArtifactQuery, ArtifactQueryError, ArtifactQueryService
from rfi.concepts import ConceptRepository
from rfi.firms import FirmDraft, FirmRepository, sample_firms
from rfi.source_profiles import SourceProfileRepository, load_canonical_template


class ArtifactRepositoryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        ConceptRepository.initialize(self.state)
        self.firms = FirmRepository.initialize(self.state / "firm-catalog")
        self.firms.create(sample_firms()[0])
        self.firms.create(
            FirmDraft(
                firm_id="amazon",
                canonical_name="Amazon",
                valid_from="2020-01-01",
                legal_name="Amazon.com, Inc.",
            )
        )
        self.template = load_canonical_template()
        SourceProfileRepository.initialize(self.state / "source-profiles", self.template)
        self.repository = AcquisitionRepository(self.state / "acquisition")
        self.service = ArtifactQueryService(self.repository, self.firms, self.template)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def ingest(
        self,
        firm_id: str,
        accession: str,
        filing_date: str,
        accepted: str,
        retrieved: str,
        content: bytes | None = None,
        media_type: str = "text/html",
    ) -> str:
        suffix = accession.replace("-", "")
        source_id = f"source-{firm_id}-sec-10k"
        self.repository.register_source(
            SourceProfile(
                source_id,
                f"{firm_id} annual filing",
                True,
                "sec-form-10k",
                {"mode": "identifier"},
                {
                    "firm_id": firm_id,
                    "artifact_id": "sec_10k",
                    "source_profile_revision_id": f"profile-{firm_id}-one",
                    "retrieval_adapter_id": "sec-form-10k",
                },
            )
        )
        document_id = f"document-sec-{firm_id}-{suffix}"
        candidate = CandidateDocument(
            f"candidate-{firm_id}-{suffix}",
            source_id,
            document_id,
            DiscoveryProvenance(
                accepted,
                "sec-form-10k",
                {
                    "provider": "SEC EDGAR",
                    "sec_accession": accession,
                    "sec_primary_document": f"{firm_id}.htm",
                },
                (
                    f"https://data.sec.gov/submissions/{firm_id}.json",
                    f"https://www.sec.gov/Archives/{suffix}/{firm_id}.htm",
                ),
                {
                    "adapter_id": "sec-form-10k",
                    "provider": "SEC EDGAR",
                    "form_type": "10-K",
                    "filing_date": filing_date,
                    "acceptance_datetime": accepted,
                    "period_of_report": filing_date,
                    "accession_number": accession,
                    "primary_document": f"{firm_id}.htm",
                },
            ),
        )
        body = content or f"<h1>{firm_id} {filing_date}</h1>".encode()
        self.repository.record_success(
            f"attempt-{firm_id}-{suffix}",
            candidate,
            RetrievalResult(
                body,
                media_type,
                retrieved,
                "sec-form-10k",
                {"provider": "SEC EDGAR", "sec_accession": accession},
            ),
        )
        return document_id

    def seed(self) -> tuple[str, str, str]:
        older = self.ingest(
            "seagate", "0001-24-000001", "2024-06-28", "2024-06-28T12:00:00Z",
            "2026-07-18T15:00:00Z",
        )
        newer = self.ingest(
            "seagate", "0001-25-000002", "2025-06-27", "2025-06-27T12:00:00Z",
            "2025-06-27T12:01:00Z",
            b"<script>parent.localStorage.setItem('owned','yes')</script><h1>Stored</h1>",
        )
        amazon = self.ingest(
            "amazon", "0002-25-000003", "2025-02-07", "2025-02-07T10:00:00Z",
            "2026-07-18T16:00:00Z",
        )
        return older, newer, amazon

    def test_normalized_query_latest_dates_details_and_content(self) -> None:
        older, newer, _amazon = self.seed()
        page = self.service.query(
            ArtifactQuery(
                firm_ids=("seagate",), canonical_artifact_ids=("sec_10k",), limit=10
            )
        )
        self.assertEqual([item.document_id for item in page.items], [newer, older])
        latest = self.service.latest("seagate", "sec_10k")
        oldest = self.service.oldest("seagate", "sec_10k")
        self.assertIsNotNone(latest)
        self.assertIsNotNone(oldest)
        self.assertEqual(latest.document_id, newer)  # type: ignore[union-attr]
        self.assertEqual(oldest.document_id, older)  # type: ignore[union-attr]
        self.assertEqual(page.items[0].source_effective.basis, "acceptance_datetime")
        self.assertLess(page.items[0].ingestion_time, page.items[1].ingestion_time)
        bounded = self.service.query(
            ArtifactQuery(
                firm_ids=("seagate",), source_effective_through="2024-12-31", limit=10
            )
        )
        self.assertEqual([item.document_id for item in bounded.items], [older])
        detail = self.service.detail(newer)
        self.assertEqual(detail.summary.canonical_artifact_id, "sec_10k")
        self.assertEqual(detail.summary.provider_artifact_type, "10-K")
        self.assertEqual(
            detail.original_source_url,
            "https://www.sec.gov/Archives/000125000002/seagate.htm",
        )
        self.assertEqual(self.service.content(newer).content[:8], b"<script>")

    def test_pagination_is_bounded_stable_and_rejects_invalid_or_stale_cursor(self) -> None:
        self.seed()
        first = self.service.query(ArtifactQuery(limit=1))
        self.assertEqual(len(first.items), 1)
        self.assertIsNotNone(first.next_cursor)
        second = self.service.query(ArtifactQuery(limit=1, cursor=first.next_cursor))
        self.assertNotEqual(first.items[0].document_id, second.items[0].document_id)
        repeated = self.service.query(ArtifactQuery(limit=1, cursor=first.next_cursor))
        self.assertEqual(second, repeated)
        with self.assertRaisesRegex(ArtifactQueryError, "malformed"):
            self.service.query(ArtifactQuery(limit=1, cursor="not-a-cursor"))
        self.ingest(
            "amazon", "0002-24-000004", "2024-02-02", "2024-02-02T10:00:00Z",
            "2024-02-02T10:01:00Z",
        )
        with self.assertRaisesRegex(ArtifactQueryError, "restart pagination"):
            self.service.query(ArtifactQuery(limit=1, cursor=first.next_cursor))
        with self.assertRaisesRegex(ArtifactQueryError, "between 1 and 100"):
            self.service.query(ArtifactQuery(limit=101))

    def test_tree_projection_empty_semantics_restart_replay_and_network_block(self) -> None:
        self.seed()
        self.assertEqual([item["firm_id"] for item in self.service.firms()], ["amazon", "seagate"])
        families = self.service.families("seagate")
        self.assertEqual(families[0]["family_id"], "regulatory_financial")
        types = self.service.canonical_types("seagate", "regulatory_financial")
        self.assertEqual(types[0]["canonical_artifact_id"], "sec_10k")
        self.assertEqual(self.service.query(ArtifactQuery(firm_ids=("western-digital",))).items, ())
        before = self.service.query(ArtifactQuery(limit=10))
        self.repository.delete_derived_state()
        with patch.object(socket, "socket", side_effect=AssertionError("network blocked")):
            self.repository.replay()
            restarted = ArtifactQueryService(
                AcquisitionRepository(self.state / "acquisition"),
                FirmRepository.open(self.state / "firm-catalog"),
                load_canonical_template(),
            ).query(ArtifactQuery(limit=10))
        self.assertEqual(before, restarted)
        self.assertEqual(self.repository.verify_integrity()["result"], "PASS")

    def test_admin_api_browser_and_preview_security_boundary(self) -> None:
        _older, newer, _amazon = self.seed()
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        base = f"http://{host}:{port}"
        try:
            with urllib.request.urlopen(base + "/artifacts", timeout=3) as response:
                html = response.read().decode()
            for marker in (
                "Artifact Repository", "role=\"tree\"", "Open stored document in new tab",
                "Open original source", "setAttribute('sandbox','')", "Load more",
            ):
                self.assertIn(marker, html)
            for forbidden in ("Edit artifact", "Delete artifact", "Rename artifact"):
                self.assertNotIn(forbidden, html)
            with urllib.request.urlopen(
                base + "/api/artifacts/" + urllib.parse.quote(newer) + "/content", timeout=3
            ) as response:
                body = response.read()
                csp = response.headers["Content-Security-Policy"]
                self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn(b"parent.localStorage", body)
            self.assertIn("sandbox", csp)
            self.assertIn("default-src 'none'", csp)
            self.assertNotIn("allow-scripts", csp)
            with urllib.request.urlopen(
                urllib.request.Request(
                    base + "/api/artifacts/" + urllib.parse.quote(newer) + "/content",
                    headers={"Range": "bytes=0-7"},
                ),
                timeout=3,
            ) as response:
                self.assertEqual((response.status, response.read()), (206, b"<script>"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_contracts_are_json_projectable_and_filters_reject_provider_free_form(self) -> None:
        self.seed()
        encoded = json.dumps(asdict(self.service.query(ArtifactQuery(limit=2))), default=str)
        self.assertIn("source_effective", encoded)
        with self.assertRaisesRegex(ArtifactQueryError, "only durable"):
            self.service.query(ArtifactQuery(durable_statuses=("failed",)))
        with self.assertRaisesRegex(ArtifactQueryError, "unknown canonical"):
            self.service.query(ArtifactQuery(canonical_artifact_ids=("sec_any_form",)))


if __name__ == "__main__":
    unittest.main()
