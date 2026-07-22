"""Deterministic acceptance coverage for TASK-023 bounded mailing-list evidence."""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from rfi.admin import create_admin_server
from rfi.artifacts import ArtifactQuery, ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    ConnectivityState,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListError,
    MailingListQueryService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.mailing_lists.contracts import ArchiveMessage
from rfi.mailing_lists.parser import parse_message
from rfi.source_profiles import load_canonical_template
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/linux-block"


def fixture_archive(*, include_invalid: bool = True) -> FixtureMailingListArchive:
    messages: dict[str, ArchiveMessage] = {}
    for path in sorted(FIXTURES.glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    if include_invalid:
        messages["<requested-malformed@kernel.example>"] = ArchiveMessage(
            (FIXTURES / "malformed-id.eml").read_bytes(), "fixture:malformed-id.eml"
        )
    return FixtureMailingListArchive(messages)


def raw_message(message_id: str, subject: str, parent: str | None = None,
                body: str = "body") -> bytes:
    headers = [
        f"Message-ID: {message_id}", f"Subject: {subject}",
        "From: Test <test@example.com>", "Date: Fri, 17 Jul 2026 12:00:00 +0000",
    ]
    if parent:
        headers.append(f"In-Reply-To: {parent}")
    return ("\r\n".join(headers) + f"\r\n\r\n{body}\r\n").encode()


class PartialPatchSeriesArchive(FixtureMailingListArchive):
    """Three retained patch-series trees plus one unavailable remote descendant."""

    unavailable = "<patch-series-unavailable@kernel.example>"
    v3_root = "<patch-v3-0@kernel.example>"

    def fetch(self, external_message_id: str) -> ArchiveMessage:
        if external_message_id == self.unavailable:
            raise MailingListError(
                "archive_request_failed",
                "simulated unavailable patch-series descendant",
                retryable=True,
            )
        return super().fetch(external_message_id)

    def direct_children(
        self, external_message_id: str, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        children, has_more = super().direct_children(external_message_id, limit)
        if external_message_id != self.v3_root or len(children) >= limit:
            return children, has_more
        expanded = children + (self.unavailable,)
        return expanded[:limit], has_more or len(expanded) > limit


def partial_patch_series_archive() -> PartialPatchSeriesArchive:
    definitions = (
        ("<patch-v1-0@kernel.example>", "[PATCH 0/1] block: P2PDMA fixes", None),
        (
            "<patch-v1-1@kernel.example>",
            "[PATCH 1/1] block: P2PDMA fix",
            "<patch-v1-0@kernel.example>",
        ),
        ("<patch-v2-0@kernel.example>", "[PATCH v2 0/1] block: P2PDMA fixes", None),
        (
            "<patch-v2-1@kernel.example>",
            "[PATCH v2 1/1] block: P2PDMA fix",
            "<patch-v2-0@kernel.example>",
        ),
        (
            "<patch-v2-review@kernel.example>",
            "Re: [PATCH v2 1/1] block: P2PDMA fix",
            "<patch-v2-1@kernel.example>",
        ),
        (PartialPatchSeriesArchive.v3_root, "[PATCH v3 0/2] block: P2PDMA fixes", None),
        (
            "<patch-v3-1@kernel.example>",
            "[PATCH v3 1/2] block: P2PDMA fix",
            PartialPatchSeriesArchive.v3_root,
        ),
        (
            "<patch-v3-2@kernel.example>",
            "[PATCH v3 2/2] block: P2PDMA fix",
            PartialPatchSeriesArchive.v3_root,
        ),
    )
    return PartialPatchSeriesArchive({
        message_id: ArchiveMessage(
            raw_message(message_id, subject, parent), f"fixture:{message_id}"
        )
        for message_id, subject, parent in definitions
    })


class MailingListCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)
        self.repository.configure_source(LINUX_BLOCK_SOURCE)
        self.identifiers = iter(f"mailrun-{index}" for index in range(100))
        self.service = MailingListAcquisitionService(
            self.repository, fixture_archive(),
            clock=lambda: "2026-07-19T12:00:00+00:00",
            identifiers=self.identifiers.__next__,
        )
        self.query = MailingListQueryService(self.repository)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def acquire_branch(self):
        return self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(
                "<task023-a1@kernel.example>", "<task023-b1@kernel.example>",
            )),
            AcquisitionLimits(seed_limit=2, context_limit=20, descendant_depth=3),
        )

    def test_unbounded_selection_is_unavailable_and_limits_are_hard(self) -> None:
        with self.assertRaisesRegex(MailingListError, "explicit bounds"):
            SelectionCriteria()
        with self.assertRaisesRegex(MailingListError, "seed limit"):
            AcquisitionLimits(seed_limit=101)
        archive = fixture_archive()
        seeds, truncated = archive.discover(
            SelectionCriteria(topic_terms=("queue",)), 1
        )
        self.assertEqual(len(seeds), 1)
        self.assertTrue(truncated)

    def test_ancestor_outside_window_branching_and_converging_seeds(self) -> None:
        preview = self.service.preview(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(
                date_from="2026-07-16", topic_terms=("lifetime", "ordering")
            ),
            AcquisitionLimits(seed_limit=10, context_limit=20, descendant_depth=3),
        )
        self.assertGreaterEqual(len(preview.seed_ids), 2)
        manifest = self.acquire_branch()
        self.assertEqual(manifest.state, ConnectivityState.CONNECTED)
        self.assertEqual(manifest.discussion_count, 1)
        discussion = self.query.discussions(LINUX_BLOCK_SOURCE.source_id)[0]
        projection = self.query.projection(discussion.discussion_id)
        self.assertEqual(len(projection.messages), 5)
        root = self.query.message(discussion.root_message_key)
        self.assertEqual(root.summary.message_date, "2026-07-01T09:00:00+00:00")
        self.assertEqual(len(self.query.children(root.summary.message_key)), 2)
        for message in projection.messages:
            path = self.query.ancestors(message.message_key)
            self.assertEqual(path[0].message_key, discussion.root_message_key)

    def test_missing_connector_cannot_become_complete_discussion(self) -> None:
        manifest = self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=("<task023-missing-seed@kernel.example>",)),
            AcquisitionLimits(descendant_depth=0),
        )
        self.assertEqual(manifest.state, ConnectivityState.INCOMPLETE)
        self.assertFalse(manifest.required_ancestry_complete)
        self.assertFalse(manifest.descendant_policy_limited)
        self.assertEqual(manifest.discussion_count, 0)
        incomplete = self.query.incomplete(LINUX_BLOCK_SOURCE.source_id)
        self.assertEqual(len(incomplete), 1)
        detail = self.query.message(incomplete[0].message_key)
        self.assertEqual(
            detail.missing_parent_reference, "<task023-not-retained@kernel.example>"
        )

    def test_partial_v1_v2_v3_series_preserve_depth_for_retained_ancestor_paths(self) -> None:
        service = MailingListAcquisitionService(
            self.repository,
            partial_patch_series_archive(),
            clock=lambda: "2026-07-21T18:00:00+00:00",
            identifiers=lambda: "mailrun-partial-patch-series",
        )
        direct = (
            "<patch-v1-1@kernel.example>",
            "<patch-v2-review@kernel.example>",
            "<patch-v3-1@kernel.example>",
            "<patch-v3-2@kernel.example>",
        )
        manifest = service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=direct),
            AcquisitionLimits(seed_limit=4, context_limit=20, descendant_depth=3),
        )
        self.assertEqual(manifest.run_status.value, "partial")
        self.assertEqual(manifest.state, ConnectivityState.INCOMPLETE)
        self.assertEqual(manifest.message_count, 8)
        self.assertEqual(manifest.relationship_count, 5)
        self.assertEqual(manifest.discussion_count, 3)

        retained = {
            item.summary.external_message_id: item
            for item in self.query.acquisition_messages(manifest.run_id)
        }
        self.assertEqual(retained[direct[0]].summary.depth, 1)
        self.assertEqual(retained[direct[1]].summary.depth, 2)
        self.assertEqual(retained[direct[2]].summary.depth, 1)
        self.assertEqual(retained[direct[3]].summary.depth, 1)
        for message_id in direct:
            item = retained[message_id]
            self.assertTrue(item.direct_match)
            self.assertIsNotNone(item.discussion_id)
            self.assertIsNotNone(item.summary.immediate_parent_id)

        verification = self.repository.validate_connectivity()
        self.assertEqual(verification["validated_paths"], 8)
        self.assertEqual(verification["discussions"], 3)
        restarted = MailingListQueryService(MailingListRepository(self.state))
        restarted_messages = {
            item.summary.external_message_id: item
            for item in restarted.acquisition_messages(manifest.run_id)
        }
        self.assertEqual(restarted_messages[direct[1]].summary.depth, 2)

    def test_cycle_and_malformed_identity_are_quarantined(self) -> None:
        cycle = self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=("<task023-cycle-a@kernel.example>",)),
            AcquisitionLimits(),
        )
        malformed = self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=("<requested-malformed@kernel.example>",)),
            AcquisitionLimits(),
        )
        self.assertEqual(cycle.state, ConnectivityState.QUARANTINED)
        self.assertEqual(malformed.state, ConnectivityState.QUARANTINED)
        self.assertEqual(self.query.discussions(LINUX_BLOCK_SOURCE.source_id), ())
        self.assertEqual(len(self.query.incomplete(LINUX_BLOCK_SOURCE.source_id)), 3)

    def test_total_message_cap_truncates_only_at_connected_frontier(self) -> None:
        manifest = self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=("<task023-a1@kernel.example>",)),
            AcquisitionLimits(seed_limit=1, context_limit=3, descendant_depth=5),
        )
        self.assertEqual(manifest.state, ConnectivityState.TRUNCATED)
        self.assertTrue(manifest.unexpected_truncation)
        self.assertFalse(manifest.descendant_policy_complete)
        self.assertFalse(manifest.coverage_complete)
        discussion = self.query.discussions(LINUX_BLOCK_SOURCE.source_id)[0]
        self.assertEqual(discussion.connectivity_state, ConnectivityState.TRUNCATED)
        for message in self.query.projection(discussion.discussion_id).messages:
            self.assertEqual(
                self.query.ancestors(message.message_key)[0].message_key,
                discussion.root_message_key,
            )

    def test_reply_depth_saturation_is_successful_policy_limited_context(self) -> None:
        root = "<policy-root@kernel.example>"
        depth_one = "<policy-depth-one@kernel.example>"
        depth_two = "<policy-depth-two@kernel.example>"

        class BoundaryRecordingArchive(FixtureMailingListArchive):
            enumerated: list[str]

            def __init__(self, messages):
                super().__init__(messages)
                self.enumerated = []

            def direct_children(self, external_message_id, limit):
                self.enumerated.append(external_message_id)
                return super().direct_children(external_message_id, limit)

        archive = BoundaryRecordingArchive({
            root: ArchiveMessage(raw_message(root, "[PATCH] policy root"), "fixture:root"),
            depth_one: ArchiveMessage(
                raw_message(depth_one, "Re: [PATCH] policy root", root), "fixture:one"
            ),
            depth_two: ArchiveMessage(
                raw_message(depth_two, "Re: [PATCH] policy root", depth_one), "fixture:two"
            ),
        })
        service = MailingListAcquisitionService(
            self.repository, archive, identifiers=self.identifiers.__next__
        )

        manifest = service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(root,)),
            AcquisitionLimits(seed_limit=1, context_limit=10, descendant_depth=1),
        )

        self.assertEqual(manifest.run_status.value, "succeeded")
        self.assertEqual(manifest.state, ConnectivityState.CONNECTED)
        self.assertFalse(manifest.truncated)
        self.assertFalse(manifest.unexpected_truncation)
        self.assertTrue(manifest.discovery_complete)
        self.assertTrue(manifest.required_ancestry_complete)
        self.assertTrue(manifest.descendant_policy_complete)
        self.assertTrue(manifest.descendant_policy_limited)
        self.assertTrue(manifest.coverage_complete)
        self.assertEqual(manifest.message_count, 2)
        self.assertEqual(archive.enumerated, [root])
        retained_ids = {
            item.summary.external_message_id
            for item in self.query.acquisition_messages(manifest.run_id)
        }
        self.assertEqual(retained_ids, {root, depth_one})
        discussion = self.query.discussions(LINUX_BLOCK_SOURCE.source_id)[0]
        self.assertEqual(discussion.connectivity_state, ConnectivityState.CONNECTED)
        self.assertFalse(discussion.descendant_truncated)
        self.assertTrue(discussion.descendant_policy_limited)

        service.rebuild()
        rebuilt = self.query.discussions(LINUX_BLOCK_SOURCE.source_id)[0]
        self.assertTrue(rebuilt.descendant_policy_limited)

    def test_repeated_acquisition_is_idempotent_for_evidence_and_relationships(self) -> None:
        first = self.acquire_branch()
        second = self.acquire_branch()
        self.assertEqual(first.artifact_count_created, 5)
        self.assertEqual(second.artifact_count_created, 0)
        self.assertEqual(second.idempotent_messages, 5)
        self.assertEqual(len(self.repository.artifacts.artifact_metadata()), 5)
        self.assertEqual(len(self.repository.artifacts.observations()), 5)
        relationships = self.repository.rows(
            "SELECT * FROM mailing_list_relationships ORDER BY child_message_key"
        )
        self.assertEqual(len(relationships), 4)

    def test_conflicting_external_identity_fails_closed(self) -> None:
        root_id = "<task023-root@kernel.example>"
        self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(root_id,)),
            AcquisitionLimits(descendant_depth=0),
        )
        conflicting = FixtureMailingListArchive({
            root_id: ArchiveMessage(
                raw_message(root_id, "different subject", body="conflicting bytes"),
                "fixture:conflict",
            )
        })
        service = MailingListAcquisitionService(
            self.repository, conflicting, identifiers=self.identifiers.__next__
        )
        with self.assertRaisesRegex(MailingListError, "conflicting immutable bytes"):
            service.acquire(
                LINUX_BLOCK_SOURCE.source_id,
                SelectionCriteria(message_ids=(root_id,)),
                AcquisitionLimits(descendant_depth=0),
            )

    def test_structured_publication_failure_never_admits_and_retry_recovers(self) -> None:
        criteria = SelectionCriteria(message_ids=("<task023-a1@kernel.example>",))
        limits = AcquisitionLimits(seed_limit=1, context_limit=20, descendant_depth=3)
        with patch.object(
            self.repository, "publish",
            side_effect=MailingListError("repository_failure", "injected publication failure"),
        ):
            with self.assertRaisesRegex(MailingListError, "injected publication failure"):
                self.service.acquire(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
        self.assertEqual(self.query.discussions(LINUX_BLOCK_SOURCE.source_id), ())
        self.assertEqual(len(self.repository.artifacts.artifact_metadata()), 5)
        recovered = self.service.acquire(LINUX_BLOCK_SOURCE.source_id, criteria, limits)
        self.assertEqual(recovered.artifact_count_created, 0)
        self.assertEqual(recovered.idempotent_messages, 5)
        self.assertEqual(recovered.discussion_count, 1)

    def test_offline_rebuild_reproduces_projection_and_search(self) -> None:
        self.acquire_branch()
        before = self.query.discussions(LINUX_BLOCK_SOURCE.source_id)
        hits = self.query.search("memory ordering", LINUX_BLOCK_SOURCE.source_id)
        self.assertEqual(len(hits), 1)
        expected_hash = hashlib.sha256(self.query.content(hits[0].message_key).content).hexdigest()
        self.repository.delete_derived_for_rebuild()
        with self.assertRaisesRegex(MailingListError, "offline rebuild"):
            self.query.discussions(LINUX_BLOCK_SOURCE.source_id)
        rebuilt = self.service.rebuild()
        self.assertEqual(rebuilt["result"], "PASS")
        self.assertEqual(self.query.discussions(LINUX_BLOCK_SOURCE.source_id), before)
        self.assertEqual(
            hashlib.sha256(self.query.content(hits[0].message_key).content).hexdigest(),
            expected_hash,
        )

    def test_subject_similarity_never_creates_relationship(self) -> None:
        first = "<same-subject-one@kernel.example>"
        second = "<same-subject-two@kernel.example>"
        archive = FixtureMailingListArchive({
            first: ArchiveMessage(raw_message(first, "[PATCH] same topic"), "fixture:one"),
            second: ArchiveMessage(raw_message(second, "Re: [PATCH] same topic"), "fixture:two"),
        })
        service = MailingListAcquisitionService(
            self.repository, archive, clock=lambda: "now",
            identifiers=self.identifiers.__next__,
        )
        service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(first, second)), AcquisitionLimits(),
        )
        self.assertEqual(len(self.query.discussions(LINUX_BLOCK_SOURCE.source_id)), 2)
        self.assertEqual(self.repository.rows("SELECT * FROM mailing_list_relationships"), [])

    def test_shared_artifact_projection_ignores_non_firm_source(self) -> None:
        self.acquire_branch()
        service = ArtifactQueryService(
            self.repository.artifacts,
            FirmRepository.open(self.state / "firm-catalog"),
            load_canonical_template(),
        )
        self.assertEqual(service.query(ArtifactQuery()).items, ())
        browser = (ROOT / "src/rfi/admin/artifact_browser.html").read_text()
        self.assertIn("Development mailing lists", browser)
        self.assertIn("/api/mailing-lists/messages/", browser)
        self.assertIn("selectDiscussion(discussion,button)", browser)
        self.assertIn("Retained discussion size", browser)
        self.assertIn("Complete — context retained through configured reply depth", browser)
        self.assertIn("Policy-limited — retained through configured depth", browser)
        self.assertIn("Unexpected truncation before policy completion", browser)
        self.assertIn("A configured reply-depth boundary is an intentional context policy", browser)
        self.assertIn('aria-label=\"Discussion list summary\"', browser)
        self.assertNotIn("In-Reply-To').split", browser)

    def test_shared_browser_api_lazily_serves_branches_detail_and_content(self) -> None:
        self.acquire_branch()
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urlopen(base + "/api/mailing-lists/sources") as response:
                sources = json.loads(response.read())
            self.assertEqual(sources["items"][0]["discussion_count"], 1)
            source_id = LINUX_BLOCK_SOURCE.source_id
            with urlopen(
                base + f"/api/mailing-lists/discussions?source_id={source_id}"
            ) as response:
                discussions = json.loads(response.read())
            root = discussions["items"][0]["root_message_key"]
            with urlopen(
                base + f"/api/mailing-lists/messages/{root}/children"
            ) as response:
                children = json.loads(response.read())
            self.assertEqual(len(children["items"]), 2)
            with urlopen(base + f"/api/mailing-lists/messages/{root}") as response:
                detail = json.loads(response.read())
            self.assertEqual(detail["summary"]["connectivity_state"], "connected")
            with urlopen(
                base + f"/api/mailing-lists/messages/{root}/content"
            ) as response:
                self.assertIn(b"Message-ID: <task023-root", response.read())
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_schema_v1_migrates_to_current_without_parallel_authority(self) -> None:
        tables = [
            "artifact_stream_membership_lineage", "artifact_stream_memberships",
            "artifact_stream_run_plans", "artifact_stream_runs",
            "artifact_stream_projections", "artifact_stream_dependencies",
            "artifact_stream_revisions", "artifact_streams",
            "mailing_list_discussion_members", "mailing_list_discussions",
            "mailing_list_relationships", "mailing_list_messages",
            "mailing_list_run_items", "mailing_list_runs", "mailing_list_sources",
        ]
        with RepositoryDatabase.open(self.state).connect() as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            for table in tables:
                connection.execute(f"DROP TABLE {table}")
            connection.execute("UPDATE schema_metadata SET schema_version=1")
        database = RepositoryDatabase.open(self.state)
        self.assertEqual(database.validate()["schema_version"], 5)
        with database.connect(read_only=True) as connection:
            names = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
            )}
        self.assertTrue(set(tables).issubset(names))


if __name__ == "__main__":
    unittest.main()
