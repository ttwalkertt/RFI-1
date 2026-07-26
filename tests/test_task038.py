"""Focused acceptance coverage for TASK-038 configuration-only reset support."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

import yaml

from rfi.firms import FirmRepository, sample_firms
from rfi.cli import main as cli_main
from rfi.mailing_lists import (
    AcquisitionLimits, FixtureMailingListArchive, LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService, MailingListRepository, SelectionCriteria,
)
from rfi.mailing_lists.contracts import ArchiveMessage
from rfi.mailing_lists.parser import parse_message
from rfi.sec import SecApplicability, SecRepository, SecSourceKnowledge
from rfi.source_profiles import (
    SourceProfileDraft, SourceProfileItem, SourceProfileRepository,
    load_canonical_template,
)
from rfi.storage import RepositoryDatabase
from rfi.storage.configuration import (
    ConfigurationError, export_configuration, import_configuration,
)
from rfi.streams import StreamDraft, StreamRepository, StreamService

ROOT = Path(__file__).resolve().parents[1]


def archive() -> FixtureMailingListArchive:
    messages = {}
    for path in sorted((ROOT / "fixtures/linux-block").glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    return FixtureMailingListArchive(messages)


class ConfigurationResetCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.populated = self.root / "populated"
        self.fresh = self.root / "fresh"
        self._populate()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _initialize(self, state: Path) -> None:
        RepositoryDatabase.initialize(state)
        FirmRepository.initialize(state / "firm-catalog")
        SourceProfileRepository.initialize(
            state / "source-profiles", load_canonical_template()
        )

    def _populate(self) -> None:
        self._initialize(self.populated)
        firm = next(item for item in sample_firms() if item.firm_id == "seagate")
        FirmRepository.open(self.populated / "firm-catalog").create(firm)
        template = load_canonical_template()
        profile = SourceProfileDraft(
            firm.firm_id,
            tuple(SourceProfileItem(item.artifact_id, item.default_enabled)
                  for item in template.artifacts),
            "operator-authored acquisition choices",
        )
        SourceProfileRepository.open(
            self.populated / "source-profiles", template
        ).publish(profile, None)
        mailing = MailingListRepository(self.populated)
        mailing.configure_source(replace(LINUX_BLOCK_SOURCE, display_name="Linux Block Layer"))
        SecRepository(self.populated).persist_source(SecSourceKnowledge(
            firm.firm_id, SecApplicability.DIRECT, "Seagate Technology Holdings plc",
            "1137789", "domestic", "verified", "2026-07-26T00:00:00+00:00",
        ), None)
        stream = StreamDraft(
            "linux-block-storage", "Linux Block Storage", "Bounded block-layer stream", True,
            "external", (LINUX_BLOCK_SOURCE.source_id,), "mail.message",
            {"op": "predicate", "field": "title", "operator": "contains", "value": "block"},
            {"strategy": "connected_discussion", "ancestor_closure": True,
             "descendant_depth": 2},
            {"seed_limit": 10, "expanded_limit": 100}, {"notes": "RBF reset proof"},
        )
        StreamService(StreamRepository(self.populated)).save(stream)
        MailingListAcquisitionService(
            mailing, archive(), clock=lambda: "2026-07-26T00:00:00+00:00",
            identifiers=lambda: "mailrun-task038",
        ).acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=("<task023-root@kernel.example>",)),
            AcquisitionLimits(seed_limit=1, context_limit=20, descendant_depth=2),
        )
        StreamService(
            StreamRepository(self.populated),
            clock=lambda: "2026-07-26T00:01:00+00:00",
            identifiers=lambda: "streamrun-task038",
        ).run(stream.stream_id)

    def counts(self, state: Path) -> dict[str, int]:
        tables = (
            "artifacts", "acquisition_attempts", "mailing_list_runs",
            "mailing_list_fetch_history", "artifact_stream_projections",
            "artifact_stream_runs", "artifact_stream_memberships",
            "mailing_list_message_conflicts", "mailing_list_discussions",
        )
        with RepositoryDatabase.open(state).connect(read_only=True) as connection:
            return {table: int(connection.execute(
                f"SELECT count(*) FROM {table}"
            ).fetchone()[0]) for table in tables}

    def test_export_is_deterministic_versioned_and_contains_no_evidence_identifiers(self) -> None:
        first = export_configuration(self.populated)
        second = export_configuration(self.populated)
        self.assertEqual(first, second)
        value = yaml.safe_load(first)
        self.assertEqual((value["format"], value["version"]), ("rfi-config", 1))
        self.assertEqual(len(value["firms"]), 1)
        rendered = first.lower()
        for forbidden in (
            "artifact-", "run_id", "artifact_stream_runs", "coverage", "conflict_id",
            "projection", str(self.populated).lower(),
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertGreater(self.counts(self.populated)["artifacts"], 0)

    def test_reset_import_restores_configuration_only_and_can_start_acquisition(self) -> None:
        package = export_configuration(self.populated)
        self._initialize(self.fresh)
        created = import_configuration(self.fresh, package)
        self.assertEqual(created, {
            "firms": 1, "source_profiles": 1, "sources": 1,
            "sec_sources": 1, "streams": 1,
        })
        self.assertEqual(export_configuration(self.fresh), package)
        self.assertTrue(all(count == 0 for count in self.counts(self.fresh).values()))
        self.assertEqual(import_configuration(self.fresh, package), {
            "firms": 0, "source_profiles": 0, "sources": 0,
            "sec_sources": 0, "streams": 0,
        })
        preview = MailingListAcquisitionService(
            MailingListRepository(self.fresh), archive()
        ).preview(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=("<task023-root@kernel.example>",)),
            AcquisitionLimits(seed_limit=1, context_limit=20, descendant_depth=2),
        )
        self.assertGreater(len(preview.seed_ids), 0)

    def test_cli_export_init_import_operator_workflow(self) -> None:
        output = self.root / "rfi-config.yaml"
        streams = (StringIO(), StringIO())
        with redirect_stdout(streams[0]), redirect_stderr(streams[1]):
            self.assertEqual(cli_main([
                "config", "--state", str(self.populated), "export", "--output", str(output),
            ]), 0)
            self.assertEqual(cli_main(["init", "--state", str(self.fresh)]), 0)
            self.assertEqual(cli_main([
                "config", "--state", str(self.fresh), "import", "--file", str(output),
            ]), 0)
        self.assertEqual(export_configuration(self.fresh), output.read_text(encoding="utf-8"))
        self.assertEqual(self.counts(self.fresh)["artifacts"], 0)

    def test_missing_uninitialized_incompatible_and_malformed_targets_are_refused(self) -> None:
        package = export_configuration(self.populated)
        with self.assertRaisesRegex(Exception, "not initialized"):
            import_configuration(self.root / "missing", package)
        incompatible = self.root / "incompatible"
        self._initialize(incompatible)
        with RepositoryDatabase.open(incompatible).transaction() as connection:
            connection.execute("UPDATE schema_metadata SET schema_version=999")
        with self.assertRaisesRegex(Exception, "schema version"):
            import_configuration(incompatible, package)
        self._initialize(self.fresh)
        with self.assertRaisesRegex(ConfigurationError, "unsupported configuration"):
            import_configuration(self.fresh, "format: rfi-config\nversion: 99\n")

    def test_conflict_and_late_validation_failure_leave_target_unchanged(self) -> None:
        self._initialize(self.fresh)
        conflicting = replace(
            next(item for item in sample_firms() if item.firm_id == "seagate"),
            canonical_name="Materially Different Seagate",
        )
        FirmRepository.open(self.fresh / "firm-catalog").create(conflicting)
        before = export_configuration(self.fresh)
        with self.assertRaisesRegex(ConfigurationError, "configuration conflict.*seagate"):
            import_configuration(self.fresh, export_configuration(self.populated))
        self.assertEqual(export_configuration(self.fresh), before)

        value = yaml.safe_load(export_configuration(self.populated))
        value["streams"][0]["input_ids"] = ["missing-upstream"]
        value["streams"][0]["input_kind"] = "streams"
        with self.assertRaises(Exception):
            import_configuration(self.fresh, yaml.safe_dump(value))
        self.assertEqual(export_configuration(self.fresh), before)


if __name__ == "__main__":
    unittest.main()
