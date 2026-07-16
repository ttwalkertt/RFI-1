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
        self.assertEqual(len(manifest["documents"]), 7)
        for document in manifest["documents"]:
            destination = ROOT / document["destination"]
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            self.assertEqual(digest, document["destination_sha256"], destination.name)

    def test_product_scope_is_acquisition_only(self) -> None:
        package_files = sorted(
            path.relative_to(SRC / "rfi").as_posix()
            for path in (SRC / "rfi").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        self.assertEqual(
            package_files,
            [
                "__init__.py",
                "acquisition/__init__.py",
                "acquisition/contracts.py",
                "acquisition/demo.py",
                "acquisition/edgar.py",
                "acquisition/engine.py",
                "acquisition/fixture_adapters.py",
                "acquisition/persistence.py",
                "acquisition/repository.py",
                "acquisition/sec_api.py",
                "py.typed",
            ],
        )


if __name__ == "__main__":
    unittest.main()
