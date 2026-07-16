"""Offline tests for the private local runtime-configuration boundary."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from rfi.acquisition.contracts import ContractError
from rfi.acquisition.runtime_config import load_runtime_configuration

USER_AGENT = "RFI-1-tests test-contact@example.invalid"
API_KEY = "synthetic-test-key"


class RuntimeConfigurationTests(unittest.TestCase):
    def write_config(self, root: Path, content: str, mode: int = 0o600) -> Path:
        path = root / ".rfi/runtime.env"
        path.parent.mkdir()
        path.write_text(content, encoding="utf-8")
        path.chmod(mode)
        return path

    def test_private_local_file_supports_only_governed_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_config(
                root,
                f"# local only\nRFI_SEC_USER_AGENT={USER_AGENT}\n"
                "SEC_API_IO_API_KEY" + f"={API_KEY}\n",
            )
            self.assertEqual(
                load_runtime_configuration(root, {}),
                {"RFI_SEC_USER_AGENT": USER_AGENT, "SEC_API_IO_API_KEY": API_KEY},
            )

    def test_environment_overrides_local_values_key_by_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_config(
                root,
                f"RFI_SEC_USER_AGENT={USER_AGENT}\n"
                "SEC_API_IO_API_KEY" + f"={API_KEY}\n",
            )
            override = "RFI-1-override override@example.invalid"
            loaded = load_runtime_configuration(root, {"RFI_SEC_USER_AGENT": override})
            self.assertEqual(loaded["RFI_SEC_USER_AGENT"], override)
            self.assertEqual(loaded["SEC_API_IO_API_KEY"], API_KEY)

    def test_local_loading_can_be_disabled_for_offline_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_config(root, f"RFI_SEC_USER_AGENT={USER_AGENT}\n", 0o644)
            self.assertEqual(load_runtime_configuration(root, {}, allow_local=False), {})

    def test_missing_file_is_an_empty_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(load_runtime_configuration(Path(temporary), {}), {})

    def test_rejects_permissive_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_config(root, f"RFI_SEC_USER_AGENT={USER_AGENT}\n", 0o644)
            with self.assertRaisesRegex(ContractError, "permissions"):
                load_runtime_configuration(root, {})

    def test_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text(f"RFI_SEC_USER_AGENT={USER_AGENT}\n", encoding="utf-8")
            target.chmod(0o600)
            config = root / ".rfi/runtime.env"
            config.parent.mkdir()
            os.symlink(target, config)
            with self.assertRaisesRegex(ContractError, "opened safely"):
                load_runtime_configuration(root, {})

    def test_rejects_unknown_duplicate_empty_and_malformed_lines(self) -> None:
        cases = (
            "UNSUPPORTED=value\n",
            f"RFI_SEC_USER_AGENT={USER_AGENT}\nRFI_SEC_USER_AGENT=second\n",
            "RFI_SEC_USER_AGENT=\n",
            "RFI_SEC_USER_AGENT\n",
        )
        for content in cases:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.write_config(root, content)
                with self.assertRaises(ContractError):
                    load_runtime_configuration(root, {})

    def test_rejects_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_config(root, "#" + ("x" * (16 * 1024)) + "\n")
            with self.assertRaisesRegex(ContractError, "size limit"):
                load_runtime_configuration(root, {})


if __name__ == "__main__":
    unittest.main()
