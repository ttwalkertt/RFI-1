"""Focused acceptance evidence for TASK-056 persistent discovery anchors."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository, CandidateDocument, DiscoveryProvenance,
    EarningsTranscriptHttpResponse, FailurePoint,
    RetrievalOutcome, RetrievalResult, SourceProfile,
)
from rfi.discovery import (
    DiscoveryPolicy, DiscoveryPolicyCatalog, DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.storage import RepositoryDatabase


class DiscoveryAnchorHistoryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        firms = FirmRepository.initialize(self.root / "firms")
        for firm in ("firm-a", "firm-b"):
            firms.create(FirmDraft(firm, firm, "2026-01-01", status=FirmStatus.ACTIVE))
        self.repository = AcquisitionRepository(self.root / "acquisition")
        for firm, source in (("firm-a", "source-a"), ("firm-a", "source-b"),
                             ("firm-b", "source-c")):
            self.repository.register_source(SourceProfile(
                source, source, True, "earnings_transcript", {},
                {"firm_id": firm, "artifact_id": "earnings_transcript",
                 "retrieval_adapter_id": "earnings-call-transcript",
                 "source_profile_revision_id": "profile-r1"},
            ))

    def anchors(self, firm: str = "firm-a", source: str = "source-a"):
        return self.repository.discovery_anchors(
            firm, source, "earnings-call-transcript"
        )

    def success(self, key: str, requested: str, resolved: str | None = None,
                source: str = "source-a", fail_at: FailurePoint | None = None,
                content: bytes | None = None):
        candidate = CandidateDocument(
            f"candidate-{key}", source, f"document-{key}",
            DiscoveryProvenance(
                f"2026-08-01T00:00:0{len(key)}Z", "earnings_transcript",
                locations=(requested,), metadata={"requested_url": requested},
            ),
        )
        return self.repository.record_success(
            f"attempt-{key}", candidate,
            RetrievalResult(
                content or f"artifact-{key}".encode(), "text/html",
                "2026-08-01T00:00:00Z",
                "earnings_transcript", diagnostics={"final_url": resolved or requested},
            ), fail_at=fail_at,
        )

    def test_empty_lifo_move_to_front_dedup_eviction_and_exact_provenance(self) -> None:
        self.assertEqual(self.anchors(), ())
        urls = [f"https://IR.Example.com:443/a/../call-{n}?token={n}#section"
                for n in range(4)]
        for index, url in enumerate(urls):
            self.success(str(index), url, url.replace("IR.Example.com:443", "ir.example.com"))
        anchors = self.anchors()
        self.assertEqual([x["requested_url"] for x in anchors], urls[3:0:-1])
        self.assertEqual(len(anchors), 3)
        self.assertEqual(anchors[0]["normalized_url"],
                         "https://ir.example.com/call-3?token=3")
        self.success("repeat", urls[1], urls[1].replace("IR.Example.com:443", "ir.example.com"))
        moved = self.anchors()
        self.assertEqual(moved[0]["requested_url"], urls[1])
        self.assertEqual(len(moved), 3)
        self.assertEqual(moved[0]["resolved_url"],
                         urls[1].replace("IR.Example.com:443", "ir.example.com"))
        receipt = self.success(
            "no-change", urls[1],
            urls[1].replace("IR.Example.com:443", "ir.example.com"),
            content=b"artifact-1",
        )
        self.assertFalse(receipt.artifact_created)
        self.assertEqual(self.anchors()[0]["attempt_id"], "attempt-no-change")

    def test_failures_and_transaction_rollback_do_not_teach(self) -> None:
        requested = "https://ir.example.com/call"
        candidate = CandidateDocument(
            "candidate-failed", "source-a", "document-failed",
            DiscoveryProvenance("2026-08-01T00:00:00Z", "earnings_transcript",
                                metadata={"requested_url": requested}),
        )
        self.repository.record_outcome(
            "attempt-failed", candidate, RetrievalOutcome.FAILED,
            "2026-08-01T00:00:00Z", "earnings_transcript", {"code": "validation_failed"},
        )
        self.assertEqual(self.anchors(), ())
        with self.assertRaises(RuntimeError):
            self.success("rollback", requested, fail_at=FailurePoint.BEFORE_INDEX)
        self.assertEqual(self.anchors(), ())
        with self.repository._database.connect(read_only=True) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM acquisition_attempts WHERE attempt_id='attempt-rollback'"
            ).fetchone()[0], 0)

    def test_revision_changes_and_key_isolation_preserve_history(self) -> None:
        url = "https://ir.example.com/call"
        self.success("a", url)
        self.success("b", "https://ir.example.com/other", source="source-b")
        self.success("c", "https://ir.example.com/firm-b", source="source-c")
        self.assertEqual(len(self.anchors()), 1)
        self.assertEqual(len(self.anchors("firm-a", "source-b")), 1)
        self.assertEqual(len(self.anchors("firm-b", "source-c")), 1)
        self.assertEqual(self.anchors()[0]["source_profile_revision_id"], "profile-r1")

    def test_v14_populated_migration_adds_empty_history_without_changing_evidence(self) -> None:
        self.success("existing", "https://ir.example.com/existing")
        database = RepositoryDatabase.open(self.root)
        with database.connect() as connection:
            attempt_count = connection.execute(
                "SELECT count(*) FROM acquisition_attempts"
            ).fetchone()[0]
            connection.execute("DROP TABLE discovery_anchor_history")
            connection.execute("UPDATE schema_metadata SET schema_version=14")
        migrated = RepositoryDatabase.open(self.root)
        with migrated.connect(read_only=True) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM acquisition_attempts"
            ).fetchone()[0], attempt_count)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM discovery_anchor_history"
            ).fetchone()[0], 0)

    def test_retained_anchor_precedes_hint_and_failure_falls_through_without_search(self) -> None:
        retained = "https://ir.example.com/old-call"
        hint = "https://ir.example.com/transcripts"
        candidate = "https://ir.example.com/2026-02-01-earnings-call-transcript.html"
        self.success("anchor", retained)

        class Transport:
            def __init__(self):
                self.requests: list[str] = []

            def get(inner, url: str):
                inner.requests.append(url)
                if url == retained:
                    raise TimeoutError("stale anchor")
                if url == hint:
                    return EarningsTranscriptHttpResponse(
                        hint, 200, "text/html",
                        (f"<html><a href='{candidate}'>Earnings call transcript "
                         "2026-02-01</a></html>").encode(),
                    )
                return EarningsTranscriptHttpResponse(
                    candidate, 200, "text/html",
                    b"<!doctype html><html>Quarterly earnings call transcript. "
                    b"Operator: Welcome. Chief Executive Officer. Questions and Answers</html>",
                )

        class Search:
            endpoint = "https://search.example/"
            calls = 0

            def search(inner, query: str, limit: int):
                inner.calls += 1
                return DiscoverySearchResponse((), 0)

        transport, search = Transport(), Search()
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog(
                {"standard": DiscoveryPolicy(2, 5, 10, 2, 10, 4, 1_000_000, 60)},
                "standard",
            ), search, transport, lambda: "2026-08-01T00:00:00Z",
            repository=self.repository,
        )
        profile = SourceProfile(
            "source-a", "source-a", True, "earnings_transcript",
            {"mode": "discovery", "discovery_class": "standard",
             "discovery_hints": [hint]},
            {"firm_id": "firm-a", "artifact_id": "earnings_transcript",
             "retrieval_adapter_id": "earnings-call-transcript"},
        )
        page = adapter.discover(profile, None)
        self.assertEqual(transport.requests[:2], [retained, hint])
        self.assertEqual(search.calls, 0)
        self.assertEqual(len(page.candidates), 1)
        self.assertEqual(page.diagnostics["retained_anchor_order"],
                         ["https://ir.example.com/old-call"])
        self.assertEqual(len(self.anchors()), 1, "failed anchor must not be removed")


if __name__ == "__main__":
    unittest.main()
