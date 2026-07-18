#!/usr/bin/env python3
"""Run deterministic browser-equivalent TASK-017 operator proof against production pages."""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from pathlib import Path

from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.firms import FirmRepository, sample_firms
from rfi.source_profiles import (
    SourceProfileDraft,
    SourceProfileRepository,
    load_canonical_template,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Prove two-firm navigation/refresh behavior and absence of implicit authority writes."""
    with tempfile.TemporaryDirectory(prefix="rfi-task017-proof-") as temporary:
        state = Path(temporary) / "state"
        ConceptRepository.initialize(state)
        firms = FirmRepository.initialize(state / "firm-catalog")
        for draft in sample_firms()[:2]:
            firms.create(draft)
        template = load_canonical_template()
        profiles = SourceProfileRepository.initialize(state / "source-profiles", template)
        profiles.publish(SourceProfileDraft("seagate", ()), None)
        profiles.publish(SourceProfileDraft("western-digital", ()), None)
        revisions_before = tuple(
            path.read_bytes()
            for path in sorted((state / "source-profiles").rglob("*"))
            if path.is_file()
        )
        server = create_admin_server(state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            result = subprocess.run(
                [
                    "node",
                    "tests/task017_browser_harness.js",
                    f"http://{host}:{port}",
                    str(ROOT / "src/rfi/admin/admin_preferences.js"),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        if result.returncode:
            print(result.stdout, end="")
            return result.returncode
        revisions_after = tuple(
            path.read_bytes()
            for path in sorted((state / "source-profiles").rglob("*"))
            if path.is_file()
        )
        evidence = json.loads(result.stdout)
        evidence.update(
            {
                "productionPagesAndServerContracts": True,
                "sourceProfileStateByteIdentical": revisions_after == revisions_before,
                "firmsExercised": ["western-digital", "seagate"],
            }
        )
        if not evidence["sourceProfileStateByteIdentical"]:
            evidence["result"] = "FAIL"
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
