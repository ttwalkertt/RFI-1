"""Acceptance coverage for TASK-026 usable stream configuration and canonical YAML."""

from __future__ import annotations

import contextlib
import io
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from pathlib import Path

import yaml

from rfi.admin import create_admin_server
from rfi.cli import initialize, main
from rfi.firms import FirmRepository
from rfi.mailing_lists import LINUX_BLOCK_SOURCE, MailingListRepository
from rfi.storage import RepositoryDatabase
from rfi.streams import (
    StreamDraft,
    StreamRepository,
    StreamService,
    parse_yaml,
    semantic_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "fixtures/streams/task026-external.yaml"
DERIVED = ROOT / "fixtures/streams/task026-derived.yaml"


class StreamYamlCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        MailingListRepository(self.state).configure_source(LINUX_BLOCK_SOURCE)
        self.repository = StreamRepository(self.state)
        self.service = StreamService(self.repository)
        self.external_text = EXTERNAL.read_text(encoding="utf-8")
        self.derived_text = DERIVED.read_text(encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_external_and_derived_round_trip_is_deterministic(self) -> None:
        external = self.service.review_yaml(self.external_text)
        self.assertTrue(external.valid, external.errors)
        self.assertEqual(external.import_mode, "new")
        self.assertEqual(external.draft.input_kind, "external")  # type: ignore[union-attr]
        created = self.service.import_yaml(self.external_text, "new")
        derived = self.service.review_yaml(self.derived_text)
        self.assertTrue(derived.valid, derived.errors)
        self.service.import_yaml(self.derived_text, "new")
        exported = self.service.export_yaml(created.revision.stream_id)
        self.assertEqual(exported, self.service.export_yaml(created.revision.stream_id))
        reparsed = self.service.review_yaml(exported)
        self.assertTrue(reparsed.valid, reparsed.errors)
        self.assertEqual(
            semantic_fingerprint(created.revision.draft), reparsed.semantic_fingerprint
        )
        self.assertTrue(exported.endswith("\n"))
        self.assertEqual(yaml.safe_load(exported)["schema_version"], 1)

    def test_strict_safe_parsing_reports_actionable_paths(self) -> None:
        cases = {
            "schema_version: 99\nstream: {}\n": (
                "unsupported_schema_version", "$.schema_version"
            ),
            self.external_text.replace(
                "  metadata:\n", "  mystery: true\n  metadata:\n"
            ): ("unknown_field", "$.stream.mystery"),
            self.external_text.replace(
                "    artifact_schema: mail.message\n",
                "    artifact_schema: mail.message\n    api_token: secret\n",
            ): ("forbidden_configuration", "$.stream.input.api_token"),
            self.external_text.replace(
                "schema_version: 1\n", "schema_version: 1\nschema_version: 1\n"
            ): ("malformed_yaml", "$"),
        }
        for text, (code, path) in cases.items():
            with self.subTest(code=code):
                review = self.service.review_yaml(text)
                self.assertFalse(review.valid)
                self.assertEqual(review.errors[0]["code"], code)
                self.assertIn(path, review.errors[0]["message"])

    def test_capability_reference_bounds_and_cycle_failures_are_shared(self) -> None:
        invalid_operator = self.external_text.replace("operator: on_or_after", "operator: runs")
        review = self.service.review_yaml(invalid_operator)
        self.assertEqual(review.errors[0]["code"], "unsupported_operator")
        self.assertIn("$.stream.selection", review.errors[0]["path"])

        missing_source = self.external_text.replace("linux-block-lore", "missing-source")
        self.assertEqual(
            self.service.review_yaml(missing_source).errors[0]["code"], "unknown_source"
        )
        self.service.import_yaml(self.external_text, "new")
        missing_upstream = self.derived_text.replace("linux-block-storage", "missing-stream")
        self.assertEqual(
            self.service.review_yaml(missing_upstream).errors[0]["code"], "unknown_upstream"
        )
        self_reference = self.derived_text.replace("linux-block-storage", "smr-discussions")
        self.assertEqual(
            self.service.review_yaml(self_reference).errors[0]["code"], "self_reference"
        )
        invalid_bounds = self.external_text.replace("direct_matches: 25", "direct_matches: 0")
        self.assertEqual(
            self.service.review_yaml(invalid_bounds).errors[0]["code"], "invalid_bounds"
        )

        self.service.import_yaml(self.derived_text, "new")
        cycle = self.external_text.replace(
            "kind: external_source\n    source_profile_id: linux-block-lore",
            "kind: upstream_streams\n    stream_ids:\n    - smr-discussions",
        )
        cycle_review = self.service.review_yaml(cycle)
        self.assertIn("dependency_cycle", {item["code"] for item in cycle_review.errors})

    def test_semantic_diff_and_identical_reimport_preserve_revision_history(self) -> None:
        first = self.service.import_yaml(self.external_text, "new")
        formatted = yaml.safe_dump(yaml.safe_load(self.external_text), sort_keys=True)
        review = self.service.review_yaml(formatted)
        self.assertEqual(review.import_mode, "already_current")
        self.assertEqual(review.differences, ())
        same = self.service.import_yaml(formatted, "revision")
        self.assertEqual(same.outcome, "already_current")
        self.assertEqual(len(self.service.history("linux-block-storage")), 1)

        changed = self.external_text.replace("direct_matches: 25", "direct_matches: 26")
        changed_review = self.service.review_yaml(changed)
        self.assertEqual(changed_review.import_mode, "revision")
        self.assertEqual(changed_review.differences[0]["category"], "bounds")
        with self.assertRaisesRegex(Exception, "requires revision mode"):
            self.service.import_yaml(changed, "new")
        revised = self.service.import_yaml(changed, "revision", first.revision.revision_id)
        self.assertEqual(revised.revision.revision_number, 2)
        self.assertEqual(len(self.service.history("linux-block-storage")), 2)

    def test_validation_preview_and_import_do_not_run_or_change_governed_source(self) -> None:
        before_source = asdict(
            MailingListRepository(self.state).source(LINUX_BLOCK_SOURCE.source_id)
        )
        review = self.service.review_yaml(self.external_text)
        self.assertTrue(review.valid)
        self.service.preview(review.draft)  # type: ignore[arg-type]
        self.assertEqual(self.repository.list_revisions(), ())
        self.assertEqual(self.repository.rows("SELECT * FROM artifact_stream_runs"), [])
        self.service.import_yaml(self.external_text, "new")
        self.assertEqual(self.repository.rows("SELECT * FROM artifact_stream_runs"), [])
        after_source = asdict(
            MailingListRepository(self.state).source(LINUX_BLOCK_SOURCE.source_id)
        )
        self.assertEqual(before_source, after_source)

    def test_contract_draft_and_yaml_share_normalization(self) -> None:
        parsed = parse_yaml(self.external_text)
        browser = StreamDraft(
            parsed.stream_id, parsed.name, parsed.description, parsed.enabled,
            parsed.input_kind, parsed.input_ids, parsed.schema_id, parsed.selection,
            parsed.expansion, parsed.bounds, parsed.metadata,
        )
        saved = self.service.save(browser)
        exported = self.service.export_yaml(saved.stream_id)
        self.assertEqual(
            semantic_fingerprint(saved.draft),
            self.service.review_yaml(exported).semantic_fingerprint,
        )


class StreamCliAndBrowserCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        with contextlib.redirect_stdout(io.StringIO()):
            initialize(self.state)
        MailingListRepository(self.state).configure_source(LINUX_BLOCK_SOURCE)
        self.external = EXTERNAL.read_text(encoding="utf-8")
        self.yaml_path = Path(self.temporary.name) / "stream.yaml"
        self.yaml_path.write_text(self.external, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_cli_schema_validate_import_export_and_clean_stdout(self) -> None:
        code, schema, diagnostics = self.invoke("stream", "schema")
        self.assertEqual((code, diagnostics), (0, ""))
        self.assertEqual(yaml.safe_load(schema)["schema_version"], 1)
        base = ("stream", "--state", str(self.state))
        code, validated, diagnostics = self.invoke(*base, "validate", "--file", str(self.yaml_path))
        self.assertEqual((code, diagnostics), (0, ""))
        self.assertTrue(yaml.safe_load(validated) if False else validated)
        code, imported, diagnostics = self.invoke(
            *base, "import", "--file", str(self.yaml_path), "--new"
        )
        self.assertEqual((code, diagnostics), (0, ""))
        self.assertIn('"outcome": "created"', imported)
        self.assertEqual(
            StreamRepository(self.state).rows("SELECT * FROM artifact_stream_runs"), []
        )
        output = Path(self.temporary.name) / "export.yaml"
        code, exported, diagnostics = self.invoke(
            *base, "export", "--stream", "linux-block-storage"
        )
        self.assertEqual((code, diagnostics), (0, ""))
        self.assertEqual(yaml.safe_load(exported)["stream"]["stream_id"], "linux-block-storage")
        code, stdout, diagnostics = self.invoke(
            *base, "export", "--stream", "linux-block-storage", "--output", str(output)
        )
        self.assertEqual((code, stdout, diagnostics), (0, "", ""))
        self.assertEqual(output.read_text(encoding="utf-8"), exported)

        changed = self.external.replace("direct_matches: 25", "direct_matches: 26")
        self.yaml_path.write_text(changed, encoding="utf-8")
        code, revised, _diagnostics = self.invoke(
            *base, "import", "--file", str(self.yaml_path), "--revision"
        )
        self.assertEqual(code, 0)
        self.assertIn('"outcome": "revised"', revised)
        code, already, _diagnostics = self.invoke(
            *base, "import", "--file", str(self.yaml_path), "--revision"
        )
        self.assertEqual(code, 0)
        self.assertIn('"outcome": "already_current"', already)

    def test_cli_invalid_yaml_is_nonzero_and_path_is_on_stderr(self) -> None:
        self.yaml_path.write_text(
            self.external.replace("artifact_schema: mail.message", "artifact_schema: unknown"),
            encoding="utf-8",
        )
        code, stdout, stderr = self.invoke(
            "stream", "--state", str(self.state), "validate", "--file", str(self.yaml_path)
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("$.stream.input.artifact_schema", stderr)

    def test_browser_page_sections_and_shared_yaml_routes(self) -> None:
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/streams") as response:
                html = response.read().decode()
            for label in (
                "Identity", "Input", "Selection", "Context and limits", "Review and save",
                "Advanced policy", "Import YAML", "Run a saved revision",
            ):
                self.assertIn(label, html)
            self.assertIn('id="run" type="button" disabled', html)
            self.assertIn('id="yaml-file" type="file"', html)
            self.assertNotIn('name="archive_base_url"', html)

            request = urllib.request.Request(
                base + "/api/streams/yaml/review",
                data=("{\"yaml\":" + __import__("json").dumps(self.external) + "}").encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                review = __import__("json").load(response)
            self.assertTrue(review["valid"])
            self.assertEqual(StreamRepository(self.state).list_revisions(), ())

            invalid = urllib.request.Request(
                base + "/api/streams/yaml/import",
                data=b'{"yaml":"schema_version: 99","mode":"new"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(invalid)
            raised.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
