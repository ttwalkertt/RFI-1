#!/usr/bin/env python3
"""Produce deterministic operator-workflow evidence for TASK-054."""

from __future__ import annotations

import json
import tempfile
import threading
import urllib.request
from pathlib import Path

from rfi.admin import create_admin_server
from rfi.cli import initialize
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/microsoft.firm-config.example.json"
HINT = "https://stockanalysis.com/stocks/msft/transcripts/"


def current_profile(state: Path) -> tuple[str, tuple[str, ...]]:
    profile = SourceProfileRepository.open(
        state / "source-profiles", load_canonical_template()
    ).get("microsoft")
    assert profile is not None
    transcript = next(
        item for item in profile.items if item.artifact_id == "earnings_transcript"
    )
    return (
        profile.source_profile_revision_id,
        transcript.retrieval_candidates[0].discovery_hints,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / "state"
        configured = state / "firm-config"
        configured.mkdir(parents=True)
        target = configured / "microsoft.firm-config.json"
        value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        initialize(state)
        before_revision = RepositoryDatabase.open(state).revision()
        before_profile, before_hints = current_profile(state)

        value["sources"]["earnings_transcript"]["discovery_hints"] = [HINT]
        target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        server = create_admin_server(state, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        host, port = server.server_address
        request = urllib.request.Request(
            f"http://{host}:{port}/api/firm-configurations/reload",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                result = json.loads(response.read())
            after_profile, after_hints = current_profile(state)
            evidence = {
                "task": "TASK-054",
                "endpoint": "/api/firm-configurations/reload",
                "request": {},
                "response": result,
                "before": {
                    "repository_authority_revision": before_revision,
                    "source_profile_revision_id": before_profile,
                    "configured_hint_present": HINT in before_hints,
                },
                "after": {
                    "repository_authority_revision": RepositoryDatabase.open(state).revision(),
                    "source_profile_revision_id": after_profile,
                    "configured_hint_first": after_hints[0] == HINT,
                    "server_restarted": False,
                },
            }
            print(json.dumps(evidence, indent=2, sort_keys=True))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
