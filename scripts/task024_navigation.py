#!/usr/bin/env python3
"""Serve a disposable seeded admin console for TASK-024 browser verification."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.firms import FirmRepository, sample_firms
from rfi.source_profiles import (
    SourceProfileDraft,
    SourceProfileRepository,
    load_canonical_template,
)


def seed(state: Path) -> None:
    """Create one configured firm whose default enabled items need configuration."""
    ConceptRepository.initialize(state)
    firms = FirmRepository.initialize(state / "firm-catalog")
    firms.create(sample_firms()[0])
    template = load_canonical_template()
    profiles = SourceProfileRepository.initialize(state / "source-profiles", template)
    profiles.publish(SourceProfileDraft("seagate", ()), None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("serve",))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8894)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rfi-task024-browser-") as temporary:
        state = Path(temporary) / "state"
        seed(state)
        server = create_admin_server(state, arguments.host, arguments.port)
        print(
            f"TASK-024 browser fixture: http://{arguments.host}:{server.server_port}/pull-sources",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
