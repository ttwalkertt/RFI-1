"""Acceptance coverage for TASK-025 revisioned multi-level artifact streams."""

from __future__ import annotations

import json
import hashlib
import re
import tempfile
import threading
import unittest
import urllib.request
from dataclasses import asdict, replace
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
from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.mailing_lists.contracts import ArchiveMessage
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase
from rfi.streams import (
    ArtifactProjection,
    StreamDraft,
    StreamError,
    StreamRepository,
    StreamService,
)

ROOT = Path(__file__).resolve().parents[1]


def mail_archive() -> FixtureMailingListArchive:
    messages = {}
    for path in sorted((ROOT / "fixtures/linux-block").glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    return FixtureMailingListArchive(messages)


def predicate(field: str, value: object, operator: str = "contains") -> dict[str, object]:
    return {"op": "predicate", "field": field, "operator": operator, "value": value}


class StreamCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        mail_repository = MailingListRepository(self.state)
        mail_repository.configure_source(LINUX_BLOCK_SOURCE)
        MailingListAcquisitionService(
            mail_repository, mail_archive(),
            clock=lambda: "2026-07-19T12:00:00+00:00",
            identifiers=lambda: "mailrun-task025",
        ).acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(
                "<task023-a1@kernel.example>", "<task023-b1@kernel.example>",
            )),
            AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=3),
        )
        self.repository = StreamRepository(self.state)
        identifiers = iter(f"streamrun-{index}" for index in range(100))
        self.service = StreamService(
            self.repository, clock=lambda: "2026-07-20T12:00:00+00:00",
            identifiers=identifiers.__next__,
        )
        self._create_sec_artifacts()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create_sec_artifacts(self) -> None:
        artifacts = AcquisitionRepository(self.state / "acquisition")
        artifacts.register_source(SourceProfile(
            "sec-fixture", "SEC fixture", True, "fixture",
            policy={"repository_projection": "fixture"},
        ))
        projections = []
        for index, form in enumerate(("10-K", "8-K", "20-F"), 1):
            content = f"{form} deterministic filing fixture".encode()
            candidate = CandidateDocument(
                f"sec-candidate-{index}", "sec-fixture", f"sec-document-{index}",
                DiscoveryProvenance(
                    f"2026-0{index}-01T00:00:00+00:00", "fixture",
                    {"accession": f"000{index}"}, metadata={"form_type": form},
                ),
            )
            receipt = artifacts.record_success(
                f"sec-attempt-{index}", candidate,
                RetrievalResult(
                    content, "text/plain", f"2026-0{index}-01T00:00:00+00:00",
                    "fixture", {"accession": f"000{index}"},
                ),
            )
            projections.append(ArtifactProjection(
                receipt.artifact_id, receipt.document_id, "sec.filing", "sec-fixture",
                f"2026-0{index}-01T00:00:00+00:00", f"Fixture {form}", content.decode(),
                ("Example issuer",),
                {"sec.form_type": form, "sec.accession": f"000{index}"},
            ))
        self.repository.upsert_projections(projections)

    def external_mail(self) -> StreamDraft:
        return StreamDraft(
            "linux-block", "Linux block", "Bounded retained Lore stream", True,
            "external", (LINUX_BLOCK_SOURCE.source_id,), "mail.message",
            predicate("title", "deterministic queue"),
            {"strategy": "connected_discussion", "ancestor_closure": True,
             "descendant_depth": 3},
            {"seed_limit": 20, "expanded_limit": 50},
        )

    def derived(self, stream_id: str, term: str, upstream: str = "linux-block") -> StreamDraft:
        return StreamDraft(
            stream_id, stream_id.replace("-", " ").title(), "Derived mail stream", True,
            "streams", (upstream,), "mail.message", predicate("text", term),
            {"strategy": "connected_discussion", "ancestor_closure": True,
             "descendant_depth": 3},
            {"seed_limit": 10, "expanded_limit": 50},
        )

    def save_graph(self) -> None:
        self.service.save(self.external_mail())
        self.service.save(self.derived("zoned-storage", "lifetime"))
        self.service.save(self.derived("blk-mq", "ordering"))
        self.service.save(self.derived("queue-review", "deterministic", "zoned-storage"))

    def test_external_revision_multilevel_fanout_and_cycle_rejection(self) -> None:
        external = self.service.save(self.external_mail())
        revised = self.service.save(
            replace(self.external_mail(), description="Revised description"),
            external.revision_id,
        )
        self.assertEqual(revised.revision_number, 2)
        self.save_graph_after_external(revised)
        summaries = {item.stream_id: item for item in self.service.list_streams()}
        self.assertEqual(set(summaries["linux-block"].consumer_ids), {"zoned-storage", "blk-mq"})
        self.assertEqual(summaries["queue-review"].upstream_ids, ("zoned-storage",))
        cycle = replace(self.external_mail(), input_kind="streams", input_ids=("queue-review",))
        validation = self.service.validate(cycle)
        self.assertFalse(validation.valid)
        self.assertIn("dependency_cycle", {item["code"] for item in validation.errors})
        self.assertIn("self_reference", {
            item["code"] for item in self.service.validate(
                self.derived("zoned-storage", "x", "zoned-storage")
            ).errors
        })

    def save_graph_after_external(self, revision: object) -> None:
        del revision
        self.service.save(self.derived("zoned-storage", "lifetime"))
        self.service.save(self.derived("blk-mq", "ordering"))
        self.service.save(self.derived("queue-review", "deterministic", "zoned-storage"))

    def test_typed_validation_rejects_unsupported_fields_and_unknown_sources(self) -> None:
        invalid = replace(
            self.external_mail(),
            selection=predicate("attribute:sec.form_type", "10-K"),
        )
        result = self.service.validate(invalid)
        self.assertFalse(result.valid)
        self.assertIn("unsupported_predicate", {item["code"] for item in result.errors})
        unknown = replace(self.external_mail(), input_ids=("unknown-source",))
        self.assertIn("unknown_source", {
            item["code"] for item in self.service.validate(unknown).errors
        })

    def test_topological_execution_lineage_idempotency_and_no_byte_duplication(self) -> None:
        self.save_graph()
        artifact_count = len(self.repository.artifacts.artifact_metadata())
        runs = self.service.run_chain("queue-review")
        self.assertEqual([item.stream_id for item in runs], [
            "linux-block", "zoned-storage", "queue-review"
        ])
        zoned = self.repository.memberships("zoned-storage")
        self.assertEqual(len(zoned), 5)
        self.assertGreaterEqual(sum(item.inclusion_kind == "direct" for item in zoned), 1)
        self.assertGreaterEqual(sum(item.inclusion_kind == "context" for item in zoned), 1)
        self.assertTrue(all(item.lineage for item in zoned))
        self.assertTrue(any(item.lineage[0].get("upstream_membership_id") for item in zoned))
        self.service.run_chain("blk-mq")
        self.assertEqual(len(self.repository.artifacts.artifact_metadata()), artifact_count)
        repeat = self.service.run("zoned-storage")
        self.assertTrue(repeat.idempotent)
        self.assertEqual(len(self.repository.runs("zoned-storage")), 1)

    def test_cross_schema_uses_generic_engine_and_none_expansion(self) -> None:
        sec = StreamDraft(
            "annual-regulatory-reports", "Annual regulatory reports", "SEC proof", True,
            "external", ("sec-fixture",), "sec.filing",
            predicate("attribute:sec.form_type", ["10-K", "20-F"], "in"),
            {"strategy": "none", "descendant_depth": 0},
            {"seed_limit": 10, "expanded_limit": 10},
        )
        self.service.save(sec)
        run = self.service.run(sec.stream_id)
        memberships = self.repository.memberships(sec.stream_id)
        self.assertEqual((run.direct_count, run.context_count), (2, 0))
        self.assertEqual(
            {item.projection.attributes["sec.form_type"] for item in memberships},
            {"10-K", "20-F"},
        )
        self.assertTrue(all(item.expansion_strategy == "none" for item in memberships))

    def test_failed_publication_has_no_memberships_and_retry_recovers(self) -> None:
        self.service.save(self.external_mail())
        with patch.object(
            self.repository, "publish_run",
            side_effect=StreamError("publication_failure", "injected failure"),
        ):
            with self.assertRaisesRegex(StreamError, "injected failure"):
                self.service.run("linux-block")
        failed = self.repository.runs("linux-block")[0]
        self.assertEqual(failed.status, "failed")
        self.assertEqual(self.repository.memberships("linux-block"), ())
        recovered = self.service.run("linux-block")
        self.assertEqual(recovered.status, "succeeded")
        self.assertGreater(len(self.repository.memberships("linux-block")), 0)

    def test_failed_replacement_keeps_prior_success_current_and_historical(self) -> None:
        revision = self.service.save(self.external_mail())
        first = self.service.run("linux-block")
        prior = self.repository.memberships("linux-block", first.run_id)
        self.service.save(
            replace(
                self.external_mail(),
                selection=predicate("title", "zoned"),
            ),
            revision.revision_id,
        )
        insert = self.repository._insert_publications

        def fail_after_one(connection, run_id, stream_id, revision_id, publications):
            insert(connection, run_id, stream_id, revision_id, publications[:1])
            raise StreamError("publication_failure", "injected replacement failure")

        with patch.object(self.repository, "_insert_publications", side_effect=fail_after_one):
            with self.assertRaisesRegex(StreamError, "injected replacement failure"):
                self.service.run("linux-block")
        failed = self.repository.runs("linux-block")[0]
        self.assertEqual(failed.status, "failed")
        self.assertEqual(
            self.repository.rows(
                "SELECT membership_id FROM artifact_stream_memberships WHERE run_id=?",
                (failed.run_id,),
            ),
            [],
        )
        self.assertEqual(self.repository.memberships("linux-block"), prior)
        self.assertEqual(self.repository.memberships("linux-block", first.run_id), prior)

    def test_offline_rebuild_is_equivalent_and_hashes_unchanged(self) -> None:
        self.save_graph()
        self.service.run_chain("queue-review")
        before = [asdict(item) for item in self.repository.memberships("queue-review")]
        hashes = {item["artifact_id"]: item["sha256"]
                  for item in self.repository.artifacts.artifact_metadata()}
        self.repository.delete_materialized_memberships()
        self.assertEqual(self.repository.memberships("queue-review"), ())
        result = self.service.rebuild()
        after = [asdict(item) for item in self.repository.memberships("queue-review")]
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(after, before)
        self.assertEqual(
            {item["artifact_id"]: item["sha256"]
             for item in self.repository.artifacts.artifact_metadata()}, hashes,
        )

    def test_no_match_recompute_preserves_evidence_history_and_lineage(self) -> None:
        first_revision = self.service.save(self.external_mail())
        first_run = self.service.run("linux-block")
        historical_before = self.repository.memberships("linux-block", first_run.run_id)
        artifact_ids = tuple(item.artifact_id for item in historical_before)
        bytes_before = {
            artifact_id: hashlib.sha256(
                self.repository.artifacts.read_artifact(artifact_id)
            ).hexdigest()
            for artifact_id in artifact_ids
        }
        artifacts_before = self.repository.artifacts.artifact_metadata()
        observations_before = self.repository.artifacts.observations()
        acquisition_before = self.repository.artifacts.history()
        lineage_before = self.repository.rows(
            "SELECT * FROM artifact_stream_membership_lineage WHERE membership_id IN "
            "(SELECT membership_id FROM artifact_stream_memberships WHERE run_id=?) "
            "ORDER BY lineage_id",
            (first_run.run_id,),
        )

        revised = replace(
            self.external_mail(),
            selection=predicate("title", "definitely-absent-from-retained-evidence"),
        )
        second_revision = self.service.save(revised, first_revision.revision_id)
        second_run = self.service.run("linux-block")

        self.assertEqual(second_revision.revision_number, 2)
        self.assertEqual(second_run.status, "succeeded")
        self.assertEqual(self.repository.memberships("linux-block"), ())
        self.assertEqual(
            self.repository.memberships("linux-block", first_run.run_id), historical_before
        )
        self.assertEqual(
            self.repository.rows(
                "SELECT * FROM artifact_stream_membership_lineage WHERE membership_id IN "
                "(SELECT membership_id FROM artifact_stream_memberships WHERE run_id=?) "
                "ORDER BY lineage_id",
                (first_run.run_id,),
            ),
            lineage_before,
        )
        self.assertEqual(self.repository.artifacts.artifact_metadata(), artifacts_before)
        self.assertEqual(self.repository.artifacts.observations(), observations_before)
        self.assertEqual(self.repository.artifacts.history(), acquisition_before)
        self.assertEqual(
            {
                artifact_id: hashlib.sha256(
                    self.repository.artifacts.read_artifact(artifact_id)
                ).hexdigest()
                for artifact_id in artifact_ids
            },
            bytes_before,
        )

    def test_admin_and_artifact_browser_share_stream_contracts(self) -> None:
        self.service.save(self.external_mail())
        self.service.run("linux-block")
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/streams") as response:
                html = response.read().decode()
            self.assertIn("Typed selection policy", html)
            self.assertIn("Run dependency chain", html)
            with urllib.request.urlopen(base + "/api/streams") as response:
                stream_data = json.load(response)
            self.assertEqual(stream_data["items"][0]["membership_count"], 5)
            with urllib.request.urlopen(base + "/api/external-sources") as response:
                source_data = json.load(response)["items"][0]
            self.assertEqual(source_data["source_id"], LINUX_BLOCK_SOURCE.source_id)
            self.assertEqual(
                source_data["configuration"]["archive_base_url"],
                LINUX_BLOCK_SOURCE.archive_base_url,
            )
            self.assertEqual(source_data["policy"]["transport"]["maximum_concurrency"], 1)
            with urllib.request.urlopen(
                base + "/api/streams/linux-block/memberships"
            ) as response:
                memberships = json.load(response)["items"]
            membership_id = memberships[0]["membership_id"]
            with urllib.request.urlopen(
                base + "/api/stream-memberships/" + membership_id
            ) as response:
                detail = json.load(response)
            self.assertIn(detail["inclusion_kind"], {"direct", "context"})
            with urllib.request.urlopen(base + "/artifacts") as response:
                browser = response.read().decode()
            self.assertIn("Artifact streams", browser)
            self.assertIn("Upstream / seed lineage", browser)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_every_top_level_page_uses_one_authoritative_navigation(self) -> None:
        expected = (
            ("/concepts", "Concept Catalog"),
            ("/firms", "Target Firms"),
            ("/source-profiles", "Firm Profiles"),
            ("/external-sources", "External Sources"),
            ("/pull-sources", "Pull Sources"),
            ("/linux-mailing-lists", "Linux Mailing Lists"),
            ("/streams", "Streams"),
            ("/artifacts", "Artifacts"),
        )
        admin_assets = ROOT / "src/rfi/admin"
        for filename in (
            "console.html", "firms.html", "source_profiles.html", "external_sources.html",
            "pull_sources.html", "linux_mailing_lists.html", "streams.html",
            "artifact_browser.html",
        ):
            template = (admin_assets / filename).read_text(encoding="utf-8")
            self.assertEqual(template.count("<!-- operator-navigation -->"), 1)
            self.assertNotIn("<nav", template)

        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            for active_path, _active_label in expected:
                with self.subTest(route=active_path):
                    with urllib.request.urlopen(base + active_path) as response:
                        html = response.read().decode()
                    match = re.search(
                        r'<nav aria-label="Operator sections">(.*?)</nav>', html,
                    )
                    self.assertIsNotNone(match)
                    links = re.findall(
                        r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>',
                        match.group(1),  # type: ignore[union-attr]
                    )
                    rendered = tuple(
                        (href, label) for href, _active, label in links
                    )
                    self.assertEqual(rendered, expected)
                    active_links = [href for href, active, _label in links if active]
                    self.assertEqual(active_links, [active_path])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_schema_v2_migrates_to_current(self) -> None:
        tables = [
            "artifact_stream_membership_lineage", "artifact_stream_memberships",
            "artifact_stream_run_plans", "artifact_stream_runs",
            "artifact_stream_projections", "artifact_stream_dependencies",
            "artifact_stream_revisions", "artifact_streams",
        ]
        fresh = Path(self.temporary.name) / "migration"
        RepositoryDatabase.initialize(fresh)
        with RepositoryDatabase.open(fresh).connect() as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            for table in tables:
                connection.execute(f"DROP TABLE {table}")
            connection.execute("UPDATE schema_metadata SET schema_version=2")
        database = RepositoryDatabase.open(fresh)
        self.assertEqual(database.validate()["schema_version"], 5)
        with database.connect(read_only=True) as connection:
            names = {str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
            )}
        self.assertTrue(set(tables).issubset(names))


if __name__ == "__main__":
    unittest.main()
