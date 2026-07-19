from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.cli import main  # noqa: E402


class StableApplicationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "application-state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run the installed-entry implementation path while capturing operator output."""
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(arguments)
        return code, output.getvalue(), errors.getvalue()

    def test_top_level_and_command_help_are_discoverable_with_module_parity(self) -> None:
        environment = {"PYTHONPATH": str(SRC)}
        module = subprocess.run(
            [sys.executable, "-m", "rfi", "--help"],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        self.assertEqual(module.returncode, 0)
        for marker in ("RFI-1", "init", "seed", "admin", "Run init once", "python -m rfi"):
            self.assertIn(marker, module.stdout)
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stdout(io.StringIO()) as installed_output:
                main(["admin", "--help"])
        self.assertEqual(caught.exception.code, 0)
        for marker in ("never seeds", "--state", "--host", "--port", "Ctrl-C"):
            self.assertIn(marker, installed_output.getvalue())

    def test_fresh_and_repeated_init_and_seed_are_safe_and_explicit(self) -> None:
        code, first, _ = self.run_cli("init", "--state", str(self.state))
        self.assertEqual(code, 0)
        self.assertIn("created authoritative SQLite repository", first)
        code, repeated, _ = self.run_cli("init", "--state", str(self.state))
        self.assertEqual(code, 0)
        self.assertIn("already existed", repeated)
        code, first_seed, _ = self.run_cli("seed", "--state", str(self.state))
        self.assertEqual(code, 0)
        self.assertIn("starter concepts created: 6", first_seed)
        self.assertIn("starter target firms created: 3", first_seed)
        code, repeated_seed, _ = self.run_cli("seed", "--state", str(self.state))
        self.assertEqual(code, 0)
        self.assertIn("starter concepts created: 0; already present: 6", repeated_seed)
        self.assertIn("starter target firms created: 0; already present: 3", repeated_seed)

    def test_admin_opens_both_catalogs_and_never_implicitly_seeds(self) -> None:
        self.assertEqual(self.run_cli("init", "--state", str(self.state))[0], 0)
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/api/concepts") as response:
                concepts = json.load(response)
            with urllib.request.urlopen(f"http://{host}:{port}/api/firms") as response:
                firms = json.load(response)
            self.assertEqual((concepts["items"], firms["items"]), ([], []))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(self.run_cli("seed", "--state", str(self.state))[0], 0)
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/api/concepts") as response:
                self.assertEqual(len(json.load(response)["items"]), 6)
            with urllib.request.urlopen(f"http://{host}:{port}/api/firms") as response:
                self.assertEqual(len(json.load(response)["items"]), 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_missing_state_invalid_port_and_incompatible_state_fail_clearly(self) -> None:
        code, _, errors = self.run_cli("seed", "--state", str(self.state))
        self.assertEqual(code, 2)
        self.assertIn("state is not initialized", errors)
        self.assertIn("run 'rfi init'", errors)
        self.run_cli("init", "--state", str(self.state))
        code, _, errors = self.run_cli(
            "admin", "--state", str(self.state), "--port", "70000"
        )
        self.assertEqual(code, 2)
        self.assertIn("port must be between 0 and 65535", errors)
        (self.state / "catalog.json").write_text("{}\n", encoding="utf-8")
        code, _, errors = self.run_cli("init", "--state", str(self.state))
        self.assertEqual(code, 2)
        self.assertIn("cannot be mixed", errors)


if __name__ == "__main__":
    unittest.main()
