from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import rfi  # noqa: E402


class FoundationTests(unittest.TestCase):
    def test_package_exposes_bootstrap_version(self) -> None:
        self.assertEqual(rfi.__version__, "0.0.0")

    def test_imported_design_baseline_matches_recorded_destinations(self) -> None:
        manifest = json.loads((ROOT / "docs" / "design-baseline.json").read_text())
        self.assertEqual(len(manifest["documents"]), 8)
        for document in manifest["documents"]:
            destination = ROOT / document["destination"]
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            self.assertEqual(digest, document["destination_sha256"], destination.name)

    def test_product_scope_matches_completed_architectural_milestones(self) -> None:
        package_files = sorted(
            path.relative_to(SRC / "rfi").as_posix()
            for path in (SRC / "rfi").rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.name != ".DS_Store"
        )
        self.assertEqual(
            package_files,
            [
                "__init__.py",
                "__main__.py",
                "acquisition/__init__.py",
                "acquisition/contracts.py",
                "acquisition/demo.py",
                "acquisition/direct_url.py",
                "acquisition/edgar.py",
                "acquisition/engine.py",
                "acquisition/fixture_adapters.py",
                "acquisition/persistence.py",
                "acquisition/repository.py",
                "acquisition/runtime_config.py",
                "acquisition/sec_api.py",
                "acquisition/sec_form_10k.py",
                "acquisition/sec_form_10q.py",
                "acquisition/sec_form_20f.py",
                "acquisition/sec_form_6k.py",
                "acquisition/sec_form_8k.py",
                "acquisition/sec_numbered_form.py",
                "acquisition/sec_provider.py",
                "admin/__init__.py",
                "admin/admin_preferences.js",
                "admin/artifact_browser.html",
                "admin/console.html",
                "admin/external_sources.html",
                "admin/field_definitions.py",
                "admin/firms.html",
                "admin/pull_sources.html",
                "admin/server.py",
                "admin/source_profiles.html",
                "admin/streams.html",
                "artifacts/__init__.py",
                "artifacts/contracts.py",
                "artifacts/service.py",
                "catalog_import.py",
                "cli.py",
                "concepts/__init__.py",
                "concepts/contracts.py",
                "concepts/derivation.py",
                "concepts/repository.py",
                "concepts/samples.py",
                "concepts/service.py",
                "firms/__init__.py",
                "firms/contracts.py",
                "firms/repository.py",
                "firms/samples.py",
                "firms/service.py",
                "intelligence/__init__.py",
                "intelligence/contracts.py",
                "intelligence/deterministic.py",
                "intelligence/inspection.py",
                "intelligence/orchestration.py",
                "knowledge/__init__.py",
                "knowledge/contracts.py",
                "knowledge/derivation.py",
                "knowledge/repository.py",
                "mailing_lists/__init__.py",
                "mailing_lists/contracts.py",
                "mailing_lists/parser.py",
                "mailing_lists/provider.py",
                "mailing_lists/repository.py",
                "mailing_lists/service.py",
                "pull/__init__.py",
                "pull/adapters.py",
                "pull/contracts.py",
                "pull/planning.py",
                "pull/repository.py",
                "pull/workflow.py",
                "py.typed",
                "resources/source-profile-template.yaml",
                "retrieval/__init__.py",
                "retrieval/contracts.py",
                "retrieval/evidence.py",
                "retrieval/replaceability.py",
                "retrieval/repository.py",
                "retrieval/vector.py",
                "source_objects/__init__.py",
                "source_objects/contracts.py",
                "source_objects/parser.py",
                "source_objects/repository.py",
                "source_profiles/__init__.py",
                "source_profiles/contracts.py",
                "source_profiles/repository.py",
                "source_profiles/service.py",
                "source_profiles/template.py",
                "storage/__init__.py",
                "storage/backup.py",
                "storage/sqlite.py",
                "streams/__init__.py",
                "streams/contracts.py",
                "streams/definition.py",
                "streams/registry.py",
                "streams/repository.py",
                "streams/service.py",
                "workspace/__init__.py",
                "workspace/contracts.py",
                "workspace/repository.py",
                "workspace/service.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
