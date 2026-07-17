from __future__ import annotations

import contextlib
import copy
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.catalog_import import import_catalogs  # noqa: E402
from rfi.cli import main  # noqa: E402
from rfi.firms import FirmError, FirmRepository  # noqa: E402


class ExternalCatalogImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(arguments)
        return code, output.getvalue(), errors.getvalue()

    def template(self) -> dict[str, object]:
        code, output, errors = self.run_cli("seed", "--print-schema")
        self.assertEqual((code, errors), (0, ""))
        return yaml.safe_load(output)

    def catalog(self, firm_id: str = "external-firm", ticker: str = "EXT") -> dict:
        value = self.template()
        value["catalog"]["prepared_on"] = "2026-07-17"
        value["research"]["reviewed_on"] = "2026-07-17"
        value["research"]["sources"][0]["accessed_on"] = "2026-07-17"
        firm = value["firms"][0]
        firm["firm_id"] = firm_id
        firm["canonical_name"] = "External Firm"
        firm["valid_from"] = "2020-01-01"
        firm["identifiers"][0]["value"] = ticker
        firm["domains"] = [f"{firm_id}.example.com"]
        return value

    def write(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        return path

    def initialize(self) -> None:
        self.assertEqual(self.run_cli("init", "--state", str(self.state))[0], 0)

    def test_template_is_valid_canonical_yaml_without_state_or_mutation(self) -> None:
        code, output, errors = self.run_cli(
            "seed", "--state", str(self.root / "absent"), "--print-schema"
        )
        self.assertEqual((code, errors), (0, ""))
        parsed = yaml.safe_load(output)
        self.assertEqual(parsed["schema_version"], 1)
        self.assertIn("firm_id", parsed["firms"][0])
        self.assertEqual(parsed["firms"][0]["relevance"], 50)
        self.assertFalse((self.root / "absent").exists())

    def test_template_with_valid_placeholders_imports_and_is_idempotent(self) -> None:
        self.initialize()
        catalog = self.write("catalog.yaml", self.catalog())
        code, first, errors = self.run_cli(
            "seed", "--state", str(self.state), "--file", str(catalog)
        )
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("external catalogs validated: 1; target firms created: 1", first)
        code, second, errors = self.run_cli(
            "seed", "--state", str(self.state), "-f", str(catalog)
        )
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("target firms created: 0; already present: 1", second)
        self.assertEqual(FirmRepository.open(self.state / "firm-catalog").get(
            "external-firm").canonical_name, "External Firm")

    def test_relevance_persists_sorts_filters_searches_and_defaults_without_labels(self) -> None:
        self.initialize()
        high = self.catalog("high-relevance", "HIGH")
        high["firms"][0]["relevance"] = 87.5
        omitted = self.catalog("default-relevance", "DFLT")
        omitted["firms"][0].pop("relevance")
        high["firms"].append(copy.deepcopy(omitted["firms"][0]))
        path = self.write("relevance.yaml", high)
        self.assertEqual(
            self.run_cli("seed", "--state", str(self.state), "-f", str(path))[0], 0
        )
        repository = FirmRepository.open(self.state / "firm-catalog")
        self.assertEqual(repository.get("high-relevance").relevance, 87.5)
        self.assertEqual(repository.get("default-relevance").relevance, 0.0)
        imported = [
            item.firm_id
            for item in repository.lookup()
            if item.firm_id in {"high-relevance", "default-relevance"}
        ]
        self.assertEqual(imported, ["high-relevance", "default-relevance"])
        self.assertEqual(
            [item.firm_id for item in repository.lookup(minimum_relevance=80)],
            ["high-relevance"],
        )
        self.assertEqual(repository.lookup("87.5")[0].firm_id, "high-relevance")
        template_text = self.run_cli("seed", "--print-schema")[1]
        for classification in ("core", "ecosystem", "adjacent"):
            self.assertNotIn(classification, template_text.casefold())

    def test_invalid_relevance_fails_before_any_mutation(self) -> None:
        for index, invalid in enumerate((-1, 101, "core", True)):
            with self.subTest(invalid=invalid):
                state = self.root / f"invalid-relevance-state-{index}"
                self.assertEqual(self.run_cli("init", "--state", str(state))[0], 0)
                value = self.catalog(f"invalid-relevance-{index}", f"BAD{index}")
                value["firms"][0]["relevance"] = invalid
                path = self.write(f"invalid-relevance-{index}.yaml", value)
                pointer = (state / "firm-catalog/catalog.json").read_bytes()
                code, _, errors = self.run_cli(
                    "seed", "--state", str(state), "-f", str(path)
                )
                self.assertEqual(code, 2)
                self.assertIn("relevance", errors)
                self.assertEqual((state / "firm-catalog/catalog.json").read_bytes(), pointer)
                self.assertEqual(FirmRepository.open(state / "firm-catalog").lookup(), ())

    def test_injected_batch_persistence_failure_restores_exact_repository(self) -> None:
        self.initialize()
        value = self.catalog("atomic-first", "ATOM1")
        value["firms"].append(copy.deepcopy(self.catalog("atomic-second", "ATOM2")["firms"][0]))
        path = self.write("atomic.yaml", value)
        repository = FirmRepository.open(self.state / "firm-catalog")
        pointer_before = repository.pointer.read_bytes()
        revisions_before = {
            item.name: item.read_bytes() for item in repository.revisions_root.iterdir()
        }
        with self.assertRaisesRegex(FirmError, "injected batch persistence failure"):
            import_catalogs((path,), repository, fail_after_revision_count=1)
        self.assertEqual(repository.pointer.read_bytes(), pointer_before)
        self.assertEqual(
            {item.name: item.read_bytes() for item in repository.revisions_root.iterdir()},
            revisions_before,
        )
        self.assertEqual(repository.lookup(), ())
        self.assertEqual(FirmRepository.open(repository.root).verify()["result"], "PASS")

    def test_multiple_files_and_short_long_options(self) -> None:
        self.initialize()
        first = self.write("first.yaml", self.catalog("first-external", "ONE"))
        second = self.write("second.yaml", self.catalog("second-external", "TWO"))
        code, output, errors = self.run_cli(
            "seed", "--state", str(self.state), "-f", str(first), "--file", str(second)
        )
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("external catalogs validated: 2; target firms created: 2", output)

    def test_duplicate_and_conflicting_canonical_identifiers_fail_closed(self) -> None:
        self.initialize()
        duplicate = self.catalog()
        duplicate["firms"].append(dict(duplicate["firms"][0]))
        path = self.write("duplicate.yaml", duplicate)
        code, _, errors = self.run_cli("seed", "--state", str(self.state), "-f", str(path))
        self.assertEqual(code, 2)
        self.assertIn("duplicate canonical identifier", errors)
        self.assertEqual(len(FirmRepository.open(self.state / "firm-catalog").lookup()), 0)
        valid = self.write("valid.yaml", self.catalog())
        self.assertEqual(self.run_cli("seed", "--state", str(self.state), "-f", str(valid))[0], 0)
        conflict = self.catalog()
        conflict["firms"][0]["canonical_name"] = "Changed Name"
        conflict_path = self.write("conflict.yaml", conflict)
        code, _, errors = self.run_cli(
            "seed", "--state", str(self.state), "-f", str(conflict_path)
        )
        self.assertEqual(code, 2)
        self.assertIn("existing record differs", errors)
        self.assertEqual(
            FirmRepository.open(self.state / "firm-catalog").get(
                "external-firm").canonical_name,
            "External Firm",
        )

    def test_duplicate_recognition_identifier_and_late_invalid_record_do_not_mutate(self) -> None:
        self.initialize()
        value = self.catalog("first-external", "SAME")
        second = self.catalog("second-external", "SAME")["firms"][0]
        value["firms"].append(second)
        path = self.write("identifier-conflict.yaml", value)
        pointer = (self.state / "firm-catalog/catalog.json").read_bytes()
        revisions = tuple((self.state / "firm-catalog/revisions").iterdir())
        code, _, errors = self.run_cli("seed", "--state", str(self.state), "-f", str(path))
        self.assertEqual(code, 2)
        self.assertIn("conflicting firm identifier", errors)
        self.assertEqual((self.state / "firm-catalog/catalog.json").read_bytes(), pointer)
        self.assertEqual(tuple((self.state / "firm-catalog/revisions").iterdir()), revisions)
        self.assertEqual(FirmRepository.open(self.state / "firm-catalog").lookup(), ())

    def test_malformed_unsupported_empty_and_unreadable_files_are_actionable(self) -> None:
        self.initialize()
        cases = []
        malformed = self.root / "malformed.yaml"
        malformed.write_text("firms: [\n", encoding="utf-8")
        cases.append((malformed, "malformed YAML"))
        unsupported = self.catalog()
        unsupported["schema_version"] = 99
        cases.append((self.write("unsupported.yaml", unsupported), "unsupported schema_version"))
        empty = self.root / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        cases.append((empty, "catalog file is empty"))
        cases.append((self.root / "missing.yaml", "cannot read catalog file"))
        for path, message in cases:
            with self.subTest(message=message):
                code, _, errors = self.run_cli(
                    "seed", "--state", str(self.state), "-f", str(path)
                )
                self.assertEqual(code, 2)
                self.assertIn(message, errors)
        self.assertEqual(FirmRepository.open(self.state / "firm-catalog").lookup(), ())

    def test_all_files_validate_before_built_in_or_external_state_mutation(self) -> None:
        self.initialize()
        valid = self.write("valid.yaml", self.catalog())
        invalid = self.root / "invalid.yaml"
        invalid.write_text("not: [valid", encoding="utf-8")
        code, _, errors = self.run_cli(
            "seed", "--state", str(self.state), "-f", str(valid), "-f", str(invalid)
        )
        self.assertEqual(code, 2)
        self.assertIn("malformed YAML", errors)
        self.assertEqual(FirmRepository.open(self.state / "firm-catalog").lookup(), ())

    def test_installed_and_module_entry_points_have_behavioral_parity(self) -> None:
        environment = {**os.environ, "PYTHONPATH": str(SRC)}
        installed = subprocess.run(
            [str(ROOT / ".venv/bin/rfi"), "seed", "--print-schema"],
            cwd=ROOT, env=environment, text=True, capture_output=True, check=False,
        )
        module = subprocess.run(
            [sys.executable, "-m", "rfi", "seed", "--print-schema"],
            cwd=ROOT, env=environment, text=True, capture_output=True, check=False,
        )
        self.assertEqual(
            (installed.returncode, installed.stdout, installed.stderr),
            (module.returncode, module.stdout, module.stderr),
        )


if __name__ == "__main__":
    unittest.main()
